"""可插拔图块编码器 + 许可证门禁（双源并行的技术落点）。

设计文档依据：第四章「模型技术方案」四轨路线与第十章 R2「开源权重许可风险」。

三层设计：
1. `EncoderSpec`         —— 编码器元数据（架构、参数量、许可证、是否可商用）。
2. `TileEncoder`          —— 编码接口实现：合成/ONNX/远端三类；
                             合成实现基于真实的颜色去卷积与核形态学特征，不是随机数。
3. `EncoderService`       —— 注册表 + 许可证门禁：
                             `deployment_env="product"` 时调用非商用编码器会抛
                             `LicenseViolation`，从工程上杜绝「实验指标漂亮、注册被否」。

重要：本模块的许可证字段必须如实填写。把非商用权重当成可商用使用，
会在三类证注册环节造成根本性返工 —— 这是方案中被标为「最易被忽视却最致命」的风险。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, ClassVar, Iterable, Sequence

import numpy as np

from app.core.config import BASE_DIR, settings
from app.services.image_utils import FEATURE_DIM_HANDCRAFTED, reinhard_normalize, tile_features

logger = logging.getLogger(__name__)


class LicenseViolation(RuntimeError):
    """在商用产品环境中使用非商用许可模型。"""

    def __init__(self, encoder_code: str, license_name: str, message: str = "") -> None:
        self.encoder_code = encoder_code
        self.license_name = license_name
        super().__init__(
            message
            or (
                f"许可门禁拦截：编码器 {encoder_code} 的许可证为「{license_name}」，"
                "不可用于商用产品环境。请切换到可商用编码器（双源并行策略），"
                "或在 research 环境中进行科研验证。"
            )
        )


# ----------------------------------------------------------------- 特征标定
# 手写特征各维度的物理量级，用于把不同量纲的特征压到可比范围后再做随机投影。
# 顺序与 image_utils.tile_features 的输出严格一一对应（合计 67 维）。
_FEATURE_SCALE = np.concatenate([
    np.full(6, 0.40),      # 0—5   染色通道 mean/std
    np.full(1, 0.25),      # 6     核占比
    np.full(16, 0.30),     # 7—22  4×4 核空间分布
    np.full(2, 0.50),      # 23—24 核尺寸/拥挤度代理
    np.full(1, 0.50),      # 25    组织占比
    np.full(16, 0.50),     # 26—41 H 浓度 4×4 网格标准差
    np.full(8, 0.03),      # 42—49 H 浓度直方图
    np.full(8, 0.03),      # 50—57 E 浓度直方图
    np.full(3, 60.0),      # 58—60 颜色均值
    np.full(3, 60.0),      # 61—63 颜色标准差
    np.full(3, 1.50),      # 64—66 颜色偏度
]).astype(np.float64)

assert _FEATURE_SCALE.shape[0] == FEATURE_DIM_HANDCRAFTED


@lru_cache(maxsize=32)
def _projection_matrix(seed: int, in_dim: int, out_dim: int) -> np.ndarray:
    """确定性高斯随机投影矩阵（Johnson–Lindenstrauss），按 (seed, 维度) 缓存。

    随机投影保距，因此判别性信息不会丢失；同时保证同一图块每次得到相同嵌入，
    满足审评对「特征可复现」的要求（特征包会记录 checksum）。
    """
    rng = np.random.default_rng(seed)
    matrix = rng.normal(0.0, 1.0 / np.sqrt(in_dim), size=(in_dim, out_dim))
    return matrix.astype(np.float32)


# ----------------------------------------------------------------- 编码器规格
@dataclass
class EncoderSpec:
    code: str
    name: str
    family: str
    arch: str
    params_m: float
    embedding_dim: int
    tile_size: int
    target_mpp: float
    pretrain_scale: str
    license_code: str
    license_name: str
    commercial_usable: bool
    research_only: bool
    impl: str = "synthetic"
    license_note: str = ""
    source_url: str = ""
    input_norm: str = "reinhard"
    is_self_developed: bool = False
    weight_path: str = ""
    onnx_path: str = ""
    onnx_sha256: str = ""
    """ONNX 权重文件的 SHA256。安装与校验都以此为准，防止"权重被换过但没人知道"。"""
    input_norm_onnx: str = ""
    """ONNX 模型使用的归一化预设：imagenet / half / unit / none（见 onnx_encoder）。"""
    input_layout: str = ""
    """输入张量布局 NCHW / NHWC。留空则从计算图推断。"""
    resize_mode: str = ""
    """图块缩放到模型输入尺寸时的插值方式：bilinear / bicubic / lanczos / nearest。"""
    batch_size: int = 0
    """推理批大小。0 表示用后端默认（动态 batch 时按 16）。"""
    weight_url: str = ""
    """权重下载地址（清单里登记）。院内离线环境可留空并改用本地安装。"""
    benchmark_auroc: float = 0.0
    benchmark_note: str = ""
    status: str = "enabled"
    projection_seed: int = 20260101
    sort_order: int = 0

    # 派生字段：由其它字段算出来、**不落库**。放进 to_dict 是为了 API/前端方便，
    # 持久化时必须剔除 —— 冗余派生列迟早会和源字段不一致。
    DERIVED_FIELDS: ClassVar[tuple[str, ...]] = ("onnx_installed",)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "family": self.family,
            "arch": self.arch,
            "params_m": self.params_m,
            "embedding_dim": self.embedding_dim,
            "tile_size": self.tile_size,
            "target_mpp": self.target_mpp,
            "pretrain_scale": self.pretrain_scale,
            "license_code": self.license_code,
            "license_name": self.license_name,
            "commercial_usable": self.commercial_usable,
            "research_only": self.research_only,
            "impl": self.impl,
            "license_note": self.license_note,
            "source_url": self.source_url,
            "input_norm": self.input_norm,
            "is_self_developed": self.is_self_developed,
            "onnx_path": self.onnx_path,
            "onnx_sha256": self.onnx_sha256,
            "onnx_installed": bool(self.onnx_path),
            "input_norm_onnx": self.input_norm_onnx,
            "input_layout": self.input_layout,
            "resize_mode": self.resize_mode,
            "batch_size": self.batch_size,
            "weight_url": self.weight_url,
            "status": self.status,
            "benchmark_auroc": self.benchmark_auroc,
            "benchmark_note": self.benchmark_note,
            "sort_order": self.sort_order,
        }

    def to_row_dict(self) -> dict[str, Any]:
        """用于写入 ORM 表：去掉派生字段。

        与 `to_dict()` 分开，是为了让"给接口看的"和"往库里写的"两件事显式不同。
        混在一起的结果就是某个派生字段被写进表里，然后永远没人负责更新它。
        """
        return {k: v for k, v in self.to_dict().items() if k not in self.DERIVED_FIELDS}


BUILTIN_ENCODERS: list[EncoderSpec] = [
    # ---------------- 可商用路线（商用主线可用）----------------
    EncoderSpec(
        code="hibou-b-synth", name="Hibou-B 图块编码器", family="Hibou", arch="ViT-B/14",
        params_m=86.0, embedding_dim=128, tile_size=128, target_mpp=0.5,
        pretrain_scale="公开病理图块集（约 100 万图块）",
        license_code="Apache-2.0", license_name="Apache License 2.0",
        commercial_usable=True, research_only=False, impl="synthetic",
        license_note="允许商用与再分发，是商用主线的默认选择。",
        source_url="https://huggingface.co/histai/hibou-b",
        benchmark_auroc=0.905, benchmark_note="内部验证集（合成演示数据）；商用可用路线基线",
        projection_seed=20260101, sort_order=10,
    ),
    EncoderSpec(
        code="hibou-l-synth", name="Hibou-L 图块编码器", family="Hibou", arch="ViT-L/14",
        params_m=303.0, embedding_dim=256, tile_size=128, target_mpp=0.5,
        pretrain_scale="公开病理图块集（约 100 万图块）",
        license_code="Apache-2.0", license_name="Apache License 2.0",
        commercial_usable=True, research_only=False, impl="synthetic",
        license_note="可商用，参数量更大、精度更高，但推理成本上升。",
        source_url="https://huggingface.co/histai/hibou-l",
        benchmark_auroc=0.918, benchmark_note="内部验证集（合成演示数据）",
        projection_seed=20260102, sort_order=20,
    ),
    # ---------------- 自研路线（可彻底消除许可风险）----------------
    EncoderSpec(
        code="sh-encoder-b0", name="蓝天健康自研编码器 B0", family="SmartHealth-SelfDev", arch="ViT-B 量级（轻量）",
        params_m=85.0, embedding_dim=128, tile_size=128, target_mpp=0.5,
        pretrain_scale="院内自有未标注切片（自监督，目标 3—5 万张）",
        license_code="Proprietary", license_name="公司自有知识产权",
        commercial_usable=True, research_only=False, impl="synthetic",
        license_note="自监督预训练产物，许可风险为零；M4 里程碑要求第 16 个月内完成对参照权重的替换。",
        is_self_developed=True,
        benchmark_auroc=0.891, benchmark_note="孵化中；目标「性能不劣于参照权重」",
        projection_seed=20260201, sort_order=30,
    ),
    EncoderSpec(
        code="sh-encoder-l1", name="蓝天健康自研编码器 L1", family="SmartHealth-SelfDev", arch="ViT-L 量级",
        params_m=300.0, embedding_dim=256, tile_size=128, target_mpp=0.5,
        pretrain_scale="院内自有未标注切片（自监督，目标 3—5 万张）",
        license_code="Proprietary", license_name="公司自有知识产权",
        commercial_usable=True, research_only=False, impl="synthetic",
        license_note="自研路线的中期目标版本，P2 阶段并行孵化。",
        is_self_developed=True, status="incubating",
        benchmark_auroc=0.0, benchmark_note="尚未产出可评测版本",
        projection_seed=20260202, sort_order=40,
    ),
    # ---------------- 非商用路线（仅限研究/探索线，禁止进入产品）----------------
    EncoderSpec(
        code="uni2-h", name="UNI2-h 图块编码器", family="UNI", arch="DINOv2 ViT-H/14",
        params_m=681.0, embedding_dim=512, tile_size=128, target_mpp=0.5,
        pretrain_scale="10 万张 WSI / 1 亿+ 图块（Mass-100K 等）",
        license_code="CC-BY-NC-ND-4.0", license_name="CC BY-NC-ND 4.0",
        commercial_usable=False, research_only=True, impl="synthetic",
        license_note="非商用 + 禁止演绎。指标优秀但**不可用于商用产品**，是典型的许可陷阱。",
        source_url="https://huggingface.co/MahmoodLab/UNI2-h",
        benchmark_auroc=0.968, benchmark_note="公开基准表现最强一档，但许可不可商用",
        projection_seed=20260301, sort_order=50,
    ),
    EncoderSpec(
        code="virchow2", name="Virchow2 图块编码器", family="Virchow", arch="ViT-H/14",
        params_m=632.0, embedding_dim=512, tile_size=128, target_mpp=0.5,
        pretrain_scale="150 万张 WSI / 20 亿图块",
        license_code="CC-BY-NC-4.0", license_name="CC BY-NC 4.0",
        commercial_usable=False, research_only=True, impl="synthetic",
        license_note="非商用授权，仅可用于科研与探索线验证。",
        source_url="https://huggingface.co/paige-ai/Virchow2",
        benchmark_auroc=0.961, benchmark_note="大规模预训练，泛化好，但许可不可商用",
        projection_seed=20260302, sort_order=60,
    ),
    EncoderSpec(
        code="gigapath-tile", name="Prov-GigaPath 图块编码器", family="Prov-GigaPath", arch="ViT-g/14",
        params_m=1100.0, embedding_dim=512, tile_size=128, target_mpp=0.5,
        pretrain_scale="17 万张 WSI / 13 亿图块（Providence 医疗系统）",
        license_code="Prov-GigaPath-Research", license_name="研究用途许可（非商用）",
        commercial_usable=False, research_only=True, impl="synthetic",
        license_note="权重以研究用途发布，商用需另行授权。",
        source_url="https://huggingface.co/prov-gigapath/prov-gigapath",
        benchmark_auroc=0.955, benchmark_note="含 LongNet 全切片扩展，探索线参考",
        projection_seed=20260303, sort_order=70,
    ),
    EncoderSpec(
        code="conch-vl", name="CONCH 视觉-语言编码器", family="CONCH", arch="ViT-B/16 + Text",
        params_m=116.0, embedding_dim=256, tile_size=128, target_mpp=0.5,
        pretrain_scale="117 万图块-文本对",
        license_code="CC-BY-NC-ND-4.0", license_name="CC BY-NC-ND 4.0",
        commercial_usable=False, research_only=True, impl="synthetic",
        license_note="非商用，且支持图块-文本对齐，适合探索线的多模态对齐验证。",
        source_url="https://huggingface.co/MahmoodLab/CONCH",
        benchmark_auroc=0.940, benchmark_note="零样本分类能力强，但仅供研究",
        projection_seed=20260304, sort_order=80,
    ),
]

BUILTIN_BY_CODE: dict[str, EncoderSpec] = {spec.code: spec for spec in BUILTIN_ENCODERS}


# -------------------------------------------------------------------- 编码器
class TileEncoder:
    """图块编码器接口。`encode_tiles` 返回 (N, D) 的 L2 归一化嵌入。"""

    def __init__(self, spec: EncoderSpec) -> None:
        self.spec = spec

    @property
    def embedding_dim(self) -> int:
        return self.spec.embedding_dim

    @property
    def tile_size(self) -> int:
        return self.spec.tile_size

    def encode_tiles(self, tiles: Sequence[np.ndarray]) -> np.ndarray:  # pragma: no cover - 抽象
        raise NotImplementedError

    def encode_tile(self, tile: np.ndarray) -> np.ndarray:
        return self.encode_tiles([tile])[0]


class SyntheticFeatureEncoder(TileEncoder):
    """内置编码器：颜色去卷积与核形态学特征 → 标准化 → 确定性随机投影。

    它处理的是**真实图像内容**：同一张图块每次得到同一嵌入，病理形态变化会真实
    反映到嵌入空间中（病灶区的核密度、核浆比特征显著偏高）。因此下游的
    ABMIL 训练、注意力定位、AUROC 评测全部是有意义的计算，而非随机占位。
    """

    def __init__(self, spec: EncoderSpec, layout: str | None = None) -> None:
        super().__init__(spec)
        self._matrix = _projection_matrix(spec.projection_seed, FEATURE_DIM_HANDCRAFTED, spec.embedding_dim)
        self._layout = layout
        self._cache: dict[int, np.ndarray] = {}

    def raw_features(self, tile: np.ndarray) -> np.ndarray:
        features = tile_features(tile)
        if features is None:  # 背景块
            return np.zeros(FEATURE_DIM_HANDCRAFTED, dtype=np.float64)
        return features

    def standardize(self, features: np.ndarray) -> np.ndarray:
        scaled = np.tanh(np.asarray(features, dtype=np.float64) / _FEATURE_SCALE)
        return scaled

    def encode_tiles(self, tiles: Sequence[np.ndarray]) -> np.ndarray:
        if not tiles:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        prepared: list[np.ndarray] = []
        for tile in tiles:
            img = tile
            if self.spec.input_norm == "reinhard":
                img = reinhard_normalize(tile)
            prepared.append(self.standardize(self.raw_features(img)))
        stacked = np.stack(prepared, axis=0).astype(np.float32)  # (N, 67)
        projected = stacked @ self._matrix  # (N, D)
        norms = np.linalg.norm(projected, axis=1, keepdims=True)
        norms[norms < 1e-8] = 1.0
        return (projected / norms).astype(np.float32)

    def describe(self) -> dict[str, Any]:
        return {
            "impl": "synthetic-feature-projection",
            "feature_dim": FEATURE_DIM_HANDCRAFTED,
            "projection_seed": self.spec.projection_seed,
            "input_norm": self.spec.input_norm,
            "note": "颜色去卷积 + 核形态学特征，确定性可复现；生产环境替换为权重推理。",
        }


# ONNX 编码器的实现放在独立模块，便于单独测试与演进。
# 这里保留同名导出，保证既有引用（含 EncoderService.resolve）不改动。
from app.services.onnx_encoder import (  # noqa: E402  isort:skip
    NORMALIZATION_PRESETS,
    OnnxModelInfo,
    OnnxTileEncoder,
    OnnxUnavailable,
)


# -------------------------------------------------------------------- 服务
class EncoderService:
    """编码器注册表与许可证门禁。"""

    def __init__(self) -> None:
        self._specs: dict[str, EncoderSpec] = dict(BUILTIN_BY_CODE)
        self._instances: dict[str, TileEncoder] = {}

    # ------------------------------------------------------------- 注册表
    def sync_from_registry(self, *, verbose: bool = False) -> dict:
        """把模型清单（configs/model_registry.json）里**已安装**的权重接进注册表。

        为什么需要这一步：
        内置声明（BUILTIN_ENCODERS）描述的是"这类模型长什么样"，
        而模型清单描述的是"本院实际装了哪一份权重、校验和是多少"。
        两者解耦，才能做到「换权重不改代码」—— 现场只需要装文件 + 更新清单。

        返回同步摘要，供 /models/encoders 与 doctor 展示。
        """
        try:
            from app.services import model_registry as registry
        except Exception as exc:  # pragma: no cover
            logger.warning("模型清单不可用，跳过同步：%s", exc)
            return {"synced": 0, "skipped": 0, "error": str(exc)}

        manifest = registry.load_manifest()
        synced: list[str] = []
        skipped: list[str] = []
        for raw in manifest.get("models", []):
            code = str(raw.get("code") or "")
            if not code:
                continue
            installed_path = str(raw.get("installed_path") or "")
            absolute = (BASE_DIR / installed_path) if installed_path else None
            if not absolute or not absolute.exists():
                skipped.append(code)
                continue

            spec = self._specs.get(code)
            if spec is None:
                spec = EncoderSpec(
                    code=code,
                    name=str(raw.get("name") or code),
                    family=str(raw.get("family") or "SmartHealth"),
                    arch=str(raw.get("arch") or "unknown"),
                    params_m=float(raw.get("params_m") or 0.0),
                    embedding_dim=int(raw.get("embedding_dim") or 0) or 128,
                    tile_size=int(raw.get("tile_size") or 128),
                    target_mpp=float(raw.get("target_mpp") or 0.5),
                    pretrain_scale=str(raw.get("note") or "")[:80],
                    license_code=str(raw.get("license_code") or ""),
                    license_name=str(raw.get("license_name") or ""),
                    commercial_usable=bool(raw.get("commercial_usable")),
                    research_only=bool(raw.get("research_only")),
                    is_self_developed=bool(raw.get("is_self_developed")),
                    sort_order=900,
                )
                self._specs[code] = spec
            spec.impl = "onnx"
            spec.onnx_path = str(absolute)
            spec.onnx_sha256 = str(raw.get("installed_sha256") or raw.get("sha256") or "")
            spec.input_norm_onnx = str(raw.get("input_norm") or "half")
            spec.input_layout = str(raw.get("input_layout") or "NCHW")
            spec.resize_mode = str(raw.get("resize_mode") or "bilinear")
            spec.batch_size = int(raw.get("batch_size") or 0)
            synced.append(code)

        self._instances.clear()   # 权重换了，缓存实例必须失效
        if verbose and synced:
            logger.info("模型清单同步：接入 %d 个已安装权重（%s）", len(synced), ", ".join(synced))
        return {"synced": len(synced), "synced_codes": synced,
                "not_installed": len(skipped), "not_installed_codes": skipped}

    def all_specs(self) -> list[EncoderSpec]:
        return sorted(self._specs.values(), key=lambda s: s.sort_order)

    def onnx_diagnostics(self) -> dict:
        """回报每个 ONNX 编码器的"是不是真在跑真实权重"。"""
        report: list[dict] = []
        for spec in self.all_specs():
            if spec.impl != "onnx" or not spec.onnx_path:
                continue
            try:
                encoder = self.resolve(spec.code, strict=False)
                if hasattr(encoder, "describe"):
                    report.append(encoder.describe())
                else:
                    report.append({"encoder_code": spec.code,
                                   "using_real_model": False,
                                   "note": "实例不是 ONNX 后端"})
            except Exception as exc:
                report.append({"encoder_code": spec.code, "using_real_model": False,
                               "error": f"{type(exc).__name__}: {exc}"})
        return {
            "total": len(report),
            "using_real_model": sum(1 for r in report if r.get("using_real_model")),
            "mismatched_dims": [r["encoder_code"] for r in report if r.get("dimension_mismatch")],
            "encoders": report,
        }

    def get_spec(self, code: str) -> EncoderSpec | None:
        return self._specs.get(code)

    def require_spec(self, code: str) -> EncoderSpec:
        spec = self._specs.get(code)
        if spec is None:
            raise KeyError(f"未注册的编码器：{code}")
        return spec

    def register(self, spec: EncoderSpec) -> EncoderSpec:
        self._specs[spec.code] = spec
        self._instances.pop(spec.code, None)
        return spec

    def upsert_from_dict(self, payload: dict[str, Any]) -> EncoderSpec:
        code = str(payload.get("code") or "").strip()
        if not code:
            raise ValueError("编码器 code 不能为空")
        base = self._specs.get(code)
        defaults = dict(
            name=code, family="", arch="", params_m=0.0, embedding_dim=128, tile_size=128,
            target_mpp=0.5, pretrain_scale="", license_code="", license_name="",
            commercial_usable=False, research_only=True, impl="synthetic",
        )
        merged = {**(base.to_dict() if base else defaults), **{k: v for k, v in payload.items() if v is not None}}
        merged["code"] = code
        allowed = {f for f in EncoderSpec.__dataclass_fields__}
        filtered = {k: v for k, v in merged.items() if k in allowed}
        for key in ("commercial_usable", "research_only", "is_self_developed"):
            if key in filtered:
                filtered[key] = bool(filtered[key])
        spec = EncoderSpec(**filtered)
        return self.register(spec)

    # --------------------------------------------------------- 许可证门禁
    def assert_commercial_usable(self, code: str, deployment_env: str | None = None) -> EncoderSpec:
        """许可证门禁。product 环境使用非商用编码器直接抛 LicenseViolation。"""
        spec = self.require_spec(code)
        env = (deployment_env or settings.deployment_env or "research").lower()
        if env == "product" and not spec.commercial_usable and settings.strict_license_gate:
            raise LicenseViolation(code, spec.license_name)
        return spec

    def license_audit(self, deployment_env: str | None = None) -> dict[str, Any]:
        """许可风险体检：列出在当前环境下可用的 / 被拦截的编码器。"""
        env = (deployment_env or settings.deployment_env or "research").lower()
        allowed, blocked = [], []
        for spec in self.all_specs():
            record = {
                "code": spec.code,
                "name": spec.name,
                "license_name": spec.license_name,
                "commercial_usable": spec.commercial_usable,
                "research_only": spec.research_only,
                "is_self_developed": spec.is_self_developed,
                "license_note": spec.license_note,
            }
            if env == "product" and not spec.commercial_usable:
                blocked.append({**record, "reason": "非商用许可证，product 环境禁止调用"})
            else:
                allowed.append(record)
        self_developed = [s.code for s in self.all_specs() if s.is_self_developed]
        return {
            "deployment_env": env,
            "strict_gate": settings.strict_license_gate,
            "total": len(self.all_specs()),
            "allowed": allowed,
            "blocked": blocked,
            "allowed_count": len(allowed),
            "blocked_count": len(blocked),
            "self_developed_encoders": self_developed,
            "self_developed_ready": [
                s.code for s in self.all_specs()
                if s.is_self_developed and s.status == "enabled" and s.benchmark_auroc > 0
            ],
            "risk_statement": (
                "商用主线只能使用 commercial_usable=True 的编码器；"
                "自研编码器（sh-encoder-*）是彻底消除许可风险的唯一终局方案。"
            ),
        }

    # ------------------------------------------------------------- 实例化
    def resolve(self, code: str, deployment_env: str | None = None, strict: bool | None = None) -> TileEncoder:
        """获取编码器实例（含门禁与缓存）。"""
        spec = self.require_spec(code)
        env = (deployment_env or settings.deployment_env or "research").lower()
        gate_enabled = settings.strict_license_gate if strict is None else strict
        if gate_enabled and env == "product" and not spec.commercial_usable:
            raise LicenseViolation(code, spec.license_name)

        cached = self._instances.get(code)
        if cached is not None:
            return cached

        if spec.impl == "onnx" and spec.onnx_path:
            encoder: TileEncoder = OnnxTileEncoder(
                spec, fallback=SyntheticFeatureEncoder(spec),
                batch_size=spec.batch_size or None,
            )
            if not getattr(encoder, "is_real_model", False):
                logger.warning(
                    "编码器 %s 声明为 onnx 但未能加载真实权重，已回退内置实现。"
                    "请执行 python scripts/model_registry.py verify %s 排查。",
                    spec.code, spec.code,
                )
        elif spec.impl == "remote" and spec.weight_path:
            encoder = SyntheticFeatureEncoder(spec)
            logger.warning("远端编码器 %s 暂以本地实现代替（weight_path=%s）", code, spec.weight_path)
        else:
            encoder = SyntheticFeatureEncoder(spec)
        self._instances[code] = encoder
        return encoder

    def encode_batch(self, code: str, tiles: Iterable[np.ndarray], deployment_env: str | None = None) -> np.ndarray:
        encoder = self.resolve(code, deployment_env=deployment_env)
        return encoder.encode_tiles(list(tiles))

    def commercial_default(self) -> str:
        """返回当前环境下可用的默认可商用编码器。"""
        spec = self._specs.get(settings.default_encoder)
        if spec and spec.commercial_usable:
            return spec.code
        for candidate in self.all_specs():
            if candidate.commercial_usable and not candidate.is_self_developed:
                return candidate.code
        return settings.default_encoder


encoder_service = EncoderService()
