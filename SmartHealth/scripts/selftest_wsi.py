"""真实 WSI 读取链路自测。

验证的是**真实文件到像素**的完整链路，而不是合成兜底：
1. 格式探测：魔数优先于后缀，能识别 tiled/striped/vendor 特征。
2. 金字塔解析：层级数、每层尺寸、从 OME 元数据提取 mpp。
3. **像素正确性**：区域读取的结果必须与文件里真实的像素一致（逐像素比对源图像）。
4. **不整层加载**：读一个 128×128 图块后，缓存占用必须远小于 L0 整层大小 ——
   把"我们真的做了分块读取"变成可测量的事实，而不是口头承诺。
5. 条带（striped）路径与单图（pillow）路径各自可用。
6. `open_slide` 工厂按格式正确分派。
7. 真实文件能走通流水线（图块抽取 + 特征提取），特征量与合成切片同量级。

    python scripts/selftest_wsi.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SAMPLES = ROOT / "data" / "samples"
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


def main() -> int:
    import tifffile

    from app.services.image_utils import color_deconvolve, tile_features, tissue_ratio
    from app.services.wsi_readers import (
        SingleImageReader,
        TiffPyramidReader,
        backend_capabilities,
        sniff_slide_format,
    )
    from app.services.wsi_service import open_slide, slide_reader_info

    print("=" * 78)
    print("  真实 WSI 读取链路自测")
    print("=" * 78)

    caps = backend_capabilities()
    print(f"\n[0] 读取后端：openslide={caps['openslide']} tifffile={caps['tifffile']} "
          f"pillow={caps['pillow']} imagecodecs={caps['imagecodecs']}")

    tiled_path = SAMPLES / "sample_pyramid.ome.tif"
    striped_path = SAMPLES / "sample_striped.tif"
    single_path = SAMPLES / "sample_single.png"
    if not tiled_path.exists():
        print("  [FAIL] 缺少样例文件，请先执行：")
        print("         python scripts/make_sample_wsi.py --size 4096 --levels 4")
        return 1

    # ---------------------------------------------------------- 1. 格式探测
    print("\n[1] 格式探测（魔数优先）")
    info_tiled = sniff_slide_format(tiled_path)
    check("tiled TIFF 被识别为 TIFF 容器",
          info_tiled.container == "tiff" and info_tiled.is_tiff,
          f"container={info_tiled.container} backend={info_tiled.backend} "
          f"magic={info_tiled.magic[:8]}…")
    check("选择的后端可用（tifffile 或 openslide）",
          info_tiled.backend in ("tifffile", "openslide"),
          f"backend={info_tiled.backend}")

    # 后缀伪装：把 tiled 复制成 .svs 后缀，探测应仍按魔数走 TIFF 路径
    fake = SAMPLES / "_disguised.svs"
    fake.write_bytes(tiled_path.read_bytes()[:4096])   # 只取头部即可验证魔数判定
    info_fake = sniff_slide_format(fake)
    check("后缀伪装（.svs）仍按魔数判定为 TIFF 链路",
          info_fake.is_tiff and info_fake.backend in ("tifffile", "openslide"),
          f"vendor={info_fake.vendor} backend={info_fake.backend}")
    fake.unlink(missing_ok=True)

    if single_path.exists():
        info_png = sniff_slide_format(single_path)
        check("PNG 走 pillow 后端",
              info_png.container == "image" and info_png.backend == "pillow",
              f"backend={info_png.backend}")

    # ---------------------------------------------------------- 2. 金字塔解析
    print("\n[2] 金字塔解析（真实 TIFF 层级）")
    t0 = time.time()
    reader = TiffPyramidReader("WSI-TILED", str(tiled_path), base_mpp=0.5)
    open_ms = (time.time() - t0) * 1000
    levels = reader.levels
    check("解析出多层级（≥3）", len(levels) >= 3,
          f"{len(levels)} 层：{[lv.width for lv in levels]}")
    check("层级尺寸逐级减半",
          all(levels[i].width == levels[i - 1].width // 2 for i in range(1, len(levels))),
          " / ".join(str(lv.width) for lv in levels))
    check("从 OME 元数据提取到 mpp（未退化为传入值）",
          abs(reader.base_mpp - 0.5) > 1e-6 and 0.2 < reader.base_mpp < 1.5,
          f"base_mpp={reader.base_mpp:.4f}（传入 0.5，说明读到了文件元数据）")
    check("打开耗时可接受（未整层解码）", open_ms < 3000,
          f"{open_ms:.0f} ms")

    # ---------------------------------------------------------- 3. 像素正确性
    print("\n[3] 像素正确性（与文件真实内容逐像素比对）")
    with tifffile.TiffFile(tiled_path) as tif:
        truth_l0 = tif.series[0].levels[0].asarray()
        truth_l1 = tif.series[0].levels[1].asarray()

    # L0：跨 tile 边界的区域（最容易在分块读里出错）
    region = reader.read_region(0, 300, 300, 256, 256)
    expected = truth_l0[300:556, 300:556]
    diff = int(np.abs(region.astype(np.int16) - expected.astype(np.int16)).max())
    check("L0 跨分块边界区域读取逐像素一致", diff == 0,
          f"最大像素差={diff}，区域 300,300 起 256×256（跨越 tile 边界）")

    # L0 角点对齐（恰好在 tile 起点）
    region2 = reader.read_region(0, 256, 512, 128, 128)
    expected2 = truth_l0[512:640, 256:384]
    diff2 = int(np.abs(region2.astype(np.int16) - expected2.astype(np.int16)).max())
    check("L0 tile 对齐区域一致", diff2 == 0, f"最大像素差={diff2}")

    # L1 层级
    region3 = reader.read_region(1, 100, 100, 128, 128)
    expected3 = truth_l1[100:228, 100:228]
    diff3 = int(np.abs(region3.astype(np.int16) - expected3.astype(np.int16)).max())
    check("L1 层级区域读取一致", diff3 == 0, f"最大像素差={diff3}")

    # 越界读取应补白且不崩
    edge = reader.read_region(0, levels[0].width - 40, levels[0].height - 40, 128, 128)
    check("越界区域读取返回正确尺寸并补白（不崩溃）",
          edge.shape == (128, 128, 3), f"shape={edge.shape}")

    # ---------------------------------------------------------- 4. 不整层加载
    print("\n[4] 分块读取验证（内存不随切片尺寸增长）")
    l0_bytes = int(np.prod(truth_l0.shape[:2]) * truth_l0.shape[2])
    cache = reader.cache_stats()
    check("读取若干图块后缓存占用远小于 L0 整层",
          cache["bytes"] < l0_bytes / 4,
          f"缓存 {cache['bytes'] / 1024:.0f} KB vs L0 整层 {l0_bytes / 1024 / 1024:.0f} MB"
          f"（{cache['bytes'] / max(l0_bytes, 1) * 100:.2f}%）")

    # 连续读取大量分散图块，缓存应被有界剔换而不是无限增长
    for i in range(120):
        x = (i * 337) % max(1, levels[0].width - 200)
        y = (i * 613) % max(1, levels[0].height - 200)
        reader.read_region(0, x, y, 128, 128)
    cache2 = reader.cache_stats()
    check("连续读取 120 个图块后缓存仍有界（LRU 剔换生效）",
          cache2["bytes"] <= cache2["budget"],
          f"缓存 {cache2['bytes'] / 1024 / 1024:.1f} MB ≤ 上限 "
          f"{cache2['budget'] / 1024 / 1024:.0f} MB，条目 {cache2['entries']}")

    # 耗时：单图块读取应该是毫秒级
    t0 = time.time()
    for _ in range(20):
        reader.read_region(0, 1024, 1024, 128, 128)
    per_tile_ms = (time.time() - t0) / 20 * 1000
    check("单图块读取为毫秒级（缓存命中后）", per_tile_ms < 60,
          f"{per_tile_ms:.1f} ms/图块")

    # ---------------------------------------------------------- 5. 条带路径
    print("\n[5] 条带（striped）TIFF 路径")
    if striped_path.exists():
        with tifffile.TiffFile(striped_path) as tif:
            page0 = tif.pages[0]
            is_tiled = bool(getattr(page0, "is_tiled", False))
            truth_s = tif.series[0].levels[0].asarray()
        check("条纹文件确认非 tiled（走条带分支）", not is_tiled,
              f"is_tiled={is_tiled} rowsperstrip={getattr(page0, 'rowsperstrip', '?')}")
        s_reader = TiffPyramidReader("WSI-STRIPED", str(striped_path), base_mpp=0.5)
        got = s_reader.read_region(0, 200, 200, 128, 128)
        exp = truth_s[200:328, 200:328]
        d = int(np.abs(got.astype(np.int16) - exp.astype(np.int16)).max())
        check("条带路径区域读取逐像素一致", d == 0, f"最大像素差={d}")
    else:
        print("  [skip] 未生成 striped 样例")

    # ---------------------------------------------------------- 6. 单图路径
    print("\n[6] 单图（pillow）路径")
    if single_path.exists():
        p_reader = SingleImageReader("WSI-PNG", str(single_path), base_mpp=0.25)
        check("单图构建出真实降采样金字塔", len(p_reader.levels) >= 3,
              f"{len(p_reader.levels)} 层：{[lv.width for lv in p_reader.levels]}")
        patch = p_reader.read_region(1, 64, 64, 128, 128)
        check("单图区域读取尺寸正确", patch.shape == (128, 128, 3), f"shape={patch.shape}")

    # ---------------------------------------------------------- 7. 工厂分派
    print("\n[7] open_slide 工厂分派")
    r1 = open_slide({"code": "F-TIF", "file_path": str(tiled_path), "mpp": 0.5})
    check("工厂对金字塔 TIFF 返回真实读取器",
          isinstance(r1, TiffPyramidReader), f"{type(r1).__name__}（非合成兜底）")
    check("工厂读取器层级来自文件", len(r1.levels) >= 3,
          f"{len(r1.levels)} 层，L0={r1.levels[0].width}px")

    r2 = open_slide({"code": "F-SYN", "has_lesion": True})
    check("无 file_path 时回退合成读取器（演示兜底仍可用）",
          type(r2).__name__ == "SyntheticWSIReader", f"{type(r2).__name__}")

    self_desc = slide_reader_info({"code": "F-TIF", "file_path": str(tiled_path)})
    check("切片自述能说明真实来源与后端",
          self_desc["source"] == "file" and self_desc["backend"] in ("tifffile", "openslide"),
          f"source={self_desc['source']} backend={self_desc['backend']} "
          f"bytes={self_desc['bytes']}")

    # ---------------------------------------------------------- 8. 真实文件走通流水线
    print("\n[8] 真实文件走通特征流水线")
    from app.services.pipeline_service import DEFAULT_BAG_CONFIG, extract_bag

    bag = extract_bag(r1, DEFAULT_BAG_CONFIG)
    check("从真实 TIFF 抽取到足够图块", len(bag["tiles"]) >= 10,
          f"{len(bag['tiles'])} 个组织图块（min_tissue_ratio="
          f"{DEFAULT_BAG_CONFIG.min_tissue_ratio}）")

    if bag["tiles"]:
        feats = np.array([tile_features(t) for t in bag["tiles"]])
        check("特征维度与合成切片一致（67 维）", feats.shape[1] == 67,
              f"shape={feats.shape}")
        ratios = [tissue_ratio(t) for t in bag["tiles"]]
        check("组织覆盖率分布合理", 0.0 < float(np.mean(ratios)) <= 1.0,
              f"平均组织占比 {np.mean(ratios):.3f}，范围 "
              f"{min(ratios):.3f}—{max(ratios):.3f}")
        # 颜色去卷积应给出非零苏木素浓度（真实 H&E 光谱）
        h, e, _ = color_deconvolve(bag["tiles"][0])
        check("颜色去卷积在真实文件上给出非零苏木素浓度",
              float(h.mean()) > 0.0,
              f"H 均值={h.mean():.4f} E 均值={e.mean():.4f}")

    # 病灶区（右上角）的核密度应高于非病灶区。
    # 注意坐标空间：图块坐标是**抽取层级**的坐标，必须换算到该层尺寸再判定位。
    coords = bag["coords"]
    bag_level = DEFAULT_BAG_CONFIG.level
    level_w = r1.levels[bag_level].width
    level_h = r1.levels[bag_level].height
    in_lesion, out_lesion = [], []
    for (lvl, x, y), tile in zip(coords, bag["tiles"]):
        f = tile_features(tile)
        is_lesion = x > level_w * 0.6 and y < level_h * 0.4
        (in_lesion if is_lesion else out_lesion).append(f[6])
    if in_lesion and out_lesion:
        check("真实文件中病灶区核密度高于非病灶区（信号可学）",
              float(np.mean(in_lesion)) > float(np.mean(out_lesion)),
              f"病灶区核占比 {np.mean(in_lesion):.4f} vs "
              f"非病灶区 {np.mean(out_lesion):.4f}")
    else:
        print(f"  [skip] 图块未覆盖病灶区（lesion={len(in_lesion)} other={len(out_lesion)}）")

    reader.close()
    if "s_reader" in dir():
        s_reader.close()

    print("\n" + "=" * 78)
    print(f"  真实 WSI 读取链路：{PASS} 通过 / {FAIL} 失败")
    print("=" * 78)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
