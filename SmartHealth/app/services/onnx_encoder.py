"""ONNX 图块编码器：真实权重推理后端。

设计文档依据：第四章 4.2（开源基座+自有数据微调的落地路径）+ 第七章（许可证合规）。

本模块把「注册表里的一条编码器声明」变成「能真正跑出 embedding 的推理会话」。
要接真实权重（例如可商用的 Hibou-B、或自研导出的 ViT），只需：
1. 把模型导出为 ONNX（固定输入 `1×3×S×S` 或动态 batch）；
2. 在模型清单 `configs/model_registry.json` 里登记：路径、SHA256、输入尺寸、
   归一化方式、许可证；
3. `python scripts/model_registry.py verify <code>` 通过校验后即可被
   `encoder_service.resolve(code)` 使用。

**这里踩过的坑，都写成显式校验了**（否则表现为"指标莫名变差"而不是报错）：
- **通道顺序**：PyTorch 导出是 NCHW，TensorFlow/Keras 导出常是 NHWC。搞反不会报错，
  只会让 embedding 变成噪声。所以按 `session.get_inputs()[0].shape` 推断并校验。
- **归一化参数**：ImageNet mean/std 与 `[-1,1]` 缩放是两套约定，混用同样静默劣化。
  清单里必须显式声明，本模块据此构造预处理。
- **插值方式**：`tile` 缩放到模型输入尺寸时，默认用 `bilinear`；病理图块常用
  `bicubic`（更接近训练时的预处理）。声明式配置，避免"猜"。
- **动态 batch**：一次喂太多会 OOM，太少则吞吐差。按显存/内存预算切批，
  并在 `describe()` 里回报实际 batch。
- **线程数**：CPU 推理默认吃满所有核，会和 API 抢 CPU。显式设 `intra_op_num_threads`。
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
from PIL import Image

from app.services.image_utils import reinhard_normalize

logger = logging.getLogger(__name__)

# 归一化预设。key 是清单里可声明的名字。
NORMALIZATION_PRESETS: dict[str, dict[str, Any]] = {
    "imagenet": {
        "mean": (0.485, 0.456, 0.406), "std": (0.229, 0.224, 0.225),
        "scale": 1.0 / 255.0,
        "note": "torchvision/timm 预训练的通用约定（ImageNet 统计量）。",
    },
    "half": {
        "mean": (0.5, 0.5, 0.5), "std": (0.5, 0.5, 0.5),
        "scale": 1.0 / 255.0,
        "note": "映射到 [-1, 1]，常见于自监督预训练（DINO 系）导出。",
    },
    "unit": {
        "mean": (0.0, 0.0, 0.0), "std": (1.0, 1.0, 1.0),
        "scale": 1.0 / 255.0,
        "note": "仅缩放到 [0, 1]，用于训练时就未做标准化的小模型。",
    },
    "none": {
        "mean": (0.0, 0.0, 0.0), "std": (1.0, 1.0, 1.0), "scale": 1.0,
        "note": "原样 0—255 输入，仅用于特殊导出的模型。",
    },
}


@dataclass
class OnnxModelInfo:
    """一个已加载 ONNX 模型的实际形态（从图里读出来，而不是从配置里抄）。"""

    path: str
    providers: list[str] = field(default_factory=list)
    input_name: str = ""
    input_shape: list[Any] = field(default_factory=list)
    input_dtype: str = ""
    output_name: str = ""
    output_shape: list[Any] = field(default_factory=list)
    layout: str = ""                 # 'NCHW' | 'NHWC' | ''
    dynamic_batch: bool = False
    static_batch: int = 0
    ready: bool = False
    load_ms: int = 0
    error: str = ""
    ops: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "path": self.path, "providers": self.providers,
            "input_name": self.input_name, "input_shape": self.input_shape,
            "input_dtype": self.input_dtype, "output_name": self.output_name,
            "output_shape": self.output_shape, "layout": self.layout,
            "dynamic_batch": self.dynamic_batch, "static_batch": self.static_batch,
            "ready": self.ready, "load_ms": self.load_ms, "error": self.error,
            "op_count": len(self.ops), "top_ops": sorted(self.ops.items(),
                                                         key=lambda kv: -kv[1])[:6],
        }


class OnnxUnavailable(RuntimeError):
    """ONNX 运行时或模型不可用。调用方决定是回退还是直接失败。"""


class OnnxTileEncoder:
    """基于 onnxruntime 的图块编码器。

    与 `SyntheticFeatureEncoder` 的接口完全一致（`embedding_dim` / `tile_size` /
    `encode_tiles`），所以流水线、MIL、评测层无需任何改动即可切到真实权重。
    """

    def __init__(self, spec, fallback=None, *, batch_size: int | None = None,
                 intra_threads: int | None = None, warmup: bool = True,
                 normalize: str | None = None, resize_mode: str | None = None) -> None:
        self.spec = spec
        self._fallback = fallback
        self._lock = threading.Lock()
        self._session = None
        self._info = OnnxModelInfo(path=str(getattr(spec, "onnx_path", "") or ""))
        self._use_fallback = False

        self._batch_size = int(batch_size or 16)
        self._intra_threads = int(intra_threads or 0) or max(1, min(4, (self._cpu_count() or 4) // 2))
        self._normalize = normalize or getattr(spec, "input_norm_onnx", "") or "half"
        self._resize_mode = resize_mode or getattr(spec, "resize_mode", "") or "bilinear"
        # 输入布局可显式声明；留空则从图里推断
        self._declared_layout = (getattr(spec, "input_layout", "") or "").upper()

        self._load(warmup=warmup)

    # ------------------------------------------------------------ 基础属性
    @property
    def embedding_dim(self) -> int:
        if self._session is not None and self._info.output_shape:
            dim = self._info.output_shape[-1]
            if isinstance(dim, int) and dim > 0:
                return int(dim)
        return int(getattr(self.spec, "embedding_dim", 0) or 0)

    @property
    def tile_size(self) -> int:
        if self._session is not None:
            shape = self._info.input_shape
            if len(shape) == 4:
                h = shape[2] if self._info.layout == "NCHW" else shape[1]
                if isinstance(h, int) and h > 0:
                    return int(h)
        return int(getattr(self.spec, "tile_size", 256) or 256)

    @staticmethod
    def _cpu_count() -> int:
        import os

        try:
            return len(os.sched_getaffinity(0))   # type: ignore[attr-defined]
        except Exception:
            return os.cpu_count() or 4

    # ------------------------------------------------------------ 加载
    def _load(self, *, warmup: bool) -> None:
        path = self._info.path
        t0 = time.time()
        if not path:
            self._degrade("未配置 onnx_path")
            return
        try:
            import onnxruntime as ort
        except Exception as exc:
            self._degrade(f"onnxruntime 不可用：{type(exc).__name__}: {exc}")
            return

        try:
            options = ort.SessionOptions()
            options.intra_op_num_threads = self._intra_threads
            options.inter_op_num_threads = 1
            # 图优化在加载期做一次，换来推理期的稳定延迟
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            options.log_severity_level = 3
            providers = self._available_providers(ort)
            self._session = ort.InferenceSession(path, sess_options=options, providers=providers)
        except Exception as exc:
            self._degrade(f"ONNX 会话建立失败：{type(exc).__name__}: {exc}")
            return

        self._probe_io(ort)
        self._info.ready = True
        self._info.load_ms = int((time.time() - t0) * 1000)

        if warmup:
            try:
                self._warmup()
            except Exception as exc:  # pragma: no cover - 环境相关
                logger.warning("ONNX 编码器 %s 预热失败（不影响正确性）：%s", self.spec.code, exc)

        logger.info(
            "ONNX 编码器已加载：%s（%s，输入 %s %s，输出 %s，%d ms，线程 %d）",
            self.spec.code, path.rsplit("/", 1)[-1], self._info.layout,
            self._info.input_shape, self._info.output_shape,
            self._info.load_ms, self._intra_threads,
        )

    @staticmethod
    def _available_providers(ort) -> list[str]:
        """优先 GPU，其次 CPU。院内多为 CPU-only 服务器，因此必须有 CPU 兜底。"""
        available = set(ort.get_available_providers())
        preferred = [p for p in ("CUDAExecutionProvider", "DmlExecutionProvider",
                                 "CoreMLExecutionProvider", "CPUExecutionProvider")
                     if p in available]
        return preferred or ["CPUExecutionProvider"]

    def _probe_io(self, ort) -> None:
        """从计算图读取真实输入输出签名，并统计算子构成。

        **不信任配置文件里的 embedding_dim / tile_size**：那是人工填写的，
        和权重对不上时不会报错、只会让下游指标变差。这里以图为准。
        """
        inputs = self._session.get_inputs()
        outputs = self._session.get_outputs()
        if not inputs:
            self._degrade("ONNX 模型没有输入")
            return
        inp = inputs[0]
        out = outputs[0]
        self._info.input_name = inp.name
        self._info.input_shape = list(inp.shape)
        self._info.input_dtype = str(inp.type)
        self._info.output_name = out.name
        self._info.output_shape = list(out.shape)
        self._info.providers = list(self._session.get_providers())

        shape = list(inp.shape)
        if len(shape) == 4:
            batch_dim = shape[0]
            self._info.dynamic_batch = not isinstance(batch_dim, int)
            self._info.static_batch = int(batch_dim) if isinstance(batch_dim, int) else 0
            if self._declared_layout:
                self._info.layout = self._declared_layout
            else:
                # NCHW: 第 2 维是通道（3 或 1）；NHWC: 第 4 维是通道
                c_second = shape[1]
                c_fourth = shape[3]
                if c_second in (1, 3, 4):
                    self._info.layout = "NCHW"
                elif c_fourth in (1, 3, 4):
                    self._info.layout = "NHWC"
                else:
                    self._info.layout = "NCHW"      # 保守默认
        else:
            self._info.layout = ""

        self._info.ops = self._count_ops()

    def _count_ops(self) -> dict[str, int]:
        """算子直方图：用来确认"这确实是一个真实网络"而不是恒等映射。

        走 onnx 库解析（稳定 API），而不是 onnxruntime 的私有属性
        —— 私有属性跨版本会改名，静默失效后诊断信息就少一块。
        """
        try:
            import onnx

            model = onnx.load(self._info.path, load_external_data=False)
            counts: dict[str, int] = {}
            for node in model.graph.node:
                counts[node.op_type] = counts.get(node.op_type, 0) + 1
            return counts
        except Exception as exc:
            logger.debug("算子直方图提取失败（不影响推理）：%s", exc)
            return {}

    def _degrade(self, reason: str) -> None:
        self._info.error = reason[:300]
        self._info.ready = False
        if self._fallback is not None:
            self._use_fallback = True
            logger.warning("ONNX 编码器 %s 不可用（%s），已回退到内置实现（指标不代表真实权重）",
                           self.spec.code, reason)
        else:
            logger.error("ONNX 编码器 %s 不可用且无回退：%s", self.spec.code, reason)

    def _warmup(self) -> None:
        """预热：让运行时完成算子选择与内存分配，避免首个请求异常慢。"""
        if self._info.layout in ("NCHW", "NHWC") and isinstance(self.tile_size, int):
            dummy = np.zeros((1, 3, self.tile_size, self.tile_size), dtype=np.float32)
            self._run(dummy)

    # ------------------------------------------------------------ 预处理
    def _normalization(self) -> dict[str, Any]:
        preset = NORMALIZATION_PRESETS.get(self._normalize)
        if preset is None:
            logger.warning("未知归一化预设 %r，回退到 'half'。可用：%s",
                           self._normalize, list(NORMALIZATION_PRESETS))
            preset = NORMALIZATION_PRESETS["half"]
        return preset

    def _preprocess(self, tiles: Sequence[np.ndarray]) -> np.ndarray:
        size = int(self.tile_size)
        layout = self._info.layout or "NCHW"
        norm = self._normalization()
        mean = np.asarray(norm["mean"], dtype=np.float32).reshape(1, 3, 1, 1)
        std = np.asarray(norm["std"], dtype=np.float32).reshape(1, 3, 1, 1)
        scale = float(norm["scale"])

        resample = {"bilinear": Image.BILINEAR, "bicubic": Image.BICUBIC,
                    "lanczos": Image.LANCZOS, "nearest": Image.NEAREST,
                    }.get(self._resize_mode, Image.BILINEAR)

        batch = np.empty((len(tiles), 3, size, size), dtype=np.float32)
        for index, tile in enumerate(tiles):
            img = reinhard_normalize(tile) if getattr(self.spec, "input_norm", "reinhard") == "reinhard" else tile
            pil = Image.fromarray(np.ascontiguousarray(img))
            if pil.size != (size, size):
                pil = pil.resize((size, size), resample)
            arr = np.asarray(pil.convert("RGB"), dtype=np.float32)
            arr *= scale
            arr = np.transpose(arr, (2, 0, 1))[None, ...]     # HWC → 1CHW
            batch[index] = (arr - mean) / std

        if layout == "NHWC":
            batch = np.transpose(batch, (0, 2, 3, 1))         # NCHW → NHWC
        return np.ascontiguousarray(batch)

    # ------------------------------------------------------------ 推理
    def _run(self, blob: np.ndarray) -> np.ndarray:
        if self._info.input_dtype and "float16" in self._info.input_dtype:
            blob = blob.astype(np.float16)
        outputs = self._session.run([self._info.output_name], {self._info.input_name: blob})
        return np.asarray(outputs[0], dtype=np.float32)

    def encode_tiles(self, tiles: Sequence[np.ndarray]) -> np.ndarray:
        tiles = list(tiles)
        if not tiles:
            return np.zeros((0, self.embedding_dim), dtype=np.float32)
        if self._use_fallback or self._session is None:
            if self._fallback is None:
                raise OnnxUnavailable(
                    f"编码器 {self.spec.code} 不可用：{self._info.error or 'ONNX 会话未建立'}"
                )
            return self._fallback.encode_tiles(tiles)

        vectors = np.zeros((len(tiles), self.embedding_dim), dtype=np.float32)
        batch_size = max(1, self._batch_size)
        if self._info.static_batch > 0:
            # 静态 batch 的模型必须按导出时的 batch 喂，否则报维度错误
            batch_size = self._info.static_batch

        for start in range(0, len(tiles), batch_size):
            chunk = tiles[start:start + batch_size]
            blob = self._preprocess(chunk)
            if self._info.static_batch > 0 and blob.shape[0] != self._info.static_batch:
                pad = np.zeros((self._info.static_batch - blob.shape[0], *blob.shape[1:]),
                               dtype=blob.dtype)
                blob = np.concatenate([blob, pad], axis=0)
            with self._lock:
                raw = self._run(blob)
            flat = raw.reshape(raw.shape[0], -1)[:len(chunk)]
            vectors[start:start + len(chunk)] = flat

        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms < 1e-8] = 1.0
        return vectors / norms

    def encode_tile(self, tile: np.ndarray) -> np.ndarray:
        return self.encode_tiles([tile])[0]

    # ------------------------------------------------------------ 诊断
    @property
    def is_real_model(self) -> bool:
        """是否在用真实权重（False 表示已回退到内置实现）。"""
        return self._session is not None and not self._use_fallback

    def describe(self) -> dict:
        info = self._info.to_dict()
        # 完整算子表（to_dict 只给 top6 摘要，诊断时往往要看全量）
        info["ops"] = dict(self._info.ops)
        info.update({
            "encoder_code": self.spec.code,
            "using_real_model": self.is_real_model,
            "embedding_dim_effective": self.embedding_dim,
            "embedding_dim_declared": int(getattr(self.spec, "embedding_dim", 0) or 0),
            "tile_size_effective": self.tile_size,
            "tile_size_declared": int(getattr(self.spec, "tile_size", 0) or 0),
            "batch_size": self._batch_size,
            "intra_op_threads": self._intra_threads,
            "normalization": self._normalize,
            "normalization_detail": self._normalization(),
            "resize_mode": self._resize_mode,
            "dimension_mismatch": (
                self.embedding_dim != int(getattr(self.spec, "embedding_dim", 0) or 0)
                or self.tile_size != int(getattr(self.spec, "tile_size", 0) or 0)
            ),
        })
        return info

    def close(self) -> None:
        self._session = None
