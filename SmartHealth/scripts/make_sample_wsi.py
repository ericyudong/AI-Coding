"""生成**真实**金字塔切片样例文件，用于端到端验证真实读取链路。

    python scripts/make_sample_wsi.py                       # 默认输出到 data/samples/
    python scripts/make_sample_wsi.py --size 8192 --levels 5
    python scripts/make_sample_wsi.py --pattern tiled       # tiled TIFF（推荐）
    python scripts/make_sample_wsi.py --pattern striped     # striped TIFF
    python scripts/make_sample_wsi.py --pattern single      # 单张 PNG

产出：
    data/samples/sample_pyramid.ome.tif   —— 多分辨率 tiled OME-TIFF（含 mpp 元数据）
    data/samples/sample_striped.tif       —— 多分辨率 striped TIFF
    data/samples/sample_single.png        —— 单张位图（走 Pillow 后端）

**为什么这不是"假数据"**：
生成的是**真正符合 TIFF/OME 规范的多分辨率金字塔文件**：tiled 存储、subifds 分级、
LZW 压缩、`PhysicalSizeX` 物理尺寸元数据。文件本身可以用任何标准工具（ImageJ /
QuPath / tifffile）打开并读出相同的层级与像素。它验证的是**文件格式解析、
分块区域读取、元数据提取、缓存边界**这条真实链路 —— 而不是绕过它。

诚实的边界：图像内容仍由程序化合成（H&E 光谱 + 细胞核密度差异），
不是真实患者的切片扫描件。要接入真实切片，把 `Slide.file_path` 指向院内切片即可。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def build_he_pyramid(size: int, levels: int, seed: int = 20261030) -> list[np.ndarray]:
    """构造 H&E 外观的多分辨率图像栈（每层是上一层的一半边长）。

    与合成切片读取器保持一致的光谱约定，便于把"真实文件路径"与"合成路径"
    的算法输出直接对比：颜色去卷积、核密度特征都应落在同一量级。
    """
    rng = np.random.default_rng(seed)
    # ---- L0：组织背景 + 细胞核（苏木素嗜碱）+ 部分病灶区（核密度更高）
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    field = np.zeros((size, size), dtype=np.float32)
    for _ in range(3):
        cx, cy = rng.uniform(0.25, 0.75, 2) * size
        sx, sy = rng.uniform(0.18, 0.30, 2) * size
        field += np.exp(-(((xx - cx) ** 2) / (2 * sx ** 2) + ((yy - cy) ** 2) / (2 * sy ** 2)))
    field = field / max(field.max(), 1e-6)
    tissue = field > 0.35

    # 病灶区：右上角一块，核更密、更嗜碱。
    #
    # 密度取值是刻意压低并保持对比的：后续的形态学膨胀会把覆盖率放大约 3 倍，
    # 若基础密度取高（如 0.24），膨胀后会整体饱和到 ~0.31，
    # 病灶与非病灶的差异会被抹平 —— 那会让"病灶可学"变成空话。
    # 这里取 0.13 vs 0.055（约 2.4 倍差），膨胀后仍保持清楚分离且不饱和。
    lesion = tissue & (xx > size * 0.55) & (yy < size * 0.45)
    density = np.where(lesion, 0.130, 0.055) + np.where(lesion, 0.035, 0.015) * field
    nuclei = (rng.random((size, size)) < density)
    # 细胞核做成 2—3 像素的斑点而非单像素：单像素在下采样两级后就消失了，
    # 会让"低倍概览层看不到病灶"变成假象（真实细胞核直径约 5—10 µm）。
    # 只膨胀一次，避免覆盖率饱和。
    nuclei_img = Image.fromarray((nuclei * 255).astype(np.uint8))
    nuclei_img = nuclei_img.filter(ImageFilter.MaxFilter(3))
    nuclei = np.asarray(nuclei_img, dtype=np.float32) > 127

    rgba = np.zeros((size, size, 3), dtype=np.float32)
    stroma = np.array([206.0, 154.0, 174.0])
    glass = np.array([246.0, 243.0, 238.0])
    cyto = np.array([224.0, 181.0, 199.0])
    nucleus_color = np.array([96.0, 66.0, 140.0])

    rgba[:] = glass
    rgba[tissue] = cyto
    rgba[tissue & (field > 0.55)] = stroma
    rgba = np.where(nuclei[..., None] > 0.5, nucleus_color, rgba)

    # 染色/扫描噪声 + 轻微光照梯度（贴近真实扫描件的非均匀性）
    rgba += rng.normal(0.0, 3.0, rgba.shape)
    grad = np.linspace(0.96, 1.04, size, dtype=np.float32)
    rgba *= grad[:, None, None]
    base = np.clip(rgba, 0, 255).astype(np.uint8)

    # ---- 逐级降采样（真实金字塔就是这么做出来的）
    stack = [base]
    current = base
    for _ in range(levels - 1):
        height, width = current.shape[:2]
        if min(height, width) <= 64:
            break
        img = Image.fromarray(current).resize((width // 2, height // 2), Image.LANCZOS)
        current = np.asarray(img, dtype=np.uint8)
        stack.append(current)
    return stack


def write_ome_pyramid(path: Path, stack: list[np.ndarray], mpp: float,
                      tile: int = 256, compression: str = "lzw") -> dict:
    """写多分辨率 tiled OME-TIFF（subifds 分级 + 物理尺寸元数据）。"""
    import tifffile

    path.parent.mkdir(parents=True, exist_ok=True)
    level0 = stack[0]
    # 分块与压缩选项对所有层级一致；subfiletype 单独给（0=主图，1=缩略层级）
    base_opts: dict = {"photometric": "rgb", "compression": compression}
    if tile:
        base_opts["tile"] = (tile, tile)
    with tifffile.TiffWriter(path, bigtiff=level0.size > 3.5e9) as tif:
        tif.write(
            level0, subfiletype=0, subifds=len(stack) - 1,
            metadata={"axes": "YXS", "PhysicalSizeX": mpp, "PhysicalSizeXUnit": "µm",
                      "PhysicalSizeY": mpp, "PhysicalSizeYUnit": "µm"},
            **base_opts,
        )
        for level in stack[1:]:
            tif.write(level, subfiletype=1, **base_opts)
    return {"path": str(path), "bytes": path.stat().st_size,
            "levels": len(stack), "tile": tile, "compression": compression}


def write_striped_pyramid(path: Path, stack: list[np.ndarray], mpp: float,
                          rows_per_strip: int = 128) -> dict:
    """写多分辨率 striped TIFF（用于验证条带级区域读取路径）。"""
    import tifffile

    path.parent.mkdir(parents=True, exist_ok=True)
    with tifffile.TiffWriter(path, bigtiff=stack[0].size > 3.5e9) as tif:
        tif.write(stack[0], photometric="rgb", rowsperstrip=rows_per_strip,
                  compression="lzw", subfiletype=0,
                  resolution=(10000.0 / mpp, 10000.0 / mpp), resolutionunit="CENTIMETER")
        for level in stack[1:]:
            tif.write(level, photometric="rgb", rowsperstrip=rows_per_strip,
                      compression="lzw", subfiletype=1)
    return {"path": str(path), "bytes": path.stat().st_size, "levels": len(stack),
            "rows_per_strip": rows_per_strip}


def write_single_png(path: Path, stack: list[np.ndarray]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(stack[0]).save(path, format="PNG", optimize=False)
    return {"path": str(path), "bytes": path.stat().st_size, "levels": 1}


def main() -> int:
    parser = argparse.ArgumentParser(description="生成真实金字塔切片样例")
    parser.add_argument("--size", type=int, default=4096, help="L0 边长（像素）")
    parser.add_argument("--levels", type=int, default=4, help="金字塔层级数")
    parser.add_argument("--mpp", type=float, default=0.25, help="L0 物理分辨率（µm/px）")
    parser.add_argument("--tile", type=int, default=256, help="分块边长（0=striped）")
    parser.add_argument("--out", default=str(ROOT / "data" / "samples"))
    parser.add_argument("--patterns", default="tiled,striped,single",
                        help="要生成的形式，逗号分隔：tiled,striped,single")
    args = parser.parse_args()

    out_dir = Path(args.out)
    patterns = {p.strip() for p in args.patterns.split(",") if p.strip()}

    print("=" * 78)
    print("  生成真实金字塔切片样例")
    print("=" * 78)
    print(f"  L0 尺寸：{args.size}×{args.size} · 层级：{args.levels} · "
          f"mpp：{args.mpp} · 分块：{args.tile or 'striped'}")

    stack = build_he_pyramid(args.size, args.levels)
    print(f"  金字塔：{[a.shape[0] for a in stack]}（各层边长）")

    results = {}
    if "tiled" in patterns:
        results["tiled"] = write_ome_pyramid(
            out_dir / "sample_pyramid.ome.tif", stack, args.mpp, tile=args.tile or 256)
    if "striped" in patterns:
        results["striped"] = write_striped_pyramid(
            out_dir / "sample_striped.tif", stack, args.mpp)
    if "single" in patterns:
        results["single"] = write_single_png(out_dir / "sample_single.png", stack)

    print()
    for kind, info in results.items():
        print(f"  [{kind:>7}] {Path(info['path']).name:<28} "
              f"{info['bytes'] / 1024 / 1024:6.2f} MB · {info['levels']} 层")

    manifest = out_dir / "samples.json"
    manifest.write_text(json.dumps({"mpp": args.mpp, "l0_size": args.size,
                                    "artifacts": results}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n  清单：{manifest}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
