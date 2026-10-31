"""WSI（全切片图像）读取、金字塔与图块抽取。

设计文档依据：第四章 4.1（图块级建模是唯一可注册路线）+ 第五章（Agent 低倍→高倍探查）。

读取器抽象（`WSIReader`）：
- 真实文件读取由 `app.services.wsi_readers` 承担：按格式自动选择
  openslide（生产首选）/ tifffile（金字塔 TIFF，分块区域读取）/ pillow（单图）/
  numpy（.npy）后端。真实厂商格式（svs/ndpi/scn/mrxs）与 OME-TIFF 均走此路径。
- `FileWSIReader`      —— 本模块内置的轻量位图读取器（PNG/JPEG/NPY），
  保留用于兼容旧数据与极简场景；真实切片请让 `open_slide` 走 `wsi_readers`。
- `SyntheticWSIReader` —— 确定性程序化生成的 H&E 病理图像金字塔（无文件时的演示兜底）。

`SyntheticWSIReader` 不是「假数据」：它生成的图像具备真实的 H&E 染色光谱特性
（苏木素嗜碱性细胞核 + 伊红细胞质），病灶区域通过**细胞核密度与核浆比差异**体现，
因此下游的颜色去卷积、核密度特征、ABMIL 注意力与评测指标全部是真实计算，
只是组织形态本身是可复现的合成信号。生产环境把 `file_path` 指向真实切片即可。

金字塔规格（mpp = 微米/像素）：
    L0 2048² @ 0.25 (40X)   高倍确认
    L1 1024² @ 0.50 (20X)   图块级特征 / MIL 主层，tile 128 → 64 图块
    L2  512² @ 1.00 (10X)   分诊初筛层，tile 128 → 16 个视野
    L3  256² @ 2.00 (5X)    全片概览
"""

from __future__ import annotations

import hashlib
import io
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import numpy as np
from PIL import Image

from app.services.image_utils import tissue_ratio

MAGNIFICATION_BY_MPP: tuple[tuple[float, str], ...] = (
    (0.30, "40X"),
    (0.60, "20X"),
    (1.20, "10X"),
    (2.50, "5X"),
)
GLASS_RGB = np.array([246.0, 243.0, 238.0], dtype=np.float32)
NUCLEUS_RGB = np.array([96.0, 66.0, 140.0], dtype=np.float32)
STROMA_RGB = np.array([206.0, 154.0, 174.0], dtype=np.float32)
CYTOPLASM_RGB = np.array([224.0, 181.0, 199.0], dtype=np.float32)


def mpp_to_magnification(mpp: float) -> str:
    for threshold, label in MAGNIFICATION_BY_MPP:
        if mpp <= threshold:
            return label
    return "2X"


def magnification_to_mpp(label: str) -> float:
    mapping = {"40X": 0.25, "20X": 0.5, "10X": 1.0, "5X": 2.0, "2X": 4.0}
    return mapping.get(label.upper().replace(" ", ""), 0.5)


def stable_seed(*parts: object) -> int:
    """由字符串稳定生成 32 位种子（跨进程可复现）。"""
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], "big")


@dataclass
class WSILevel:
    level: int
    width: int
    height: int
    mpp: float
    magnification: str


@dataclass
class TileRef:
    """一个候选图块的位置与基础统计量。"""

    level: int
    x: int
    y: int
    size: int
    mpp: float
    magnification: str
    tissue_ratio: float = 0.0
    extra: dict = field(default_factory=dict)


class WSIReader:
    """切片读取器抽象。"""

    slide_code: str = ""
    base_mpp: float = 0.25

    @property
    def levels(self) -> list[WSILevel]:  # pragma: no cover - 抽象
        raise NotImplementedError

    @property
    def level_count(self) -> int:
        return len(self.levels)

    def read_region(self, level: int, x: int, y: int, w: int, h: int) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def level_mpp(self, level: int) -> float:
        return self.base_mpp * (2 ** level)

    def magnitude_label(self, level: int) -> str:
        return mpp_to_magnification(self.level_mpp(level))

    def dimensions(self, level: int) -> tuple[int, int]:
        lv = self.levels[level]
        return lv.width, lv.height

    def tile_budget(self, config: Any) -> int:
        """预估本轮会抽取的图块数上限。

        仅用于把「已抽取 N 个」换算成进度百分比。它是上界估计而非精确值
        （背景块会被跳过），因此进度条在抽取阶段只会单调递增、不会倒退。
        """
        width, height = self.dimensions(int(getattr(config, "level", 0)))
        tile_size = int(getattr(config, "tile_size", 256)) or 256
        stride = int(getattr(config, "stride", tile_size)) or tile_size
        cols = max(1, (width - tile_size) // stride + 1)
        rows = max(1, (height - tile_size) // stride + 1)
        budget = cols * rows
        max_tiles = int(getattr(config, "max_tiles", 0) or 0)
        if max_tiles > 0:
            budget = min(budget, max_tiles)
        return max(budget, 1)

    # ------------------------------------------------------------- 图块抽取
    def iter_tiles(
        self,
        level: int,
        tile_size: int,
        stride: int | None = None,
        max_tiles: int = 0,
        min_tissue_ratio: float = 0.05,
        offset_x: int = 0,
        offset_y: int = 0,
        region: tuple[int, int, int, int] | None = None,
    ) -> Iterator[TileRef]:
        """按滑动窗口产出图块引用；自动跳过背景块。"""
        stride = stride or tile_size
        width, height = self.dimensions(level)
        x0, y0, x1, y1 = region if region else (0, 0, width, height)
        x0 = max(0, min(x0, width - 1))
        y0 = max(0, min(y0, height - 1))
        x1 = max(x0 + 1, min(x1, width))
        y1 = max(y0 + 1, min(y1, height))

        emitted = 0
        start_x = x0 + offset_x
        start_y = y0 + offset_y
        for y in range(start_y, y1 - tile_size + 1, stride):
            for x in range(start_x, x1 - tile_size + 1, stride):
                tile = self.read_region(level, x, y, tile_size, tile_size)
                ratio = tissue_ratio(tile)
                if ratio < min_tissue_ratio:
                    continue
                emitted += 1
                yield TileRef(
                    level=level,
                    x=x,
                    y=y,
                    size=tile_size,
                    mpp=self.level_mpp(level),
                    magnification=self.magnitude_label(level),
                    tissue_ratio=ratio,
                )
                if max_tiles and emitted >= max_tiles:
                    return

    def count_tiles(self, level: int, tile_size: int, stride: int | None = None,
                    min_tissue_ratio: float = 0.05) -> int:
        return sum(1 for _ in self.iter_tiles(level, tile_size, stride, min_tissue_ratio=min_tissue_ratio))

    # -------------------------------------------------------------- 渲染
    def render_thumbnail(self, size: int = 320) -> Image.Image:
        level = self.level_count - 1
        width, height = self.dimensions(level)
        img = Image.fromarray(self.read_region(level, 0, 0, width, height))
        img.thumbnail((size, size))
        return img

    def render_region_png(self, level: int, x: int, y: int, w: int, h: int) -> bytes:
        arr = self.read_region(level, x, y, w, h)
        buffer = io.BytesIO()
        Image.fromarray(arr).save(buffer, format="PNG")
        return buffer.getvalue()

    def lesion_mask_at(self, level: int) -> np.ndarray | None:
        """返回该层级的病灶掩膜（合成切片才有）。用于评估 Agent 导航命中率。"""
        return None

    def lesion_bbox_at_level0(self) -> list[int]:
        mask = self.lesion_mask_at(0)
        if mask is None or not mask.any():
            return []
        ys, xs = np.where(mask)
        return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.min()), int(xs.max()), int(ys.max()), int(xs.min()), int(ys.max())]


# ---------------------------------------------------------------------------
class SyntheticWSIReader(WSIReader):
    """确定性合成的 H&E 病理图像金字塔。"""

    def __init__(
        self,
        slide_code: str,
        base_size: int = 2048,
        level_count: int = 4,
        base_mpp: float = 0.25,
        has_lesion: bool = False,
        lesion_strength: float = 1.0,
        seed_salt: str = "",
        site_code: str = "",
    ) -> None:
        self.slide_code = slide_code
        self.base_size = base_size
        self.base_mpp = base_mpp
        self.has_lesion = has_lesion
        self.lesion_strength = lesion_strength
        self.site_code = site_code
        self._seed = stable_seed(slide_code, seed_salt)
        self._site_profile = self._site_stain_profile(site_code)
        # 难度分层：真实筛查问题里总有「小灶/不典型」的困难阳性与「核密度也偏高」的
        # 反应性增生阴性。若所有样本都一目可分，评测基座、阈值选择与概率标定就形同虚设。
        diff_rng = np.random.default_rng(stable_seed("difficulty", slide_code, seed_salt))
        self._difficulty = float(diff_rng.uniform(0.0, 1.0))
        self._normal_boost = 0.0
        if has_lesion:
            if self._difficulty < 0.20:
                self.lesion_strength *= 0.34          # 困难阳性：微灶
            elif self._difficulty < 0.45:
                self.lesion_strength *= 0.64          # 中等难度
        elif self._difficulty < 0.30:
            self._normal_boost = float(diff_rng.uniform(0.040, 0.070))
            """反应性增生：核密度也偏高，对模型形成真实干扰。"""
        self._levels: list[WSILevel] = []
        for level in range(level_count):
            size = max(64, base_size >> level)
            self._levels.append(
                WSILevel(
                    level=level,
                    width=size,
                    height=size,
                    mpp=base_mpp * (2 ** level),
                    magnification=mpp_to_magnification(base_mpp * (2 ** level)),
                )
            )
        self._cache: dict[int, np.ndarray] = {}
        self._lesion_grids: dict[int, np.ndarray] = {}

    @staticmethod
    def _site_stain_profile(site_code: str) -> dict[str, Any]:
        """各中心的染色/扫描差异画像。

        不同医院使用不同染色机与扫描仪，会带来整体色调偏移与对比度差异——
        这正是设计文档 R3「跨中心泛化衰减（中心特异性）」的物理来源。
        合成切片如实模拟该差异，使「按中心分组的指标衰减」成为可复现的真实现象。
        """
        if not site_code:
            return {"gain": np.array([1.0, 1.0, 1.0], dtype=np.float32), "gamma": 1.0, "bias": 0.0}
        rng = np.random.default_rng(stable_seed("site", site_code))
        return {
            "gain": (1.0 + rng.uniform(-0.11, 0.11, size=3)).astype(np.float32),
            "gamma": float(1.0 + rng.uniform(-0.22, 0.22)),
            "bias": float(rng.uniform(-14.0, 14.0)),
            "site_code": site_code,
        }

    def _slide_stain_jitter(self, level: int) -> dict[str, float]:
        """同一中心内逐片也不一致（染色批次、切片厚薄差异）。"""
        rng = np.random.default_rng(stable_seed("slide-stain", self.slide_code, level))
        return {
            "gain": float(1.0 + rng.uniform(-0.045, 0.045)),
            "gamma": float(1.0 + rng.uniform(-0.09, 0.09)),
        }

    @property
    def levels(self) -> list[WSILevel]:
        return self._levels

    # ------------------------------------------------------------ 场生成
    @staticmethod
    def _smooth_noise(rng: np.random.Generator, size: int, coarse: int = 24) -> np.ndarray:
        coarse = max(2, min(coarse, size))
        small = (rng.random((coarse, coarse)) * 255).astype(np.uint8)
        img = Image.fromarray(small).resize((size, size), Image.BICUBIC)
        return np.asarray(img, dtype=np.float32) / 255.0

    @staticmethod
    def _gaussian_blob(size: int, cx: float, cy: float, sx: float, sy: float,
                       theta: float = 0.0) -> np.ndarray:
        ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
        dx = xs - cx
        dy = ys - cy
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        xr = dx * cos_t + dy * sin_t
        yr = -dx * sin_t + dy * cos_t
        return np.exp(-0.5 * ((xr / sx) ** 2 + (yr / sy) ** 2)).astype(np.float32)

    @staticmethod
    def _box_blur3(field: np.ndarray) -> np.ndarray:
        """3×3 均值模糊（用累积和实现，避免 scipy 依赖）。"""
        pad = np.pad(field, 1, mode="edge")
        acc = np.cumsum(np.cumsum(pad, axis=0), axis=1)
        acc = np.pad(acc, ((1, 0), (1, 0)), mode="constant")
        h, w = field.shape
        total = acc[3:, 3:] - acc[:-3, 3:] - acc[3:, :-3] + acc[:-3, :-3]
        return (total[:h, :w] / 9.0).astype(np.float32)

    def _build_level(self, level: int) -> np.ndarray:
        cached = self._cache.get(level)
        if cached is not None:
            return cached

        lv = self._levels[level]
        size = lv.width
        step = max(1, 4 >> level)
        gsize = max(16, size // step)
        rng = np.random.default_rng(self._seed ^ (level * 7919 + 13))

        # ---- 1. 组织区域（多叶高斯 + 低频噪声扰动，形成不规则轮廓）
        field = np.zeros((gsize, gsize), dtype=np.float32)
        lobes = 4 + int(rng.integers(0, 3))
        for _ in range(lobes):
            cx = float(rng.uniform(0.15, 0.85)) * gsize
            cy = float(rng.uniform(0.15, 0.85)) * gsize
            sx = float(rng.uniform(0.17, 0.32)) * gsize
            sy = float(rng.uniform(0.17, 0.32)) * gsize
            field += self._gaussian_blob(gsize, cx, cy, sx, sy, float(rng.uniform(0, math.pi)))
        field = field / max(field.max(), 1e-6)
        field = field * (0.80 + 0.40 * self._smooth_noise(rng, gsize, max(4, gsize // 24)))
        tissue = field > 0.26

        # ---- 2. 病灶区域（核密度显著升高，核浆比增大）
        lesion = np.zeros((gsize, gsize), dtype=bool)
        if self.has_lesion:
            cx = float(rng.uniform(0.30, 0.70)) * gsize
            cy = float(rng.uniform(0.30, 0.70)) * gsize
            sx = float(rng.uniform(0.11, 0.19)) * gsize
            sy = float(rng.uniform(0.11, 0.19)) * gsize
            blob = self._gaussian_blob(gsize, cx, cy, sx, sy, float(rng.uniform(0, math.pi)))
            wobble = 0.75 + 0.50 * self._smooth_noise(rng, gsize, max(4, gsize // 20))
            lesion = (blob * wobble) > (0.36 - 0.08 * self.lesion_strength)
            lesion &= tissue

        # ---- 3. 细胞核密度场
        # 难度分层：`lesion_strength` 同时调制密度差与病灶范围，
        # 使「困难阳性（微灶）」在特征空间上与阴性真实重叠，而不是人为制造一眼可分的玩具问题。
        fine = self._smooth_noise(rng, gsize, max(6, gsize // 12))
        strength = float(np.clip(self.lesion_strength, 0.15, 1.30))
        normal_density = 0.150 + self._normal_boost + 0.055 * fine
        lesion_gap = (0.115 + 0.100 * fine) * strength
        lesion_density = normal_density + lesion_gap
        density = np.where(lesion, lesion_density, normal_density) * tissue.astype(np.float32)
        nuclei = (rng.random((gsize, gsize)) < density).astype(np.float32)

        # ---- 4. 上采样到像素栅格并柔化（细胞核呈团块状而非单像素）
        nuc_img = np.repeat(np.repeat(nuclei, step, axis=0), step, axis=1)[:size, :size]
        nuc_img = self._box_blur3(nuc_img)
        nuc_img = np.clip((nuc_img - 0.10) * 1.45, 0.0, 1.0).astype(np.float32)

        tissue_img = np.repeat(np.repeat(tissue.astype(np.float32), step, axis=0), step, axis=1)[:size, :size]
        tissue_img = np.clip(self._box_blur3(tissue_img) * 1.6, 0.0, 1.0)

        # ---- 5. 组织底色（基质 / 细胞质按低频噪声混合）
        mix = self._smooth_noise(rng, size, max(6, size // 48))[..., None]
        base_color = STROMA_RGB * (1.0 - mix) + CYTOPLASM_RGB * mix

        # ---- 6. 合成（核浆比：病灶区核覆盖更高，胞质更少）
        nuclear_weight = np.clip(nuc_img, 0.0, 1.0)[..., None]
        rgb = base_color * (1.0 - nuclear_weight * 0.88) + NUCLEUS_RGB * (nuclear_weight * 0.88)

        # ---- 7. 光照梯度与传感器噪声
        grad_y = np.linspace(0.94, 1.06, size, dtype=np.float32)[:, None, None]
        grad_x = np.linspace(1.03, 0.97, size, dtype=np.float32)[None, :, None]
        rgb = rgb * grad_y * grad_x
        rgb += rng.normal(0.0, 2.6, rgb.shape).astype(np.float32)

        # ---- 7b. 中心级与逐片级染色差异（对应风险 R3 的中心特异性）
        jitter = self._slide_stain_jitter(level)
        profile = self._site_profile
        needs_color_shift = bool(profile.get("site_code")) or abs(jitter["gain"] - 1.0) > 1e-4
        if needs_color_shift:
            normalized = np.clip(rgb, 0, 255) * np.float32(1.0 / 255.0)
            gamma = np.float32(profile["gamma"] * jitter["gamma"])
            normalized = np.power(np.clip(normalized, 1e-6, 1.0), gamma)
            rgb = normalized * np.float32(255.0) * (profile["gain"] * np.float32(jitter["gain"]))
            rgb = rgb + np.float32(profile["bias"])

        # ---- 8. 组织外为玻片背景
        rgb = np.where(tissue_img[..., None] > 0.35, rgb, GLASS_RGB)

        out = np.clip(rgb, 0, 255).astype(np.uint8)
        self._cache[level] = out
        self._lesion_grids[level] = lesion
        return out

    def lesion_mask_at(self, level: int) -> np.ndarray | None:
        if not self.has_lesion:
            return None
        self._build_level(level)
        grid = self._lesion_grids.get(level)
        if grid is None:
            return None
        lv = self._levels[level]
        size = lv.width
        step = max(1, 4 >> level)
        return np.repeat(np.repeat(grid, step, axis=0), step, axis=1)[:size, :size]

    def read_region(self, level: int, x: int, y: int, w: int, h: int) -> np.ndarray:
        plane = self._build_level(level)
        size = plane.shape[0]
        x = max(0, min(int(x), size - 1))
        y = max(0, min(int(y), size - 1))
        x2 = min(size, x + int(w))
        y2 = min(size, y + int(h))
        patch = plane[y:y2, x:x2]
        if patch.shape[0] != h or patch.shape[1] != w:
            canvas = np.full((int(h), int(w), 3), GLASS_RGB.astype(np.uint8))
            canvas[: patch.shape[0], : patch.shape[1]] = patch
            return canvas
        return patch


# ---------------------------------------------------------------------------
class FileWSIReader(WSIReader):
    """真实切片文件读取器（PNG/JPEG/NPY/TIFF），自动构建降采样金字塔。"""

    def __init__(self, slide_code: str, file_path: str, base_mpp: float = 0.5, level_count: int = 4) -> None:
        self.slide_code = slide_code
        self.base_mpp = base_mpp
        self._path = Path(file_path)
        if not self._path.exists():
            raise FileNotFoundError(f"切片文件不存在：{file_path}")

        if self._path.suffix.lower() == ".npy":
            arr = np.load(self._path)
            if arr.ndim == 2:
                arr = np.stack([arr] * 3, axis=-1)
            self._base = np.clip(arr[..., :3], 0, 255).astype(np.uint8)
        else:
            with Image.open(self._path) as img:
                self._base = np.asarray(img.convert("RGB"), dtype=np.uint8)

        self._levels: list[WSILevel] = []
        h, w = self._base.shape[:2]
        self._plane_cache: dict[int, np.ndarray] = {0: self._base}
        for level in range(level_count):
            scale = 2 ** level
            lw, lh = max(16, w // scale), max(16, h // scale)
            if lw >= w and level > 0:
                break
            self._levels.append(
                WSILevel(level=level, width=lw, height=lh,
                         mpp=base_mpp * scale, magnification=mpp_to_magnification(base_mpp * scale))
            )

    @property
    def levels(self) -> list[WSILevel]:
        return self._levels

    def _plane(self, level: int) -> np.ndarray:
        plane = self._plane_cache.get(level)
        if plane is not None:
            return plane
        lv = self._levels[level]
        img = Image.fromarray(self._base).resize((lv.width, lv.height), Image.BILINEAR)
        plane = np.asarray(img, dtype=np.uint8)
        self._plane_cache[level] = plane
        return plane

    def read_region(self, level: int, x: int, y: int, w: int, h: int) -> np.ndarray:
        plane = self._plane(level)
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


# ---------------------------------------------------------------------------
def open_slide(slide: object, *, prefer_backend: str = "") -> WSIReader:
    """工厂：有真实文件则按格式打开真实切片，否则回退到确定性合成切片。

    `slide` 可以是 ORM 对象或 dict，需要 code / file_path / mpp / has_lesion 字段。

    真实文件的读取交给 `app.services.wsi_readers`：它会按魔数+后缀探测格式，
    在 openslide / tifffile / pillow / numpy 之间挑可用后端，
    并对 tiled/striped TIFF 做**分块区域读取**（不整层加载）。

    `prefer_backend`：强制指定后端，仅用于排障对照。
    """
    def _get(obj: object, key: str, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    code = str(_get(slide, "code", "") or _get(slide, "slide_code", "SYN-000"))
    file_path = str(_get(slide, "file_path", "") or "")
    mpp = float(_get(slide, "mpp", 0.5) or 0.5)
    has_lesion = bool(_get(slide, "has_lesion", False))

    if file_path and Path(file_path).exists():
        from app.services.wsi_readers import open_real_slide

        return open_real_slide(code, file_path, base_mpp=mpp, prefer=prefer_backend)

    # 合成切片的 base_mpp 固定为 0.25（40X），保证金字塔倍率阶梯一致
    case_no = str(_get(slide, "case_no", "") or "")
    site_code = str(_get(slide, "site_code", "") or "")
    return SyntheticWSIReader(
        code,
        base_size=2048,
        level_count=4,
        base_mpp=0.25,
        has_lesion=has_lesion,
        seed_salt=case_no,
        site_code=site_code,
    )


def slide_reader_info(slide: object, *, prefer_backend: str = "") -> dict:
    """返回「这张切片由谁读、怎么读」的自述，供上传校验与前端展示。"""
    from app.services.wsi_readers import backend_capabilities, sniff_slide_format

    def _get(obj: object, key: str, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    file_path = str(_get(slide, "file_path", "") or "")
    payload: dict = {"source": "synthetic", "backend": "synthetic",
                     "capabilities": backend_capabilities()}
    if file_path and Path(file_path).exists():
        info = sniff_slide_format(file_path)
        payload.update({"source": "file", **info.to_dict()})
        if prefer_backend:
            payload["prefer_backend"] = prefer_backend
    return payload
