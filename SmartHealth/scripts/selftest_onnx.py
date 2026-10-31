"""ONNX 真实推理与模型仓库自测。

验证四组事实：

A. **模型仓库治理**
   - 清单可读写、幂等同步
   - SHA256 校验能识别被替换/损坏的权重（构造一份被篡改的副本，必须被拒）
   - **许可门禁**在 product 环境拒绝安装非商用权重（并说明可选做法）
   - verify 逐项检查：文件、校验和、ONNX 结构、真实算子、onnxruntime 会话、维度一致

B. **真实 ONNX 推理**
   - 会话真实建立，输入输出签名与计算图一致（不信任配置声明）
   - 布局从图推断（NCHW/NHWC）
   - 预处理正确性：归一化按预设、布局转换、尺寸缩放
   - **确定性**：同输入两次推理结果完全一致
   - **批处理等价**：一次喂 N 张 == 逐张喂，且 L2 归一化
   - **内容敏感**：不同图像内容产生不同 embedding（不是恒等映射）
   - 吞吐可测量

C. **降级路径**
   - 权重缺失/损坏时，有 fallback 则降级并明确标注"非真实权重"
   - 无 fallback 则抛 OnnxUnavailable（不静默用假数据）

D. **与流水线集成**
   - 真实 ONNX 编码器接入 encoder_service 后，能跑通图块抽取 → 编码 → MIL 预测

    python scripts/selftest_onnx.py
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [ OK ] {label}" + (f"  —— {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  [FAIL] {label}  {detail}")


def make_tiles(seed: int = 1) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """构造三张内容明确不同的图块：深染核密 / 浅染背景 / 中等。"""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:128, 0:128]

    dense = np.full((128, 128, 3), 232, dtype=np.uint8)
    mask = (np.sin(xx * 0.7) * np.sin(yy * 0.7)) > 0.55
    dense[mask] = (72, 46, 122)

    flat = np.full((128, 128, 3), 232, dtype=np.uint8)

    moderate = np.full((128, 128, 3), 226, dtype=np.uint8)
    soft = (np.sin(xx * 0.35) * np.sin(yy * 0.35)) > 0.5
    moderate[soft] = (196, 158, 182)
    moderate += rng.integers(-4, 5, moderate.shape, dtype=np.int16).astype(np.uint8)
    return dense, flat, moderate


def main() -> int:
    from app.services import model_registry as reg
    from app.services.encoder_service import (
        LicenseViolation, OnnxTileEncoder, OnnxUnavailable, encoder_service,
    )

    print("=" * 78)
    print("  ONNX 真实推理与模型仓库自测")
    print("=" * 78)

    # ---------------------------------------------------------- A. 仓库治理
    print("\n[A] 模型仓库治理")
    reg.ensure_dirs()
    added = reg.seeded_default_manifest()
    entries = reg.all_entries()
    check("清单可同步内置编码器声明（幂等）", len(entries) >= 8,
          f"{len(entries)} 条（本次新增 {added}）")
    check("重复同步不产生重复条目",
          reg.seeded_default_manifest() == 0, "第二次同步新增 0 条")

    overview = reg.registry_overview()
    check("概览统计可算（含按许可/阶段分组）",
          overview["total"] == len(entries) and overview["by_license"],
          f"许可分布 {overview['by_license']}")

    # 许可门禁：product 环境安装非商用权重必须被拒
    non_commercial = next((e for e in entries
                           if not e.commercial_usable and not e.is_self_developed), None)
    if non_commercial is not None:
        blocked = False
        detail = ""
        try:
            reg.install_entry(non_commercial.code, source="", deployment_env="product")
        except LicenseViolation as exc:
            blocked = True
            detail = str(exc).splitlines()[0][:70]
        except reg.ModelRegistryError as exc:
            blocked = True
            detail = f"（{type(exc).__name__}）{str(exc).splitlines()[0][:60]}"
        check(f"product 环境拒绝安装非商用权重（{non_commercial.code}）", blocked, detail)

        # research 环境不应被许可拦截。这里用「不存在的本地文件」触发失败，
        # 避免测试联网（院内是隔离网，测试不该依赖外网可用）。
        try:
            reg.install_entry(non_commercial.code, source=str(ROOT / "_no_such_weight.onnx"),
                              deployment_env="research")
            research_ok = True
            reason = "（竟然安装成功了）"
        except LicenseViolation:
            research_ok = False
            reason = "被许可拦截（不该：research 不应拦许可）"
        except reg.ModelRegistryError as exc:
            research_ok = True
            reason = f"非许可原因失败（正确）：{str(exc).splitlines()[0][:50]}"
        check("research 环境不拦许可（只在 product 拦）", research_ok, reason)

        # 联网下载失败应被包装成可读的仓库错误并给出离线做法
        offline_msg = ""
        try:
            reg._download("https://invalid.invalid/_no_such.onnx", ROOT / "_dl_probe.onnx")
        except reg.ModelRegistryError as exc:
            offline_msg = str(exc)
        except Exception as exc:
            offline_msg = f"未包装：{type(exc).__name__}"
        (ROOT / "_dl_probe.onnx").unlink(missing_ok=True)
        check("下载失败被包装为仓库错误并提示离线安装",
              "离线安装" in offline_msg, offline_msg.splitlines()[0][:60])

    # 自研参照模型
    entry = reg.get_entry("sh-ref-cnn-v1")
    if entry is None or not entry.installed_path:
        print("  → 未发现参照模型，先导出一份")
        entry = reg.register_reference(embedding_dim=256, tile_size=128)
    weight_path = Path(reg.weight_abspath(entry))
    check("自研参照权重已安装到磁盘", weight_path.exists(),
          f"{entry.installed_path}（{weight_path.stat().st_size / 1024:.1f} KB）")

    # ---------------------------------------------------------- A2. 篡改检测
    print("\n[A2] 权重完整性（篡改必须被识破）")
    tampered = weight_path.with_name("_tampered_copy.onnx")
    shutil.copy2(weight_path, tampered)
    with open(tampered, "r+b") as fh:      # 破坏一个字节（真实场景=损坏/被替换）
        fh.seek(max(0, tampered.stat().st_size // 2))
        original = fh.read(1)
        fh.seek(max(0, tampered.stat().st_size // 2))
        fh.write(bytes([original[0] ^ 0xFF]))

    expected = entry.sha256
    try:
        reg.install_entry(entry.code, source=str(tampered), expect_sha256=expected,
                          deployment_env="research")
        check("篡改的权重被 SHA256 校验拒绝", False, "竟然安装成功了")
    except reg.ModelRegistryError as exc:
        msg = str(exc)
        check("篡改的权重被 SHA256 校验拒绝", "校验失败" in msg,
              msg.splitlines()[0][:60])
    tampered.unlink(missing_ok=True)

    # 确认原权重未被误删
    check("拒绝安装时未破坏已装好的原权重",
          weight_path.exists() and reg.sha256_file(weight_path) == expected,
          f"sha256={reg.sha256_file(weight_path)[:12]}…")

    # ---------------------------------------------------------- A3. verify
    print("\n[A3] verify 逐项校验")
    result = reg.verify_entry(entry.code)
    names = [c["name"] for c in result["checks"]]
    check("verify 通过", result["ok"],
          f"{len(result['checks'])} 项检查全通过")
    for must in ("ONNX 结构合法（checker 通过）", "onnxruntime 可建立会话",
                 "含真实算子（非恒等映射）", "SHA256 与清单期望值一致"):
        check(f"  · 检查项存在：{must}", must in names)

    # ---------------------------------------------------------- B. 真实推理
    print("\n[B] 真实 ONNX 推理")
    encoder_service.sync_from_registry(verbose=False)
    enc = encoder_service.resolve(entry.code, strict=False)
    check("解析到 ONNX 后端", isinstance(enc, OnnxTileEncoder), type(enc).__name__)
    check("确认为真实权重（未回退）", bool(getattr(enc, "is_real_model", False)),
          f"is_real_model={getattr(enc, 'is_real_model', None)}")

    desc = enc.describe()
    check("输入输出签名来自计算图而非配置",
          desc["input_shape"] and desc["output_shape"] and desc["layout"] in ("NCHW", "NHWC"),
          f"{desc['layout']} {desc['input_shape']} → {desc['output_shape']}")
    check("算子直方图显示为真实网络",
          any(op in desc["ops"] for op in ("Conv", "MatMul", "Gemm", "Hardswish")),
          f"算子 {desc['top_ops']}")
    check("维度与清单声明一致（无 mismatch）",
          not desc["dimension_mismatch"],
          f"图 {desc['embedding_dim_effective']} vs 清单 {desc['embedding_dim_declared']}")
    check("归一化与插值方式显式声明（不靠猜）",
          desc["normalization"] in ("imagenet", "half", "unit", "none") and desc["resize_mode"],
          f"归一化={desc['normalization']} 插值={desc['resize_mode']} "
          f"线程={desc['intra_op_threads']}")

    dense, flat, moderate = make_tiles()

    # 确定性
    first = enc.encode_tiles([dense, flat])[0]
    second = enc.encode_tiles([dense, flat])[0]
    check("同输入两次推理完全一致（确定性）",
          float(np.abs(first - second).max()) == 0.0,
          f"最大差={float(np.abs(first - second).max())}")

    # 批处理等价
    tiles = [dense, flat, moderate, dense, flat]
    batched = enc.encode_tiles(tiles)
    singles = np.array([enc.encode_tiles([t])[0] for t in tiles])
    check("批处理结果与逐张推理等价",
          float(np.abs(batched - singles).max()) < 1e-6,
          f"最大差={float(np.abs(batched - singles).max()):.2e}")

    # L2 归一化
    norms = np.linalg.norm(batched, axis=1)
    check("输出已 L2 归一化", bool(np.allclose(norms, 1.0, atol=1e-4)),
          f"范数范围 {norms.min():.4f}—{norms.max():.4f}")

    # 内容敏感（不是恒等映射）
    cos_df = float(np.dot(batched[0], batched[1]))
    check("不同内容产生不同 embedding（核密 vs 均匀背景）",
          cos_df < 0.999 and float(np.abs(batched[0] - batched[1]).max()) > 1e-3,
          f"余弦={cos_df:.4f} 最大分量差={float(np.abs(batched[0] - batched[1]).max()):.4f}")
    check("相同内容复现同一 embedding（同图两次结果一致）",
          float(np.abs(batched[0] - batched[3]).max()) == 0.0)

    # 尺寸适配：输入图块尺寸与模型输入不一致时应自动缩放
    big = np.ascontiguousarray(np.repeat(np.repeat(dense, 2, axis=0), 2, axis=1))
    out_big = enc.encode_tiles([big])
    check("输入尺寸与模型不一致时自动缩放（256→128）",
          out_big.shape == (1, enc.embedding_dim),
          f"输入 {big.shape} → 输出 {out_big.shape}")

    # 空输入
    empty = enc.encode_tiles([])
    check("空输入返回 (0, dim) 而不抛异常", empty.shape == (0, enc.embedding_dim),
          f"shape={empty.shape}")

    # 吞吐
    t0 = time.time()
    enc.encode_tiles([dense] * 32)
    dt = time.time() - t0
    check("吞吐可测量（CPU 单进程）", dt < 30,
          f"32 图块 {dt:.2f}s ≈ {32 / max(dt, 1e-6):.0f} 图块/秒")

    # ---------------------------------------------------------- C. 降级路径
    print("\n[C] 降级与错误处理")

    class _FakeSpec:
        code = "fake-onnx"
        onnx_path = str(ROOT / "models" / "_not_exist.onnx")
        embedding_dim = 64
        tile_size = 128
        input_norm = "reinhard"
        input_norm_onnx = "half"
        input_layout = "NCHW"
        resize_mode = "bilinear"
        batch_size = 4

    with_fallback = OnnxTileEncoder(_FakeSpec(), fallback=None, warmup=False)
    check("权重文件不存在时标记为不可用",
          not with_fallback.is_real_model and "会话建立失败" in with_fallback.describe()["error"],
          with_fallback.describe()["error"][:70])
    try:
        with_fallback.encode_tiles([dense])
        check("无回退时抛 OnnxUnavailable（不静默用假数据）", False, "竟然没抛异常")
    except OnnxUnavailable as exc:
        check("无回退时抛 OnnxUnavailable（不静默用假数据）", True,
              str(exc)[:70])

    from app.services.encoder_service import SyntheticFeatureEncoder

    class _SpecLike:
        """给 fallback 用的最小 spec 桩。"""
        code = "fake-onnx"

    fb = SyntheticFeatureEncoder(encoder_service.require_spec("hibou-b-synth"))
    degraded = OnnxTileEncoder(_FakeSpec(), fallback=fb, warmup=False)
    degraded_out = degraded.encode_tiles([dense, flat])
    check("有回退时降级到内置实现并可用",
          not degraded.is_real_model and degraded_out.shape == (2, fb.embedding_dim),
          f"输出 {degraded_out.shape}，且 is_real_model=False 会被上层看到")

    # ---------------------------------------------------------- D. 流水线集成
    print("\n[D] 与流水线集成（真实编码器跑通 MIL）")
    from app.services.mil_service import GatedABMIL, MilConfig
    from app.services.wsi_readers import TiffPyramidReader
    from app.services.pipeline_service import DEFAULT_BAG_CONFIG, extract_bag

    sample = ROOT / "data" / "samples" / "sample_pyramid.ome.tif"
    if sample.exists():
        reader = TiffPyramidReader("ONNX-E2E", str(sample), base_mpp=0.5)
        bag = extract_bag(reader, DEFAULT_BAG_CONFIG)
        check("真实 TIFF 可抽取图块", len(bag["tiles"]) >= 10, f"{len(bag['tiles'])} 个")

        embeddings = enc.encode_tiles(bag["tiles"])
        check("真实编码器对真实图块产出 embedding",
              embeddings.shape == (len(bag["tiles"]), enc.embedding_dim),
              f"{embeddings.shape}")

        # 用真实 embedding 训练一个 MIL，验证链路端到端可用
        bags, labels = [], []
        for i in range(12):
            sub = bag["tiles"][i * 8:(i + 1) * 8] or bag["tiles"][:8]
            bags.append(enc.encode_tiles(sub))
            labels.append(1.0 if i % 2 == 0 else 0.0)
        model = GatedABMIL(MilConfig(in_dim=enc.embedding_dim, attn_dim=32,
                                     epochs=20, learning_rate=0.02, seed=3))
        summary = model.fit(bags, labels, bags[:4], labels[:4])
        check("真实 embedding 可驱动 ABMIL 训练",
              "final_train_auroc" in summary and summary["epochs_run"] > 0,
              f"训练 {summary['epochs_run']} 轮，train AUROC={summary['final_train_auroc']}")
        pred = model.predict(bags[0])
        check("训练后推理给出注意力权重与 top-k 热区",
              {"probability", "calibrated_probability", "attention",
               "top_indices", "max_attention"} <= set(pred),
              f"概率={pred['probability']:.4f} · 注意力 {len(pred['attention'])} 维 · "
              f"最大注意力={pred['max_attention']:.4f}")
        reader.close()
    else:
        print("  [skip] 缺少样例切片，先执行 scripts/make_sample_wsi.py")

    # 清理：把降级测试用的伪编码器从缓存里去掉
    encoder_service._instances.pop("fake-onnx", None)

    print("\n" + "=" * 78)
    print(f"  ONNX 推理与模型仓库：{PASS} 通过 / {FAIL} 失败")
    print("=" * 78)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
