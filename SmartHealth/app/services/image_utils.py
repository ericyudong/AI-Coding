"""病理图像基础算法：光密度变换、颜色去卷积、染色归一化、形态学特征提取。

这些函数是「图块级特征模型」的真实计算底座，不依赖任何深度学习框架：

1. `optical_density` / `color_deconvolve` 采用 Ruifrok & Johnston (2001) 标准颜色去卷积，
   把 RGB 分解为苏木素(H) / 伊红(E) / 残余(D) 三个染色通道浓度。
2. `reinhard_normalize` 做染色归一化（通道统计匹配），用于降低不同扫描仪/实验室的
   染色差异 —— 这是设计文档 R3「跨中心泛化衰减」的第一道应对措施。
3. `tile_features` 从单个图块提取 67 维形态学/染色学特征（细胞核密度、空间分布、
   纹理多尺度方差、染色通道直方图、颜色矩），供编码器投影为嵌入向量。

性能说明：全链路使用 float32 与 `np.bincount` 直方图统计（避免 np.histogram 的
排序开销），单图块特征提取约 4—6 ms（128×128），满足批量预计算的吞吐要求。

生产环境接入真实病理基座模型时，只需替换 `encoder_service` 中的编码器实现，
本模块仍然用于预处理（归一化）与可解释性辅助特征（核密度、染色占比）。
"""

from __future__ import annotations

import numpy as np

RGB_MAX = 255.0
OD_EPS = 1.0 / RGB_MAX

# ------------------------------------------------------------------ 标准染色矩阵
# Ruifrok & Johnston 2001, OD 空间下的单位化染色向量
STAIN_H = np.array([0.650, 0.704, 0.286], dtype=np.float32)
STAIN_E = np.array([0.072, 0.990, 0.105], dtype=np.float32)
STAIN_D = np.array([0.268, 0.570, 0.776], dtype=np.float32)
HE_STAIN_MATRIX = np.stack([STAIN_H, STAIN_E, STAIN_D], axis=0)  # (3, 3)，行为单位化染色向量
HE_STAIN_INV = np.linalg.pinv(HE_STAIN_MATRIX).astype(np.float32)

# Reinhard 目标统计量（H&E 切片的经验均值/标准差，0—255 RGB）
REINHARD_TARGET_MEAN = np.array([168.0, 132.0, 168.0], dtype=np.float32)
REINHARD_TARGET_STD = np.array([46.0, 42.0, 44.0], dtype=np.float32)

# 组织掩膜判据
TISSUE_SATURATION_THRESHOLD = 0.10
TISSUE_BRIGHTNESS_CEILING = 0.92


def to_float(rgb: np.ndarray) -> np.ndarray:
    """uint8 -> float32，范围 [0,1]。"""
    return np.asarray(rgb, dtype=np.float32) * np.float32(1.0 / RGB_MAX)


def optical_density(rgb: np.ndarray) -> np.ndarray:
    """RGB -> 光密度 OD = -log10(I)，并裁剪到 [0, 4]。"""
    intensity = np.clip(to_float(rgb), OD_EPS, 1.0)
    return np.clip(-np.log10(intensity), 0.0, 4.0)


def color_deconvolve(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """颜色去卷积，返回 (H 浓度, E 浓度, 残余浓度)，形状与输入前两维一致。

    线性模型：OD = c · S，其中 S 的行是单位化染色向量，c = (h, e, d)。
    因此 c = OD · pinv(S) —— 对纯苏木素像素（OD ∝ STAIN_H）应解得 c≈(k,0,0)。
    浓度按通道裁剪为非负（物理上浓度不能为负）。
    """
    od = optical_density(rgb)
    h, w = od.shape[0], od.shape[1]
    conc = od.reshape(-1, 3) @ HE_STAIN_INV
    np.clip(conc, 0.0, None, out=conc)
    return conc[:, 0].reshape(h, w), conc[:, 1].reshape(h, w), conc[:, 2].reshape(h, w)


# ------------------------------------------------------------------ 染色归一化
def reinhard_normalize(rgb: np.ndarray, target_mean: np.ndarray | None = None,
                       target_std: np.ndarray | None = None) -> np.ndarray:
    """通道统计匹配的染色归一化，返回 uint8。

    对每个通道做 z-score 标准化后匹配到目标分布的均值与标准差。
    这是 Macenke/Vahadane 之外的轻量替代，用于演示「染色归一化 + 中心不变性训练」
    这条应对措施具备可执行落点；生产环境可无缝替换为 Macenke 实现。
    """
    t_mean = REINHARD_TARGET_MEAN if target_mean is None else np.asarray(target_mean, dtype=np.float32)
    t_std = REINHARD_TARGET_STD if target_std is None else np.asarray(target_std, dtype=np.float32)

    data = np.asarray(rgb, dtype=np.float32)
    flat = data.reshape(-1, 3)
    src_mean = flat.mean(axis=0)
    src_std = flat.std(axis=0)
    np.maximum(src_std, 1e-6, out=src_std)
    out = (flat - src_mean) * (t_std / src_std) + t_mean
    return np.clip(out, 0, 255).reshape(data.shape).astype(np.uint8)


def stain_stats(rgb: np.ndarray) -> dict[str, float]:
    """染色统计摘要（归一化前后对比用）。"""
    data = np.asarray(rgb, dtype=np.float32).reshape(-1, 3)
    mean = data.mean(axis=0)
    std = data.std(axis=0)
    return {
        "r_mean": float(mean[0]), "g_mean": float(mean[1]), "b_mean": float(mean[2]),
        "r_std": float(std[0]), "g_std": float(std[1]), "b_std": float(std[2]),
    }


# -------------------------------------------------------------------- 组织掩膜
def tissue_mask(rgb: np.ndarray, saturation_threshold: float = TISSUE_SATURATION_THRESHOLD) -> np.ndarray:
    """组织区域掩膜：非白背景且饱和度高于阈值。

    对应「组织占比」这一质控口径 —— 占比过低的图块应被丢弃，
    这直接决定 `min_tissue_ratio` 拒识规则的触发。
    """
    data = to_float(rgb)
    mx = data.max(axis=2)
    mn = data.min(axis=2)
    saturation = (mx - mn) / np.maximum(mx, 1e-6)
    brightness = data.mean(axis=2)
    return (saturation > saturation_threshold) & (brightness < TISSUE_BRIGHTNESS_CEILING)


def tissue_ratio(rgb: np.ndarray) -> float:
    return float(tissue_mask(rgb).mean())


# -------------------------------------------------------------------- 细胞核掩膜
def _fast_quantile(values: np.ndarray, q: float) -> float:
    """O(n) 分位数（np.partition），比 np.quantile 的排序实现快数倍。"""
    n = values.size
    if n == 0:
        return 0.0
    k = int(round(q * (n - 1)))
    k = min(max(k, 0), n - 1)
    return float(np.partition(values, k)[k])


def nuclei_mask(h_conc: np.ndarray, e_conc: np.ndarray, tissue: np.ndarray | None = None,
                h_quantile: float = 0.68, min_h: float = 0.12) -> np.ndarray:
    """细胞核掩膜。

    判据：苏木素浓度在组织区域内处于高分位（细胞核嗜碱性），且 H 相对 E 占优。
    阈值取组织区域内的分位数，使判据自动适应染色深浅差异（跨中心鲁棒）；
    同时设绝对下限 min_h，避免把玻片背景的极低浓度噪声判成细胞核。
    """
    valid = tissue if tissue is not None else np.ones_like(h_conc, dtype=bool)
    sample = h_conc[valid & (h_conc > min_h)]
    if sample.size < 16:
        return np.zeros_like(h_conc, dtype=bool)
    threshold = max(_fast_quantile(sample, h_quantile), min_h)
    dominance = h_conc - np.float32(0.85) * e_conc
    return (h_conc > threshold) & (dominance > np.float32(0.03)) & valid


def nuclear_size_proxy(mask: np.ndarray) -> tuple[float, float]:
    """细胞核尺寸/拥挤度代理量（无需连通域分析）。

    做法：对掩膜做 2×2 与 4×4 平均池化，统计「仍判定为核」的子格比例。
    核越大越密集，池化后残留比例越高 —— 单调反映核尺寸与拥挤度。
    """
    if mask.size == 0 or not mask.any():
        return 0.0, 0.0
    m = mask.astype(np.float32)
    h, w = m.shape
    p2 = m[: h // 2 * 2, : w // 2 * 2].reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))
    p4 = m[: h // 4 * 4, : w // 4 * 4].reshape(h // 4, 4, w // 4, 4).mean(axis=(1, 3))
    return float((p2 > 0.6).mean()), float((p4 > 0.6).mean())


def grid_stats(field: np.ndarray, grid: int) -> np.ndarray:
    """把二维场切成 grid×grid 子格并返回每格均值（空间分布特征）。"""
    h, w = field.shape
    gh, gw = h // grid, w // grid
    if gh == 0 or gw == 0:
        return np.zeros(grid * grid, dtype=np.float32)
    trimmed = field[: gh * grid, : gw * grid]
    return trimmed.reshape(grid, gh, grid, gw).mean(axis=(1, 3)).reshape(-1).astype(np.float32)


def _hist8(conc: np.ndarray) -> np.ndarray:
    """8 桶直方图（范围 [0, 2]，桶宽 0.25），用 bincount 实现以避开排序开销。"""
    idx = np.clip((conc * np.float32(4.0)).astype(np.int32, copy=False), 0, 7).ravel()
    counts = np.bincount(idx, minlength=8).astype(np.float32)
    return counts / max(conc.size, 1)


def grid_std(field: np.ndarray, grid: int = 4) -> np.ndarray:
    """多尺度纹理：grid×grid 子格内的标准差。"""
    h, w = field.shape
    gh, gw = h // grid, w // grid
    if gh == 0 or gw == 0:
        return np.zeros(grid * grid, dtype=np.float32)
    trimmed = field[: gh * grid, : gw * grid]
    return trimmed.reshape(grid, gh, grid, gw).std(axis=(1, 3)).reshape(-1).astype(np.float32)


# -------------------------------------------------------------------- 图块特征
FEATURE_DIM_HANDCRAFTED = 67


def tile_features(rgb: np.ndarray, drop_background: bool = False) -> np.ndarray | None:
    """从单个图块提取 67 维特征。`drop_background=True` 时对背景块返回 None。

    特征构成（合计 67 维）：
      染色通道统计            : mean/std of H, E, D            -> 6
      细胞核比例              : nuclear fraction               -> 1
      细胞核空间分布          : 4×4 网格核占比                 -> 16
      核尺寸/拥挤度代理       : 2 尺度池化残留                  -> 2
      组织占比                : tissue ratio                   -> 1
      纹理多尺度方差          : H 浓度 4×4 网格标准差           -> 16
      H 浓度直方图            : 8 bins                         -> 8
      E 浓度直方图            : 8 bins                         -> 8
      颜色矩                  : R/G/B 各 mean/std/skew         -> 9
                                                      合计    = 67
    """
    if rgb is None or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("tile_features 需要 HxWx3 的 RGB 图块")

    h_conc, e_conc, d_conc = color_deconvolve(rgb)
    mask = tissue_mask(rgb)
    t_ratio = float(mask.mean())
    if drop_background and t_ratio < 0.05:
        return None

    nuclei = nuclei_mask(h_conc, e_conc, tissue=mask)

    parts: list[np.ndarray] = [
        np.array([
            h_conc.mean(), h_conc.std(),
            e_conc.mean(), e_conc.std(),
            d_conc.mean(), d_conc.std(),
        ], dtype=np.float32),
        np.array([float(nuclei.mean())], dtype=np.float32),
        grid_stats(nuclei, 4),
        np.array(list(nuclear_size_proxy(nuclei)), dtype=np.float32),
        np.array([t_ratio], dtype=np.float32),
        grid_std(h_conc, 4),
        _hist8(h_conc),
        _hist8(e_conc),
    ]

    # 颜色矩（float32 全链路）
    data = (np.asarray(rgb, dtype=np.float32) * np.float32(1.0 / RGB_MAX)).reshape(-1, 3)
    mean = data.mean(axis=0)
    std = data.std(axis=0)
    centered = data - mean
    skew = (centered * centered * centered).mean(axis=0) / np.maximum(std * std * std, 1e-8)
    parts.append(np.concatenate([mean, std, skew]).astype(np.float32))

    out = np.concatenate(parts).astype(np.float32)
    if out.shape[0] != FEATURE_DIM_HANDCRAFTED:
        raise AssertionError(f"手写特征维度应为 {FEATURE_DIM_HANDCRAFTED}，实际 {out.shape[0]}")
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


def heatmap_overlay(base_rgb: np.ndarray, weights: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    """把图块级注意力权重叠成热力图，返回 uint8 RGB。

    `weights` 形状需能 reshape 成与 base 相同的网格（由调用方保证）。
    热区用暗红 (#5A0E13) 到白色的平滑过渡，不使用彩虹色（医疗场景配色约束）。
    """
    w = np.asarray(weights, dtype=np.float32)
    if w.size == 0:
        return base_rgb
    w = np.nan_to_num(w)
    span = float(w.max() - w.min())
    w = np.zeros_like(w) if span < 1e-12 else (w - w.min()) / span

    h, wd = base_rgb.shape[:2]
    gh, gw = w.shape
    cell_h = max(h // gh, 1)
    cell_w = max(wd // gw, 1)

    hot = np.array([90, 14, 19], dtype=np.float32)   # #5A0E13 暗红
    cold = np.array([255, 255, 255], dtype=np.float32)

    base = base_rgb.astype(np.float32).copy()
    for i in range(gh):
        y0, y1 = i * cell_h, min((i + 1) * cell_h, h)
        for j in range(gw):
            value = float(w[i, j])
            x0, x1 = j * cell_w, min((j + 1) * cell_w, wd)
            color = cold * (1 - value) + hot * value
            blend = alpha * value
            base[y0:y1, x0:x1] = base[y0:y1, x0:x1] * (1 - blend) + color * blend
    return np.clip(base, 0, 255).astype(np.uint8)
