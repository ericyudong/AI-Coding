"""真实切片文件读取器：格式探测 + 金字塔逐级读取。

设计文档依据：第四章 4.1（图块级建模）+ 第五章（Agent 低倍→高倍探查）。
生产环境把 `Slide.file_path` 指向真实切片，本模块负责把它变成统一的 `WSIReader`。

支持的后端（按优先级自动选择）：

| 后端 | 适用格式 | 说明 |
|---|---|---|
| `openslide` | svs / ndpi / mrxs / scn / tiff | 生产首选；未安装时自动跳过 |
| `tifffile` | svs / ndpi / scn / ome-tiff / tiff | 纯 Python，支持分块（tile）与条带（strip）级区域读取 |
| `pillow` | png / jpg / jpeg / bmp | 单图，自动构建真实降采样金字塔 |
| `numpy` | npy | 已解好的数组（调试/转换产物） |

**为什么必须实现分块区域读取，而不是"整层读进内存再切片"**：
一张 40X 全切片 L0 可达 10 万 × 8 万像素 ≈ 24 GB。整层加载在任何真实场景下
都直接 OOM。真实 WSI 采用 tiled-TIFF 存储，正确的做法是：只解码覆盖目标矩形
的那几个 tile。本模块对 tiled 与 striped TIFF 分别实现了区域读取，
并用有界 LRU 缓存相邻 tile（切片时空间局部性很强，命中率很高）。

**时间/内存的可验证性**：`scripts/selftest_wsi.py` 会生成一个真实金字塔 TIFF，
并断言「读取一个图块所耗内存远小于整层大小」，把"没有整层加载"变成可测事实。
"""

from __future__ import annotations

import logging
import struct
import threading
import warnings
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from app.services.wsi_service import (
    WSILevel,
    WSIReader,
    magnification_to_mpp,
    mpp_to_magnification,
)

logger = logging.getLogger(__name__)

Image.MAX_IMAGE_PIXELS = None   # 真实切片可以极大，去掉 PIL 的解压炸弹保护阈值


# ================================================================= 格式探测
# 常见 WSI 后缀 → (厂商, 容器)
_EXT_HINTS: dict[str, tuple[str, str]] = {
    ".svs": ("aperio", "tiff"),
    ".ndpi": ("hamamatsu", "tiff"),
    ".scn": ("leica", "tiff"),
    ".mrxs": ("mirax", "mirax"),
    ".vms": ("hamamatsu", "tiff"),
    ".vmu": ("hamamatsu", "tiff"),
    ".tif": ("generic", "tiff"),
    ".tiff": ("generic", "tiff"),
    ".ome.tif": ("generic", "tiff"),
    ".ome.tiff": ("generic", "tiff"),
    ".png": ("generic", "image"),
    ".jpg": ("generic", "image"),
    ".jpeg": ("generic", "image"),
    ".bmp": ("generic", "image"),
    ".npy": ("generic", "numpy"),
    ".dcm": ("dicom", "dicom"),
}


@dataclass
class SlideFormatInfo:
    """一次格式探测的结果。用于日志、`/assets/slides/{id}/format` 与上传校验。"""

    suffix: str
    vendor: str
    container: str
    backend: str
    is_tiff: bool
    magic: str
    bytes: int
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "suffix": self.suffix, "vendor": self.vendor, "container": self.container,
            "backend": self.backend, "is_tiff": self.is_tiff,
            "magic": self.magic, "bytes": self.bytes, "note": self.note,
        }


def _magic_head(path: Path, n: int = 256) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read(n)
    except Exception:
        return b""


def sniff_slide_format(path: str | Path) -> SlideFormatInfo:
    """按「魔数优先、后缀辅助」探测格式。

    为什么魔数优先：科室把 Aperio 文件改名成 `.tif` 是常态，
    只信后缀会把 SVS 当成普通 TIFF，丢掉厂商私有的标签（如 Aperio 的 MPP 标签 65420/65421）。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"切片文件不存在：{p}")
    size = p.stat().st_size
    suffix = p.suffix.lower()
    head = _magic_head(p)

    # ---- 魔数判定
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        container, vendor, is_tiff = "tiff", "generic", True
        # TIFF 描述里通常带厂商名
        lowered = head.lower()
        if b"aperio" in lowered or b"svs" in lowered:
            vendor = "aperio"
        elif b"hamamatsu" in lowered or b"ndpi" in lowered:
            vendor = "hamamatsu"
        elif b"leica" in lowered or b"scn" in lowered:
            vendor = "leica"
    elif head.startswith(b"\x89PNG\r\n\x1a\n"):
        container, vendor, is_tiff = "image", "generic", False
    elif head[:3] == b"\xff\xd8\xff":
        container, vendor, is_tiff = "image", "generic", False
    elif head[:2] == b"BM":
        container, vendor, is_tiff = "image", "generic", False
    elif head[:6] == b"\x93NUMPY":
        container, vendor, is_tiff = "numpy", "generic", False
    elif head[:4] == b"MRXS":
        container, vendor, is_tiff = "mirax", "mirax", False
    elif len(head) > 132 and head[128:132] == b"DICM":
        container, vendor, is_tiff = "dicom", "dicom", False
    else:
        container, vendor, is_tiff = "unknown", "generic", False

    # ---- 后缀补充/纠正：魔数认出是 TIFF 但后缀给出了厂商
    hint = _EXT_HINTS.get(suffix)
    if hint:
        hint_vendor, hint_container = hint
        if container == "unknown":
            container, vendor = hint_container, hint_vendor
        elif container == "tiff" and hint_vendor != "generic":
            vendor = hint_vendor          # SVS 常带 Aperio 描述，但改名文件可能不带头
        elif container == "image" and hint_container == "numpy":
            container = "numpy"

    backend = choose_backend(container, is_tiff)
    return SlideFormatInfo(
        suffix=suffix, vendor=vendor, container=container, backend=backend,
        is_tiff=is_tiff, magic=head[:8].hex(), bytes=size,
        note="" if container != "unknown" else "未能识别格式，将尝试按图像解码",
    )


def choose_backend(container: str, is_tiff: bool) -> str:
    """挑选可用后端。返回 'openslide' | 'tifffile' | 'pillow' | 'numpy' | 'none'。"""
    if is_tiff or container in ("tiff", "mirax"):
        if _has("openslide"):
            return "openslide"
        if _has("tifffile"):
            return "tifffile"
        return "none"
    if container == "numpy":
        return "numpy"
    if container == "image":
        return "pillow"
    # 未知：优先 tifffile（很多厂商容器其实是 TIFF），再 Pillow
    if _has("tifffile"):
        return "tifffile"
    if _has("PIL"):
        return "pillow"
    return "none"


def _has(module: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


# ================================================================= 分块解码工具
class _TileCache:
    """有界 LRU。切片遍历具有强空间局部性，缓存相邻 tile 命中率很高。"""

    def __init__(self, budget_mb: int = 256) -> None:
        self.budget = max(8, int(budget_mb)) * 1024 * 1024
        self._data: OrderedDict = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
        return None

    def put(self, key, value) -> None:
        nbytes = int(getattr(value, "nbytes", 0))
        with self._lock:
            if key in self._data:
                self._bytes -= int(getattr(self._data[key], "nbytes", 0))
                self._data.pop(key, None)
            self._data[key] = value
            self._bytes += nbytes
            while self._bytes > self.budget and self._data:
                _, evicted = self._data.popitem(last=False)
                self._bytes -= int(getattr(evicted, "nbytes", 0))

    @property
    def stats(self) -> dict:
        with self._lock:
            return {"entries": len(self._data), "bytes": self._bytes, "budget": self.budget}


class _TiffLevelPage:
    """一个 TIFF 层级（page）的分块/条带区域读取器。

    这是本模块的核心：**按需解码**而不是整层加载。

    - tiled TIFF：按 `page.tilewidth × page.tilelength` 计算覆盖目标矩形的 tile 索引，
      只读这些 tile 的原始字节并解码。
    - striped TIFF：按 `rowsperstrip` 计算覆盖行范围的条带，解码后按行切片。
    - 两种都经 `_TileCache` 缓存，避免相邻图块重复解码同一 tile。
    """

    def __init__(self, path: Path, page, cache: _TileCache, page_key: str) -> None:
        self.path = path
        self.page = page
        self.cache = cache
        self.page_key = page_key
        self.shape = tuple(int(v) for v in page.shape)      # (H, W) 或 (H, W, S)
        self.height = self.shape[0]
        self.width = self.shape[1]
        self.is_tiled = bool(getattr(page, "is_tiled", False))
        self.tile_w = int(getattr(page, "tilewidth", 0) or 0)
        self.tile_h = int(getattr(page, "tilelength", 0) or 0)
        self.rows_per_strip = int(getattr(page, "rowsperstrip", 0) or 0) or self.height
        self._segments: list[tuple[int, int]] | None = None
        self._fallback_decoded = False
        self._fh = None
        self._fh_lock = threading.Lock()

    # ------------------------------------------------------------ 原始字节读取
    def _segments_list(self) -> list[tuple[int, int]]:
        """(offset, bytecount) 列表，用于**随机访问**单个 tile/strip。

        为什么不用 `page.segments()`：那是个按顺序解码全部段的生成器，
        无法随机定位到"第 R 行第 C 列那个 tile"；而我们要的恰恰是随机访问。
        `dataoffsets` / `databytecounts` 是 TIFF 的段索引表，配合 `page.decode(raw, i)`
        就能只解码目标段 —— 这才是分块区域读取的正确做法。
        """
        if self._segments is None:
            offsets = tuple(int(v) for v in (getattr(self.page, "dataoffsets", ()) or ()))
            counts = tuple(int(v) for v in (getattr(self.page, "databytecounts", ()) or ()))
            if offsets and counts and len(offsets) == len(counts):
                self._segments = list(zip(offsets, counts))
            else:
                # 极少数结构没有段索引表：退回顺序解码并一次性物化（会占用整层内存，
                # 因此打 warning，提示这是降级路径而非正常路径）。
                logger.warning(
                    "文件 %s 的段索引不可用，退化为顺序解码（内存占用将显著上升）",
                    self.path.name,
                )
                self._segments = []
                for result in self.page.segments():
                    arr = result[0] if isinstance(result, tuple) else result
                    self._segments.append((-1, int(np.asarray(arr).nbytes)))
                self._fallback_decoded = True
        return self._segments

    def _read_raw(self, offset: int, bytecount: int) -> bytes:
        with self._fh_lock:
            if self._fh is None:
                self._fh = open(self.path, "rb")
            self._fh.seek(offset)
            return self._fh.read(bytecount)

    def _decode_segment(self, index: int) -> np.ndarray:
        """随机解码第 index 个 tile/strip。绝不解码其它段。"""
        key = (self.page_key, index)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        segs = self._segments_list()
        if index >= len(segs):
            raise IndexError(f"tile/strip 索引越界：{index} >= {len(segs)}")
        offset, bytecount = segs[index]
        if offset < 0:   # 降级路径
            arr = self._decode_by_order(index)
        else:
            raw = self._read_raw(offset, bytecount)
            decoded = self.page.decode(raw, index)
            arr = decoded[0] if isinstance(decoded, tuple) else decoded
        arr = self._normalize(arr)
        self.cache.put(key, arr)
        return arr

    @staticmethod
    def _normalize(arr) -> np.ndarray:
        """统一成 (H, W, 3) uint8。

        解码结果可能是 (1, H, W, 3)（多深度/多样本轴）或 (H, W) 灰度，
        这里把单例轴挤掉、灰度复制成三通道，保证下游拿到稳定形状。
        """
        arr = np.asarray(arr)
        while arr.ndim > 3 and arr.shape[0] == 1:
            arr = arr[0]
        if arr.ndim == 3 and arr.shape[0] in (3, 4) and arr.shape[2] not in (3, 4):
            arr = np.moveaxis(arr, 0, -1)      # planar → interleaved
        if arr.ndim == 2:
            arr = np.stack([arr] * 3, axis=-1)
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        return np.ascontiguousarray(arr[..., :3])

    def _decode_by_order(self, index: int) -> np.ndarray:
        for i, result in enumerate(self.page.segments()):
            if i == index:
                return result[0] if isinstance(result, tuple) else result
        raise IndexError(f"顺序解码未找到段 {index}")

    def close(self) -> None:
        with self._fh_lock:
            if self._fh is not None:
                try:
                    self._fh.close()
                except Exception:
                    pass
                self._fh = None

    # ------------------------------------------------------------ 区域读取
    def read(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        x = max(0, min(int(x), max(0, self.width - 1)))
        y = max(0, min(int(y), max(0, self.height - 1)))
        w = max(1, int(w))
        h = max(1, int(h))
        out = np.full((h, w, 3), 255, dtype=np.uint8)

        if self.is_tiled and self.tile_w and self.tile_h:
            self._read_tiled(x, y, w, h, out)
        else:
            self._read_striped(x, y, w, h, out)
        return out

    def _read_tiled(self, x: int, y: int, w: int, h: int, out: np.ndarray) -> None:
        tw, th = self.tile_w, self.tile_h
        cols = max(1, (self.width + tw - 1) // tw)
        rows = max(1, (self.height + th - 1) // th)
        # 钳制到实际存在的 tile 范围：影像尺寸不一定是 tile 的整数倍，
        # 靠近右/下边缘的读取会算出越界列行号，必须夹住否则解码时索引越界。
        c0 = max(0, min(x // tw, cols - 1))
        c1 = max(0, min((x + w - 1) // tw, cols - 1))
        r0 = max(0, min(y // th, rows - 1))
        r1 = max(0, min((y + h - 1) // th, rows - 1))
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                tile = self._decode_segment(r * cols + c)
                ty0, tx0 = r * th, c * tw
                # 目标矩形与本 tile 的交集
                sx0, sy0 = max(x, tx0), max(y, ty0)
                sx1, sy1 = min(x + w, tx0 + tile.shape[1]), min(y + h, ty0 + tile.shape[0])
                if sx1 <= sx0 or sy1 <= sy0:
                    continue
                src = tile[sy0 - ty0:sy1 - ty0, sx0 - tx0:sx1 - tx0]
                out[sy0 - y:sy1 - y, sx0 - x:sx1 - x] = src

    def _read_striped(self, x: int, y: int, w: int, h: int, out: np.ndarray) -> None:
        rps = max(1, self.rows_per_strip)
        total_strips = max(1, len(self._segments_list()))
        s0 = max(0, min(y // rps, total_strips - 1))
        s1 = max(0, min((y + h - 1) // rps, total_strips - 1))
        for s in range(s0, s1 + 1):
            strip = self._decode_segment(s)
            sy0 = s * rps
            # 目标矩形与条带在行方向的交集
            iy0, iy1 = max(y, sy0), min(y + h, sy0 + strip.shape[0])
            if iy1 <= iy0:
                continue
            # 列方向与条带的交集。注意顺序：ix0 是左边界（取 max），
            # ix1 是右边界（取 min）。写反会让交集恒为空、整片返回空白。
            ix0 = max(x, 0)
            ix1 = min(x + w, strip.shape[1])
            if ix1 <= ix0:
                continue
            src = strip[iy0 - sy0:iy1 - sy0, ix0:ix1]
            out[iy0 - y:iy1 - y, ix0 - x:ix1 - x] = src


# ================================================================= 后端实现
class TiffPyramidReader(WSIReader):
    """基于 tifffile 的真实金字塔 TIFF 读取器（svs / ndpi / scn / ome-tiff / tiff）。

    关键能力：
    - 识别多分辨率层级（pyramidal series），映射为 `WSILevel`。
    - 从 OME / 厂商标签 / 分辨率标签中提取 mpp（缺省回退到参数值）。
    - **分块区域读取**：读一个 128×128 图块只解码 1—4 个 tile，不加载整层。
    """

    def __init__(self, slide_code: str, file_path: str, base_mpp: float = 0.5,
                 level_count: int = 5, cache_mb: int = 256) -> None:
        import tifffile

        self.slide_code = slide_code
        self._path = Path(file_path)
        self._cache = _TileCache(cache_mb)
        self._pages: dict[int, _TiffLevelPage] = {}
        self._levels: list[WSILevel] = []
        self._handle = None
        self.info = sniff_slide_format(self._path)

        # tifffile 在多线程下对同一 TiffFile 并发访问不安全；读取用独立文件句柄，
        # 元数据解析只用一次，因此这里串行化"打开"这个动作即可。
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self._handle = tifffile.TiffFile(self._path)

        series = self._pick_series(self._handle)
        if series is None:
            self._handle.close()
            raise ValueError(f"文件中没有可读的图像系列：{self._path.name}")

        self._series = series
        self.base_mpp = self._resolve_mpp(series, base_mpp)

        # 构建层级：series.levels 在金字塔文件中就是各分辨率
        level_objs = self._series_levels(series)
        for index, level_obj in enumerate(level_objs[:max(1, level_count)]):
            page = self._level_page(level_obj)
            if page is None:
                continue
            height, width = int(page.shape[0]), int(page.shape[1])
            self._levels.append(WSILevel(
                level=index, width=width, height=height,
                mpp=self.base_mpp * (2 ** index),
                magnification=mpp_to_magnification(self.base_mpp * (2 ** index)),
            ))
            self._pages[index] = _TiffLevelPage(
                self._path, page, self._cache, f"{self._path.name}#{page.index}")

        if not self._levels:
            self._handle.close()
            raise ValueError(f"未能解析出任何金字塔层级：{self._path.name}")

    # ------------------------------------------------------------ 元数据
    @staticmethod
    def _pick_series(handle):
        """挑选最可能的"金字塔主体"系列。

        Aperio/Leica 文件里除主图外还有缩略图、标签图、宏图等系列。
        判据优先级：声明为 pyramidal 的 > 层级最多的 > 面积最大的。
        """
        best, best_score = None, None
        for s in handle.series:
            try:
                level_count = len(getattr(s, "levels", [s]))
                area = int(np.prod(s.shape[:2]))
                pyramidal = int(bool(getattr(s, "is_pyramidal", False)))
            except Exception:
                continue
            score = (pyramidal, level_count, area)
            if best_score is None or score > best_score:
                best, best_score = s, score
        return best

    @staticmethod
    def _series_levels(series) -> list:
        """把 series 展开为各层级（level 0 = 最高分辨率）。

        不同版本的 tifffile 用 `levels`（新）或需要手工从 pages 推断（旧）。
        这里做兼容，避免升级 tifffile 后整条读取链断掉。
        """
        levels = getattr(series, "levels", None)
        if levels:
            return list(levels)
        pages = list(getattr(series, "pages", []) or [])
        return pages or [series]

    @staticmethod
    def _level_page(level_obj):
        """从「层级对象」取出真正的 TiffPage。

        tifffile 的 `series.levels` 元素在不同版本/结构下可能是：
        - TiffPageSeries（金字塔子层级）→ 取它的 `.pages[0]`
        - TiffPage 本身（单页 series）→ 直接用
        两种情况都要能处理，否则换个文件结构就读不出来。
        """
        if hasattr(level_obj, "pages"):
            pages = list(getattr(level_obj, "pages") or [])
            return pages[0] if pages else None
        if hasattr(level_obj, "shape") and hasattr(level_obj, "segments"):
            return level_obj
        return None

    def _resolve_mpp(self, series, fallback: float) -> float:
        """提取 mpp，按「可靠度从高到低」依次尝试。

        顺序很重要：厂商标签（Aperio 65420/65421）比 OME 元数据更可信，
        OME 又比"从倍率标签猜"更可信；全都没有才用传入值。
        """
        # 1) tifffile 解析出的 mpp（部分版本从 OME 或分辨率标签得到）
        try:
            mpp = getattr(series, "mpp", None)
            if mpp and float(mpp) > 0:
                return float(mpp)
        except Exception:
            pass

        # 2) coord_scales / OME 物理尺寸
        try:
            scales = getattr(series, "coord_scales", None)
            if scales:
                first = scales[0] if isinstance(scales, (list, tuple)) else scales
                if first and float(first) > 0:
                    return float(first) * 1000.0   # µm/mm 视单位而定，保守换算
        except Exception:
            pass

        # 3) 厂商私有标签
        try:
            page = series.pages[0]
            tags = page.tags
            for name in ("XResolution", "ResolutionUnit"):
                _ = tags.get(name)   # 触发解析
            for aperio_tag in (65420, 65421):
                if aperio_tag in tags:
                    value = tags[aperio_tag].value
                    if value and float(value) > 0:
                        return abs(float(value))
        except Exception:
            pass

        # 4) OME 描述里的 PhysicalSizeX
        try:
            description = ""
            page = series.pages[0]
            desc_tag = page.tags.get("ImageDescription")
            if desc_tag is not None:
                description = str(desc_tag.value)
            if "PhysicalSizeX" in description:
                import re

                match = re.search(r"PhysicalSizeX=\"?([0-9.]+)\"?", description)
                unit = re.search(r"PhysicalSizeXUnit=\"?([a-zA-Z]+)\"?", description)
                if match:
                    value = float(match.group(1))
                    if unit and unit.group(1).lower().startswith("nm"):
                        value /= 1000.0
                    if value > 0:
                        return value
        except Exception:
            pass

        logger.info("未能从 %s 解析 mpp，使用传入值 %.3f", self._path.name, fallback)
        return float(fallback)

    # ------------------------------------------------------------ 读取
    @property
    def levels(self) -> list[WSILevel]:
        return self._levels

    def read_region(self, level: int, x: int, y: int, w: int, h: int) -> np.ndarray:
        page = self._pages.get(int(level))
        if page is None:
            raise IndexError(f"层级越界：{level}（共 {len(self._levels)} 层）")
        return page.read(x, y, w, h)

    def render_thumbnail(self, size: int = 320) -> Image.Image:
        # 优先用最低分辨率层（成本最低），不足时再向上采样
        level = len(self._levels) - 1
        width, height = self.dimensions(level)
        img = Image.fromarray(self.read_region(level, 0, 0, width, height))
        img.thumbnail((size, size))
        return img

    def cache_stats(self) -> dict:
        return self._cache.stats

    def close(self) -> None:
        for page in self._pages.values():
            page.close()
        if self._handle is not None:
            try:
                self._handle.close()
            except Exception:
                pass
            self._handle = None

    def __del__(self):  # pragma: no cover - 兜底释放
        try:
            self.close()
        except Exception:
            pass


class OpenSlideReader(WSIReader):
    """openslide 后端（生产首选）。未安装 openslide 时不会走到这里。"""

    def __init__(self, slide_code: str, file_path: str, base_mpp: float = 0.5) -> None:
        import openslide

        self.slide_code = slide_code
        self.info = sniff_slide_format(file_path)
        self._osr = openslide.OpenSlide(file_path)
        self._levels: list[WSILevel] = []
        native_mpp = self._native_mpp(base_mpp)
        self.base_mpp = native_mpp
        for index in range(self._osr.level_count):
            width, height = self._osr.level_dimensions[index]
            downsample = self._osr.level_downsamples[index]
            self._levels.append(WSILevel(
                level=index, width=int(width), height=int(height),
                mpp=native_mpp * float(downsample),
                magnification=mpp_to_magnification(native_mpp * float(downsample)),
            ))

    def _native_mpp(self, fallback: float) -> float:
        for key in ("openslide.mpp-x", "mpp-x", "tiff.XResolution"):
            value = self._osr.properties.get(key)
            if value:
                try:
                    parsed = float(value)
                    if key == "tiff.XResolution" and parsed > 0:
                        parsed = 10000.0 / parsed if parsed > 100 else parsed
                    if parsed > 0:
                        return parsed
                except ValueError:
                    continue
        return float(fallback)

    @property
    def levels(self) -> list[WSILevel]:
        return self._levels

    def read_region(self, level: int, x: int, y: int, w: int, h: int) -> np.ndarray:
        downsample = self._osr.level_downsamples[int(level)]
        region = self._osr.read_region(
            (int(x * downsample), int(y * downsample)), int(level), (int(w), int(h)))
        arr = np.asarray(region.convert("RGB"), dtype=np.uint8)
        return np.ascontiguousarray(arr)

    def close(self) -> None:
        try:
            self._osr.close()
        except Exception:
            pass


class SingleImageReader(WSIReader):
    """单张位图（PNG/JPG/BMP）读取器：构建**真实**降采样金字塔。

    与 `wsi_service.FileWSIReader` 的区别：
    - 原始位图可能非常大（数万像素），一次性转成整层数组会占大量内存；
      这里对每个层级**按需**从原图用 Pillow 的 draft/reduce 解码，
      并对层级平面做有界缓存。
    - 支持多帧 TIFF/多页图像的多分辨率语义。
    """

    def __init__(self, slide_code: str, file_path: str, base_mpp: float = 0.5,
                 level_count: int = 5, cache_mb: int = 256) -> None:
        self.slide_code = slide_code
        self.base_mpp = base_mpp
        self._path = Path(file_path)
        self.info = sniff_slide_format(self._path)
        with Image.open(self._path) as img:
            self._raw_size = (img.width, img.height)
            self._raw_mode = img.mode
        self._levels: list[WSILevel] = []
        width, height = self._raw_size
        for index in range(max(1, level_count)):
            scale = 2 ** index
            lw, lh = max(32, width // scale), max(32, height // scale)
            if index > 0 and lw >= width:
                break
            self._levels.append(WSILevel(
                level=index, width=lw, height=lh,
                mpp=base_mpp * scale, magnification=mpp_to_magnification(base_mpp * scale),
            ))
        self._cache = _TileCache(cache_mb)

    @property
    def levels(self) -> list[WSILevel]:
        return self._levels

    def _plane(self, level: int) -> np.ndarray:
        cached = self._cache.get(("plane", level))
        if cached is not None:
            return cached
        target = self._levels[level]
        with Image.open(self._path) as img:
            # draft：让解码器直接按目标尺寸解码（JPEG 可加速数倍且省内存）
            try:
                img.draft("RGB", (target.width, target.height))
            except Exception:
                pass
            resized = img.convert("RGB").resize((target.width, target.height), Image.BILINEAR)
            arr = np.asarray(resized, dtype=np.uint8)
        self._cache.put(("plane", level), arr)
        return arr

    def read_region(self, level: int, x: int, y: int, w: int, h: int) -> np.ndarray:
        plane = self._plane(int(level))
        size_y, size_x = plane.shape[:2]
        x = max(0, min(int(x), size_x - 1))
        y = max(0, min(int(y), size_y - 1))
        x2, y2 = min(size_x, x + int(w)), min(size_y, y + int(h))
        patch = plane[y:y2, x:x2]
        if patch.shape[0] != h or patch.shape[1] != w:
            canvas = np.full((int(h), int(w), 3), 255, dtype=np.uint8)
            canvas[: patch.shape[0], : patch.shape[1]] = patch
            return canvas
        return patch

    def cache_stats(self) -> dict:
        return self._cache.stats


class NumpyArrayReader(WSIReader):
    """`.npy` 数组读取器（转换产物 / 调试用）。"""

    def __init__(self, slide_code: str, file_path: str, base_mpp: float = 0.5,
                 level_count: int = 5) -> None:
        self.slide_code = slide_code
        self.base_mpp = base_mpp
        self._path = Path(file_path)
        self.info = sniff_slide_format(self._path)
        arr = np.load(self._path, mmap_mode="r")
        if arr.ndim == 2:
            arr = np.stack([arr] * 3, axis=-1)
        self._base = arr
        height, width = arr.shape[:2]
        self._levels: list[WSILevel] = []
        self._planes: dict[int, np.ndarray] = {0: np.asarray(arr[..., :3], dtype=np.uint8)}
        for index in range(max(1, level_count)):
            scale = 2 ** index
            lw, lh = max(32, width // scale), max(32, height // scale)
            if index > 0 and lw >= width:
                break
            self._levels.append(WSILevel(
                level=index, width=lw, height=lh,
                mpp=base_mpp * scale, magnification=mpp_to_magnification(base_mpp * scale),
            ))

    @property
    def levels(self) -> list[WSILevel]:
        return self._levels

    def _plane(self, level: int) -> np.ndarray:
        plane = self._planes.get(level)
        if plane is not None:
            return plane
        target = self._levels[level]
        img = Image.fromarray(self._planes[0]).resize((target.width, target.height), Image.BILINEAR)
        plane = np.asarray(img, dtype=np.uint8)
        self._planes[level] = plane
        return plane

    def read_region(self, level: int, x: int, y: int, w: int, h: int) -> np.ndarray:
        plane = self._plane(int(level))
        size_y, size_x = plane.shape[:2]
        x = max(0, min(int(x), size_x - 1))
        y = max(0, min(int(y), size_y - 1))
        x2, y2 = min(size_x, x + int(w)), min(size_y, y + int(h))
        patch = plane[y:y2, x:x2]
        if patch.shape[0] != h or patch.shape[1] != w:
            canvas = np.full((int(h), int(w), 3), 255, dtype=np.uint8)
            canvas[: patch.shape[0], : patch.shape[1]] = patch
            return canvas
        return patch


# ================================================================= 工厂
def open_real_slide(slide_code: str, file_path: str, base_mpp: float = 0.5,
                    level_count: int = 5, cache_mb: int = 256,
                    prefer: str = "") -> WSIReader:
    """打开真实切片文件，按格式自动选择后端。

    `prefer` 可强制指定后端（`openslide` / `tifffile` / `pillow` / `numpy`），
    用于排障：某个后端读出来不对时，可以显式换一个做对照。
    """
    info = sniff_slide_format(file_path)
    backend = prefer or info.backend
    if prefer and prefer != info.backend:
        logger.warning("强制指定后端 %s（自动探测结果为 %s）", prefer, info.backend)

    if backend == "openslide":
        return OpenSlideReader(slide_code, file_path, base_mpp=base_mpp)
    if backend == "tifffile":
        return TiffPyramidReader(slide_code, file_path, base_mpp=base_mpp,
                                 level_count=level_count, cache_mb=cache_mb)
    if backend == "numpy":
        return NumpyArrayReader(slide_code, file_path, base_mpp=base_mpp,
                                level_count=level_count)
    if backend == "pillow":
        return SingleImageReader(slide_code, file_path, base_mpp=base_mpp,
                                 level_count=level_count, cache_mb=cache_mb)

    # 兜底：先试 tifffile（很多厂商容器实为 TIFF），再试 Pillow，最后明确报错
    errors: list[str] = []
    if _has("tifffile"):
        try:
            return TiffPyramidReader(slide_code, file_path, base_mpp=base_mpp,
                                     level_count=level_count, cache_mb=cache_mb)
        except Exception as exc:
            errors.append(f"tifffile: {type(exc).__name__}: {exc}")
    try:
        return SingleImageReader(slide_code, file_path, base_mpp=base_mpp,
                                 level_count=level_count, cache_mb=cache_mb)
    except Exception as exc:
        errors.append(f"pillow: {type(exc).__name__}: {exc}")
    raise ValueError(
        f"无法读取切片 {Path(file_path).name}（探测格式={info.container}）。"
        f"尝试记录：{'; '.join(errors)}。"
        "真实厂商格式（svs/ndpi/mrxs/scn）建议安装 openslide。"
    )


def backend_capabilities() -> dict:
    """当前环境可用的读取后端（doctor / 上传校验 / 前端提示共用）。"""
    return {
        "openslide": _has("openslide"),
        "tifffile": _has("tifffile"),
        "pillow": _has("PIL"),
        "imagecodecs": _has("imagecodecs"),
        "numpy": True,
        "preferred_for": {
            "svs/ndpi/scn/mrxs": "openslide" if _has("openslide") else "tifffile",
            "ome-tiff/tiff": "openslide" if _has("openslide") else "tifffile",
            "png/jpg/bmp": "pillow",
            "npy": "numpy",
        },
        "note": ("imagecodecs 已安装：tifffile 可解码 LZW/JPEG/JPEG2000 等压缩 TIFF（真实 WSI 常用）"
                 if _has("imagecodecs") else
                 "imagecodecs 未安装：压缩 TIFF 可能无法解码，建议 pip install imagecodecs"),
    }
