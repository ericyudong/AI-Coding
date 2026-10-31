"""模型仓库：清单登记、安装、校验、卸载。

设计文档依据：第四章 4.2（开源基座可插拔）+ 第七章（许可证合规与权重溯源）。

要解决的问题是**权重治理**，而不是"下载一个文件"：
1. **溯源**：每个权重必须能回答「从哪来、什么许可、什么时候装的、装的哪一份」。
   注册申报阶段审核员会问「你们的模型基于什么权重」，答不出来就是硬伤。
2. **完整性**：权重文件必须校验 SHA256。没有校验，"装的是不是当时验证过的那一份"
   就无法证明；而 NMPA 审评关注可复现性。
3. **合规**：非商用权重（UNI2-h / Virchow2 / GigaPath 等）在 `product` 环境下
   **不允许安装到商用目录**。这一条要在安装阶段就拦住，而不是等推理时才报错。
4. **离线可用**：院内多为隔离网。安装必须支持"本地文件安装"（`--from`），
   不强制联网。

数据落在 `configs/model_registry.json`（清单）+ `models/`（权重文件）：
- 清单进版本库 → 权重的许可与校验和随代码一起被审计。
- 权重文件不进版本库（太大）→ 用 `.gitignore` 排除，靠 SHA256 保证一致。
"""

from __future__ import annotations

import hashlib
import json
import os
import logging
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import BASE_DIR, settings

logger = logging.getLogger(__name__)

CONFIG_DIR = BASE_DIR / "configs"
MANIFEST_PATH = CONFIG_DIR / "model_registry.json"
MODELS_DIR = BASE_DIR / "models"
COMMERCIAL_DIR = MODELS_DIR / "commercial"
RESEARCH_DIR = MODELS_DIR / "research"
REFERENCE_DIR = MODELS_DIR / "reference"


class ModelRegistryError(RuntimeError):
    pass


class LicenseDenied(ModelRegistryError):
    """许可门禁拦截。"""


@dataclass
class ModelEntry:
    """一条权重登记。字段与实际推理所需一一对应，不留"以后再补"的空洞。"""

    code: str
    name: str
    family: str
    arch: str
    embedding_dim: int
    tile_size: int
    target_mpp: float = 0.5
    params_m: float = 0.0

    license_code: str = ""
    license_name: str = ""
    commercial_usable: bool = False
    research_only: bool = False
    license_note: str = ""

    source_url: str = ""
    """权重来源地址。院内离线可留空，改用 --from 本地安装。"""
    sha256: str = ""
    """期望的权重文件 SHA256（小写十六进制）。安装与校验都以此为准。"""
    installed_path: str = ""
    """装好后的相对路径（相对项目根）。空 = 未安装。"""
    installed_sha256: str = ""
    installed_at: str = ""
    installed_by: str = ""
    bytes: int = 0

    input_norm: str = "half"
    """归一化预设：imagenet / half / unit / none。"""
    input_layout: str = "NCHW"
    resize_mode: str = "bilinear"
    batch_size: int = 16

    is_self_developed: bool = False
    """自研权重。自研即许可风险为零，是主线的长期目标。"""
    note: str = ""
    runtime: str = "onnx"
    """运行时。目前实现 onnx；torch 等留作扩展点。"""
    stage: str = "reference"
    """用途分级：reference=参照/验证用，candidate=候选主线，production=已定主线。"""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["absolute_path"] = str(weight_abspath(self)) if self.installed_path else ""
        data["exists"] = bool(self.installed_path and
                              Path(weight_abspath(self)).exists())
        return data

    @property
    def target_dir(self) -> Path:
        if self.is_self_developed or self.stage == "reference":
            return REFERENCE_DIR
        return COMMERCIAL_DIR if self.commercial_usable else RESEARCH_DIR


def weight_abspath(entry: ModelEntry) -> Path:
    return (BASE_DIR / entry.installed_path).resolve() if entry.installed_path else Path("")


# ================================================================= 清单读写
_DEFAULT_MANIFEST: dict[str, Any] = {
    "schema_version": 1,
    "updated_at": "",
    "note": ("模型权重清单。许可与校验和随代码一起被审计；权重文件本身不入版本库。"
             "安装：python scripts/model_registry.py install <code> [--from <file>]"),
    "models": [],
}


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, MODELS_DIR, COMMERCIAL_DIR, RESEARCH_DIR, REFERENCE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_manifest() -> dict:
    ensure_dirs()
    if not MANIFEST_PATH.exists():
        save_manifest(_DEFAULT_MANIFEST)
        return dict(_DEFAULT_MANIFEST)
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ModelRegistryError(f"清单解析失败（{MANIFEST_PATH}）：{exc}") from exc
    data.setdefault("models", [])
    return data


def save_manifest(data: dict) -> None:
    ensure_dirs()
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    MANIFEST_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def all_entries() -> list[ModelEntry]:
    entries: list[ModelEntry] = []
    for raw in load_manifest().get("models", []):
        known = {f for f in ModelEntry.__dataclass_fields__}
        entries.append(ModelEntry(**{k: v for k, v in raw.items() if k in known}))
    return entries


def get_entry(code: str) -> ModelEntry | None:
    for entry in all_entries():
        if entry.code == code:
            return entry
    return None


def upsert_entry(entry: ModelEntry) -> ModelEntry:
    data = load_manifest()
    models = [m for m in data.get("models", []) if m.get("code") != entry.code]
    models.append(entry.to_dict())
    data["models"] = models
    save_manifest(data)
    return entry


# ================================================================= 校验和
def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


# ================================================================= 许可门禁
def assert_license_allows_install(entry: ModelEntry, *, deployment_env: str,
                                  stage: str = "") -> None:
    """安装阶段的许可门禁。

    判定规则（这里写清楚，避免"看起来拦了其实没拦"）：
    - 目标是商用环境（deployment_env=product）；
    - 该权重不具备商用许可（commercial_usable=False 或 research_only=True）；
    - 且操作者**没有显式声明**这次安装是给科研/探索线用的（--stage research）
    → 拒绝安装。

    关键点在于第三条：**默认必须拦**。曾经写成"只有明确要装到商用目录才拦"，
    结果不传目标目录时 `wants_commercial` 恒为 False，product 环境下
    非商用权重一路放行 —— 门禁形同虚设，而且完全没有报错提示。
    默认拒绝 + 显式放行，才是合规门禁该有的方向。

    为什么要在**安装**时拦，而不是等推理时报错：
    推理时的报错发生在"业务正在跑"的时刻，运维的第一反应往往是关掉门禁让业务先过；
    而安装是明确的人工动作，此时说"不"最容易被接受，也最不会造成线上事故。
    """
    env = (deployment_env or settings.deployment_env or "research").lower()
    if env != "product":
        return
    if entry.commercial_usable and not entry.research_only:
        return
    # 只看**本次安装显式声明的 stage**，不看清单里已有的 stage。
    # 原因：清单里非商用条目的默认 stage 就是 "research"（表示它的定位），
    # 若拿它当放行依据，门禁就永远不触发 —— 那等于没有门禁。
    # 放行必须来自操作者这一次的明确表态（--stage research）。
    if (stage or "").lower() == "research":
        logger.warning(
            "允许在 product 环境安装非商用权重 %s，但已标记为 research（仅探索线，"
            "不得进入商用主线与注册申报材料）", entry.code,
        )
        return
    raise LicenseDenied(
        f"{entry.code} 的许可为「{entry.license_name}」，不可用于商用环境"
        f"（deployment_env=product）。\n"
        f"  · 可选做法一：显式声明本次仅供探索线使用：\n"
        f"      python scripts/model_registry.py install {entry.code} "
        f"--from <文件> --stage research\n"
        f"  · 可选做法二：改用可商用权重（如 Apache-2.0 的 Hibou 系列，或自研权重）。\n"
        f"  · 直接拿它做申报 NMPA 三类证的产品，会在注册环节被驳回。"
    )


# ================================================================= 安装 / 卸载
def install_entry(code: str, *, source: str = "", deployment_env: str = "",
                  stage: str = "", actor: str = "", expect_sha256: str = "",
                  allow_license_override: bool = False) -> ModelEntry:
    """安装权重。

    `source`：本地文件路径（院内离线安装的推荐方式）。
    为空时若清单里登记了 `source_url`，则下载 —— 但**下载不作为唯一路径**，
    因为院内环境通常没有外网。
    """
    entry = get_entry(code)
    if entry is None:
        raise ModelRegistryError(f"清单中没有编码器 {code}。可用：{', '.join(e.code for e in all_entries())}")

    if not allow_license_override:
        assert_license_allows_install(entry, deployment_env=deployment_env, stage=stage)

    ensure_dirs()
    # 目录选择在门禁之后、复制之前确定；显式 stage 会改变落地目录
    if stage:
        entry.stage = stage
    target_dir = entry.target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(entry.installed_path).name if entry.installed_path else f"{code}.onnx"
    target = target_dir / filename

    # **先落到临时文件并校验，再原子替换**。
    # 直接覆盖 target 再校验，一旦校验失败就必须删除 target —— 那会把
    # 之前装好的、经过验证的权重一起删掉（真实数据丢失，且现场无从恢复）。
    incoming = target.with_suffix(target.suffix + ".incoming")
    incoming.unlink(missing_ok=True)

    try:
        if source:
            src = Path(source)
            if not src.exists():
                raise ModelRegistryError(f"源文件不存在：{src}")
            if src.resolve() == target.resolve():
                # 原地重装：先复制一份再校验，避免"校验失败即丢失原文件"
                shutil.copy2(src, incoming)
            else:
                shutil.copy2(src, incoming)
        elif entry.installed_path and Path(weight_abspath(entry)).exists():
            logger.info("%s 已存在于 %s，跳过复制", code, entry.installed_path)
            entry.installed_sha256 = entry.installed_sha256 or sha256_file(
                Path(weight_abspath(entry)))
            entry.bytes = Path(weight_abspath(entry)).stat().st_size
            if not entry.sha256:
                entry.sha256 = entry.installed_sha256
            upsert_entry(entry)
            return entry
        elif entry.source_url:
            _download(entry.source_url, incoming)
        else:
            raise ModelRegistryError(
                f"{code} 没有可用的安装来源。\n"
                f"  · 院内离线：python scripts/model_registry.py install {code} "
                f"--from <权重文件>\n"
                f"  · 或先在清单里补 source_url"
            )

        # 完整性校验（在临时文件上做，不碰已装好的那一份）
        actual = sha256_file(incoming)
        expected = (expect_sha256 or entry.sha256 or "").strip().lower()
        if expected and expected != actual:
            raise ModelRegistryError(
                f"{code} 权重校验失败，已丢弃本次文件（**原有安装未受影响**）。\n"
                f"  期望 SHA256：{expected}\n"
                f"  实际 SHA256：{actual}\n"
                f"  这通常意味着文件损坏、下载被劫持，或清单与权重不是同一版本。"
            )

        # 校验通过：原子替换（同目录 rename 在 Windows/POSIX 上都是原子的）
        os.replace(incoming, target)
    finally:
        incoming.unlink(missing_ok=True)

    entry.installed_path = str(target.relative_to(BASE_DIR)).replace("\\", "/")
    entry.installed_sha256 = actual
    entry.bytes = target.stat().st_size
    entry.installed_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    entry.installed_by = actor or f"pid={__import__('os').getpid()}"
    if not entry.sha256:
        entry.sha256 = actual
    if entry.source_url:
        entry.runtime = entry.runtime or "onnx"
    upsert_entry(entry)
    logger.info("已安装 %s（%s，%.1f MB，sha256=%s…）", code, entry.installed_path,
                entry.bytes / 1024 / 1024, actual[:12])
    return entry


def _download(url: str, target: Path) -> None:
    """下载权重。用标准库，避免为一次下载引入额外依赖。

    院内多为隔离网，下载失败是**常态而非异常**，因此这里把网络错误统一包装成
    ModelRegistryError 并给出离线安装的替代做法 —— 否则运维拿到的是一串
    SSL/Traceback，看不出"其实只要把文件拷进来就行"。
    """
    import urllib.error
    import urllib.request

    logger.info("下载权重：%s → %s", url, target)
    request = urllib.request.Request(url, headers={"User-Agent": "SmartHealth/1.1"})
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=120) as response, open(target, "wb") as out:
            shutil.copyfileobj(response, out, length=1 << 20)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        target.unlink(missing_ok=True)
        raise ModelRegistryError(
            f"下载权重失败（{type(exc).__name__}: {str(exc)[:120]}）。\n"
            f"  院内环境通常无法访问外网，这不是故障。请改用离线安装：\n"
            f"    1) 在有网机器上取到权重文件；\n"
            f"    2) 拷到本机；\n"
            f"    3) python scripts/model_registry.py install <code> --from <权重文件路径>"
        ) from exc
    logger.info("下载完成：%.1f MB，耗时 %.1fs",
                target.stat().st_size / 1024 / 1024, time.time() - started)


def uninstall_entry(code: str, *, keep_manifest: bool = True) -> dict:
    entry = get_entry(code)
    if entry is None:
        raise ModelRegistryError(f"清单中没有编码器 {code}")
    removed = ""
    if entry.installed_path:
        path = Path(weight_abspath(entry))
        if path.exists():
            removed = str(path)
            path.unlink()
    entry.installed_path = ""
    entry.installed_sha256 = ""
    entry.installed_at = ""
    entry.bytes = 0
    if keep_manifest:
        upsert_entry(entry)
    return {"code": code, "removed_file": removed}


# ================================================================= 校验
def verify_entry(code: str) -> dict:
    """校验一条权重：文件存在、SHA256 匹配、能被解析为有效 ONNX、维度与声明一致。"""
    entry = get_entry(code)
    if entry is None:
        return {"code": code, "ok": False, "stage": "lookup",
                "error": f"清单中没有编码器 {code}"}

    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("清单登记许可", bool(entry.license_code and entry.license_name),
        f"{entry.license_code} / {entry.license_name} / 可商用={entry.commercial_usable}")

    if not entry.installed_path:
        add("权重文件已安装", False, "installed_path 为空，请先 install")
        return {"code": code, "ok": False, "stage": "installed", "checks": checks,
                "error": "未安装权重"}

    path = Path(weight_abspath(entry))
    add("权重文件存在", path.exists(), str(path))
    if not path.exists():
        return {"code": code, "ok": False, "stage": "exists", "checks": checks,
                "error": f"文件缺失：{path}"}

    size_mb = path.stat().st_size / 1024 / 1024
    add("文件非空", path.stat().st_size > 0, f"{size_mb:.2f} MB")

    actual = sha256_file(path)
    if entry.installed_sha256:
        add("已安装副本 SHA256 与记录一致", actual == entry.installed_sha256,
            f"{actual[:16]}… vs 记录 {entry.installed_sha256[:16]}…")
    if entry.sha256:
        add("SHA256 与清单期望值一致", actual == entry.sha256.lower(),
            f"{actual[:16]}… vs 清单 {entry.sha256[:16]}…")
    else:
        add("清单已登记 SHA256", False, "清单缺 sha256：无法证明权重未被替换")
        entry.sha256 = actual
        upsert_entry(entry)

    # ONNX 结构校验（真正解析计算图，不只是存在性）
    try:
        import onnx

        model = onnx.load(str(path))
        onnx.checker.check_model(model)
        graph = model.graph
        inputs = list(graph.input)
        outputs = list(graph.output)
        op_counts: dict[str, int] = {}
        for node in graph.node:
            op_counts[node.op_type] = op_counts.get(node.op_type, 0) + 1
        add("ONNX 结构合法（checker 通过）", True,
            f"{len(graph.node)} 个节点，{len(graph.initializer)} 个权重张量")
        add("模型有输入输出", bool(inputs) and bool(outputs),
            f"输入 {[i.name for i in inputs][:2]}，输出 {[o.name for o in outputs][:2]}")
        add("含真实算子（非恒等映射）", len(op_counts) >= 2,
            f"算子：{sorted(op_counts.items(), key=lambda kv: -kv[1])[:5]}")
    except ImportError:
        add("onnx 库可用", False, "未安装 onnx，无法做结构校验：pip install onnx")
    except Exception as exc:
        add("ONNX 结构合法（checker 通过）", False, f"{type(exc).__name__}: {exc}")

    # 用 onnxruntime 实际跑一次，验证维度声明是否与图一致
    try:
        import onnxruntime as ort

        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        inp, out = session.get_inputs()[0], session.get_outputs()[0]
        add("onnxruntime 可建立会话", True,
            f"输入 {inp.name} {inp.shape}，输出 {out.name} {out.shape}")

        shape = list(inp.shape)
        if len(shape) == 4:
            layout = entry.input_layout or ("NCHW" if shape[1] in (1, 3, 4) else "NHWC")
            declared_h = shape[2] if layout == "NCHW" else shape[1]
            add("输入尺寸与清单一致",
                not isinstance(declared_h, int) or declared_h == entry.tile_size,
                f"图={declared_h} 清单={entry.tile_size}")
        out_dim = out.shape[-1] if out.shape else None
        add("输出维度与清单一致",
            not isinstance(out_dim, int) or out_dim == entry.embedding_dim,
            f"图={out_dim} 清单={entry.embedding_dim}")
        if isinstance(out_dim, int) and out_dim != entry.embedding_dim:
            add("清单维度已按图修正", True,
                f"{entry.embedding_dim} → {out_dim}（以计算图为准）")
            entry.embedding_dim = int(out_dim)
            upsert_entry(entry)
    except ImportError:
        add("onnxruntime 可用", False, "未安装 onnxruntime：pip install onnxruntime")
    except Exception as exc:
        add("onnxruntime 可建立会话", False, f"{type(exc).__name__}: {exc}")

    ok = all(c["ok"] for c in checks)
    return {"code": code, "ok": ok, "stage": "complete", "checks": checks,
            "path": str(path), "bytes": path.stat().st_size,
            "sha256": actual}


def verify_all() -> dict:
    """校验所有**已安装**的权重。

    语义边界（必须明确，否则门禁会自相矛盾）：
    - 「装了哪些」是**覆盖率**问题，由 doctor 的「模型权重清单」检查负责报告
      （它会给出 n/total 已安装的可视化并按部署环境分级提示）；
    - 这里只对**在用的**权重做完整性校验（存在、SHA256、ONNX 结构、维度）。
      未安装的登记项是预期状态 —— CI 的 release 档在 export-reference 之后只有
      1 份已装权重，其余外部/自研权重本就不在 CI 环境里，不应当拦门禁。
      （旧实现把未安装也判 FAIL，与 doctor 的判定直接矛盾：doctor 说
      「1/9 已安装」是 OK，verify --all 却 FAIL —— 第一次跑 release 门禁时暴露。）
    """
    entries = all_entries()
    skipped = [e.code for e in entries if not e.installed_path]
    results = [verify_entry(e.code) for e in entries if e.installed_path]
    return {"total": len(entries), "ok": sum(1 for r in results if r["ok"]),
            "failed": [r["code"] for r in results if not r["ok"]],
            "skipped": skipped, "results": results}


# ================================================================= 参照模型导出
def export_reference_model(*, code: str = "sh-ref-cnn-v1",
                           embedding_dim: int = 256, tile_size: int = 128,
                           seed: int = 20261030, channels: tuple[int, ...] = (32, 64, 128),
                           dynamic_batch: bool = True,
                           out_path: str | Path | None = None) -> dict:
    """导出一个**真实的 ONNX 卷积编码器**（自研参照模型）。

    用途与边界（必须说清楚，否则就是误导）：
    - 它是一张**真实**的 ONNX 计算图：卷积、激活、全局池化、全连接都是真的算子，
      权重是真实张量，onnxruntime 会真正执行它们；输出随输入图像内容变化。
    - 它**不是**病理预训练权重：这些卷积核没有在病理数据上训练过，
      因此其 embedding 不具备病理语义判别力，不能拿它的指标当模型性能。
    - 它的作用是**验证并锁定推理链路**：预处理（归一化/布局插值）、批处理、
      维度校验、SHA256 治理、许可门禁、以及"换权重即可升级"的可插拔性。
      真实权重到位后，替换文件 + 更新清单 SHA256 即可，不需要改一行推理代码。
    """
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    out_dir = REFERENCE_DIR if out_path is None else Path(out_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    target = Path(out_path) if out_path is not None else (REFERENCE_DIR / f"{code}.onnx")

    rng = np.random.default_rng(seed)
    batch_dim = "N" if dynamic_batch else 1

    inputs = [helper.make_tensor_value_info("input", TensorProto.FLOAT,
                                            [batch_dim, 3, tile_size, tile_size])]
    outputs = [helper.make_tensor_value_info("embedding", TensorProto.FLOAT,
                                             [batch_dim, embedding_dim])]

    nodes: list = []
    initializers: list = []
    current = "input"
    prev_ch = 3
    spatial = tile_size

    for index, out_ch in enumerate(channels):
        name = f"conv{index + 1}"
        # He 初始化：方差按 fan_in 缩放，让激活值在深层保持同量级
        scale = float(np.sqrt(2.0 / (prev_ch * 9)))
        weight = rng.normal(0.0, scale, (out_ch, prev_ch, 3, 3)).astype(np.float32)
        bias = np.zeros(out_ch, dtype=np.float32)
        initializers.append(numpy_helper.from_array(weight, f"{name}_w"))
        initializers.append(numpy_helper.from_array(bias, f"{name}_b"))
        nodes.append(helper.make_node("Conv", [current, f"{name}_w", f"{name}_b"],
                                      [f"{name}_out"], name=name,
                                      kernel_shape=[3, 3], strides=[2, 2], pads=[1, 1, 1, 1]))
        nodes.append(helper.make_node("Relu", [f"{name}_out"], [f"{name}_act"], name=f"{name}_relu"))
        current = f"{name}_act"
        prev_ch = out_ch
        spatial = max(1, spatial // 2)

    nodes.append(helper.make_node("GlobalAveragePool", [current], ["pooled"], name="gap"))
    nodes.append(helper.make_node("Flatten", ["pooled"], ["flat"], name="flatten", axis=1))
    # Gemm(transB=1) 的语义是 Y = A · Bᵀ + b，因此当 A 是 (N, prev_ch)、
    # 目标是 (N, embedding_dim) 时，B 必须是 (embedding_dim, prev_ch)。
    # 写成 (prev_ch, embedding_dim) 会让 onnx.checker 通过、但 onnxruntime 在
    # 建会话时报维度不匹配 —— 这也是 verify 必须真的建一次会话的原因。
    head_scale = float(np.sqrt(2.0 / max(prev_ch, 1)))
    head_w = rng.normal(0.0, head_scale, (embedding_dim, prev_ch)).astype(np.float32)
    head_b = np.zeros(embedding_dim, dtype=np.float32)
    initializers.append(numpy_helper.from_array(head_w, "head_w"))
    initializers.append(numpy_helper.from_array(head_b, "head_b"))
    nodes.append(helper.make_node("Gemm", ["flat", "head_w", "head_b"], ["embedding"],
                                  name="head", alpha=1.0, beta=1.0, transB=1))

    graph = helper.make_graph(nodes, f"SmartHealthReference_{code}", inputs, outputs, initializers)
    model = helper.make_model(
        graph,
        producer_name="SmartHealth",
        doc_string=("自研参照编码器：用于验证 ONNX 推理链路与权重治理，"
                    "非病理预训练权重，其指标不代表模型性能。"),
        opset_imports=[helper.make_opsetid("", 17)],
    )
    model.ir_version = 9
    onnx.checker.check_model(model)
    onnx.save(model, str(target))

    digest = sha256_file(target)
    param_count = int(sum(int(np.prod(numpy_helper.to_array(t).shape)) for t in initializers))
    return {
        "code": code, "path": str(target.relative_to(BASE_DIR)).replace("\\", "/"),
        "absolute_path": str(target), "bytes": target.stat().st_size,
        "sha256": digest, "embedding_dim": embedding_dim, "tile_size": tile_size,
        "params": param_count,
        "params_m": round(param_count / 1e6, 4),
        "nodes": len(nodes), "dynamic_batch": dynamic_batch,
        "channels": list(channels), "downsample_factor": 2 ** len(channels),
        "feature_map_at_input": spatial,
    }


def register_reference(code: str = "sh-ref-cnn-v1", *, embedding_dim: int = 256,
                       tile_size: int = 128, seed: int = 20261030) -> ModelEntry:
    """导出自研参照模型并登记进清单（一步到位，供 CLI 与自测共用）。"""
    result = export_reference_model(code=code, embedding_dim=embedding_dim,
                                    tile_size=tile_size, seed=seed)
    entry = get_entry(code) or ModelEntry(
        code=code, name="自研参照编码器（ONNX 链路验证）", family="SmartHealth",
        arch=f"CNN-{result['channels']}", embedding_dim=embedding_dim,
        tile_size=tile_size, target_mpp=0.5, params_m=result["params_m"],
        license_code="Proprietary", license_name="公司自有知识产权",
        commercial_usable=True, research_only=False,
        license_note="自研产出，许可风险为零；用于验证 ONNX 推理链路与权重治理。",
        input_norm="imagenet", input_layout="NCHW", resize_mode="bilinear",
        batch_size=16, is_self_developed=True, runtime="onnx", stage="reference",
        note=("自研参照模型：真实 ONNX 计算图与真实张量，但未经病理数据训练，"
              "指标不代表模型性能。真实权重到位后替换文件并更新 sha256 即可。"),
    )
    entry.installed_path = result["path"]
    entry.installed_sha256 = result["sha256"]
    entry.sha256 = result["sha256"]
    entry.bytes = result["bytes"]
    entry.installed_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    entry.installed_by = "export_reference_model"
    entry.embedding_dim = embedding_dim
    entry.tile_size = tile_size
    upsert_entry(entry)
    return entry


# ================================================================= 概览
def registry_overview() -> dict:
    entries = all_entries()
    return {
        "manifest_path": str(MANIFEST_PATH.relative_to(BASE_DIR)).replace("\\", "/"),
        "models_dir": str(MODELS_DIR.relative_to(BASE_DIR)).replace("\\", "/"),
        "total": len(entries),
        "installed": sum(1 for e in entries if e.installed_path and Path(weight_abspath(e)).exists()),
        "commercial_ready": sum(1 for e in entries
                                if e.commercial_usable and e.installed_path
                                and Path(weight_abspath(e)).exists()),
        "self_developed": sum(1 for e in entries if e.is_self_developed),
        "by_stage": _count_by(entries, "stage"),
        "by_license": _count_by(entries, "license_code"),
        "models": [e.to_dict() for e in entries],
        "env": settings.deployment_env,
    }


def _count_by(entries: list[ModelEntry], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        key = str(getattr(entry, attr, "") or "（未标注）")
        counts[key] = counts.get(key, 0) + 1
    return counts


def seeded_default_manifest() -> int:
    """把内置编码器声明同步进清单（标记为 reference / 未安装）。

    只补"清单里还没有"的条目，不覆盖已有记录 —— 否则会把已安装的记录清掉。
    """
    from app.services.encoder_service import BUILTIN_ENCODERS

    existing = {e.code for e in all_entries()}
    added = 0
    for spec in BUILTIN_ENCODERS:
        if spec.code in existing:
            continue
        upsert_entry(ModelEntry(
            code=spec.code, name=spec.name, family=spec.family, arch=spec.arch,
            embedding_dim=spec.embedding_dim, tile_size=spec.tile_size,
            target_mpp=spec.target_mpp, params_m=spec.params_m,
            license_code=spec.license_code, license_name=spec.license_name,
            commercial_usable=spec.commercial_usable, research_only=spec.research_only,
            license_note=spec.license_note, source_url=spec.source_url,
            input_norm=spec.input_norm_onnx or "half", input_layout=spec.input_layout or "NCHW",
            resize_mode=spec.resize_mode or "bilinear", batch_size=spec.batch_size or 16,
            is_self_developed=spec.is_self_developed, runtime="onnx",
            stage="candidate" if spec.commercial_usable else "research",
            note="由内置注册表同步；未安装权重，当前以合成实现提供占位能力。",
        ))
        added += 1
    return added
