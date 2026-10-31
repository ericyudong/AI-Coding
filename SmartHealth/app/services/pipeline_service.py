"""特征预计算与推理流水线。

设计文档依据：第四章 4.3「技术路线分期 Stage A—D」与 4.4「图块级 + 切片级聚合」。

Stage A 特征预计算（本模块 `precompute_slide_feature`）
    → 输出可复用特征库（落盘 npz，库内留元数据与 checksum，满足「特征可复现」）
Stage B 域自适应继续预训练（以 TrainingJob 记录，工程上体现为编码器切换）
Stage C 监督微调与切片级聚合（`train_mil_model` —— ABMIL 在全切片级训练）
Stage D 多模态对齐（探索线，此处以 Agent 描述智能体承载）

`run_inference` 产出的 AttentionRegion 同时服务于三处：
可解释性证据、Agent 导航候选池、AgentEvidence 的引用对象。
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from collections.abc import Callable
from typing import Any, Iterable, Sequence

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import AgentSession
from app.models.asset import Slide, SlideFeature
from app.models.modeling import ModelBase, ModelVersion, TrainingJob
from app.models.pipeline import AttentionRegion, CaseEmbedding, InferenceJob, SlidePrediction
from app.services.encoder_service import encoder_service
from app.services.image_utils import heatmap_overlay
from app.services.mil_service import GatedABMIL, MilConfig, confidence_level, encode_summary_for_storage
from app.services.wsi_service import WSIReader, open_slide

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------- 任务定义
TASK_DEFINITIONS: dict[str, dict[str, Any]] = {
    "lymph_node_metastasis": {
        "code": "lymph_node_metastasis",
        "name": "淋巴结转移检测",
        "tier": "Tier 1 成熟应用",
        "positive_label": "转移阳性",
        "negative_label": "转移阴性",
        "organ": "淋巴结",
        "staining": "H&E",
        "clinical_rationale": "已有同类产品获三类证，临床证据充分，作为商用主线首个打样任务。",
        "target_auroc": 0.92,
        "target_sensitivity": 0.95,
    },
    "gi_early_cancer": {
        "code": "gi_early_cancer",
        "name": "消化道早癌识别",
        "tier": "Tier 1 成熟应用",
        "positive_label": "早癌阳性",
        "negative_label": "非肿瘤性病变",
        "organ": "消化道",
        "staining": "H&E",
        "clinical_rationale": "筛查量大、基层缺口明显，适合云边协同下沉场景。",
        "target_auroc": 0.90,
        "target_sensitivity": 0.93,
    },
    "cervical_cytology": {
        "code": "cervical_cytology",
        "name": "宫颈细胞学辅助诊断",
        "tier": "Tier 1 成熟应用",
        "positive_label": "阳性（≥LSIL）",
        "negative_label": "阴性（NILM）",
        "organ": "宫颈",
        "staining": "特殊染色（巴氏）",
        "clinical_rationale": "成熟应用场景，注册路径最清晰；但细胞学涂片超出当前 H&E 能力声明范围。",
        "target_auroc": 0.90,
        "target_sensitivity": 0.90,
    },
}

TIER_TASKS: dict[str, list[str]] = {
    "Tier 1 成熟应用": ["cervical_cytology", "lymph_node_metastasis", "gi_early_cancer"],
    "Tier 2 增益应用": ["ihc_quantification", "pd_l1_scoring", "ki67_index"],
    "Tier 3 探索研究": ["multimodal_report", "gene_expression_prediction", "prognosis_prediction"],
}


def task_meta(task_code: str) -> dict[str, Any]:
    return TASK_DEFINITIONS.get(task_code) or {
        "code": task_code, "name": task_code, "tier": "自定义",
        "positive_label": "阳性", "negative_label": "阴性", "target_auroc": 0.90,
        "target_sensitivity": 0.90, "clinical_rationale": "", "organ": "", "staining": "H&E",
    }


# ----------------------------------------------------------------- 图块抽取配置
@dataclass
class BagConfig:
    """切片 → 图块袋的抽取配置。"""

    level: int = 1
    """特征主层：L1 = 20X（mpp 0.5）"""
    tile_size: int = 128
    stride: int = 128
    min_tissue_ratio: float = 0.05
    max_tiles: int = 0
    normalize: str = "reinhard"

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level, "tile_size": self.tile_size, "stride": self.stride,
            "min_tissue_ratio": self.min_tissue_ratio, "max_tiles": self.max_tiles,
            "normalize": self.normalize,
        }


DEFAULT_BAG_CONFIG = BagConfig()


def _feature_path(slide_code: str, encoder_code: str) -> Path:
    safe = f"{slide_code}_{encoder_code}".replace("/", "_").replace("\\", "_")
    return Path(settings.feature_dir) / f"{safe}.npz"


def _artifact_path(version_label: str) -> Path:
    safe = version_label.replace("/", "_").replace("\\", "_").replace(" ", "")
    return Path(settings.artifact_dir) / f"mil_{safe}.npz"


# ---------------------------------------------------------------- 特征预计算
def extract_bag(reader: WSIReader, config: BagConfig = DEFAULT_BAG_CONFIG,
                progress_cb: Callable[[int], None] | None = None,
                cancel_cb: Callable[[], None] | None = None) -> dict[str, Any]:
    """按 BagConfig 抽取图块袋（含坐标，供注意力热区定位）。

    progress_cb/cancel_cb：长任务（万级图块）需要可见进度与可中断能力，
    每 200 个图块回调一次，避免把进度回调本身变成性能瓶颈。
    """
    coords: list[tuple[int, int, int]] = []
    tiles: list[np.ndarray] = []
    tissue_ratios: list[float] = []
    for index, ref in enumerate(reader.iter_tiles(
        level=config.level,
        tile_size=config.tile_size,
        stride=config.stride,
        max_tiles=config.max_tiles,
        min_tissue_ratio=config.min_tissue_ratio,
    ), start=1):
        if cancel_cb is not None and index % 200 == 0:
            cancel_cb()
        coords.append((ref.level, ref.x, ref.y))
        tissue_ratios.append(ref.tissue_ratio)
        tiles.append(reader.read_region(ref.level, ref.x, ref.y, config.tile_size, config.tile_size))
        if progress_cb is not None and index % 200 == 0:
            progress_cb(index)
    return {
        "tiles": tiles,
        "coords": np.asarray(coords, dtype=np.int32).reshape(-1, 3),
        "tissue_ratios": np.asarray(tissue_ratios, dtype=np.float32),
        "level": config.level,
        "tile_size": config.tile_size,
        "stride": config.stride,
    }


def precompute_slide_feature(
    db: Session,
    slide: Slide,
    encoder_code: str,
    config: BagConfig = DEFAULT_BAG_CONFIG,
    deployment_env: str | None = None,
    job_id: int = 0,
    force: bool = False,
    progress_cb: Callable[[float, str], None] | None = None,
    cancel_cb: Callable[[], None] | None = None,
) -> SlideFeature:
    """Stage A：把切片转成可复用特征包，落盘 npz 并登记元数据与校验和。

    progress_cb(pct, stage)：把抽取与编码两个耗时阶段拆开上报，
    用户能看到「正在抽取图块」与「正在编码特征」是两件事。
    """
    def _report(pct: float, stage: str) -> None:
        if progress_cb is not None:
            progress_cb(pct, stage)
    existing = db.execute(
        select(SlideFeature).where(
            SlideFeature.slide_id == slide.id,
            SlideFeature.encoder_code == encoder_code,
            SlideFeature.tile_size == config.tile_size,
        )
    ).scalar_one_or_none()
    if existing and not force and existing.feature_path and Path(existing.feature_path).exists():
        return existing

    encoder = encoder_service.resolve(encoder_code, deployment_env=deployment_env)
    reader = open_slide(slide)
    started = time.time()
    _report(0.05, "读取切片金字塔，准备抽取组织区域")
    bag = extract_bag(
        reader, config,
        progress_cb=lambda n: _report(min(0.60, 0.05 + 0.55 * (n / max(reader.tile_budget(config), 1))),
                                      f"已抽取 {n} 个组织图块"),
        cancel_cb=(lambda: (cancel_cb() if cancel_cb is not None else None)),
    )
    _report(0.62, f"图块抽取完成（{len(bag['tiles'])} 个），开始编码特征")

    embeddings = encoder.encode_tiles(bag["tiles"]) if bag["tiles"] else np.zeros((0, encoder.embedding_dim), np.float32)
    _report(0.94, "特征编码完成，写入特征包")

    target = _feature_path(slide.code, encoder_code)
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        target,
        embeddings=embeddings.astype(np.float32),
        coords=bag["coords"],
        tissue_ratios=bag["tissue_ratios"],
        level=np.asarray([bag["level"]], dtype=np.int32),
        tile_size=np.asarray([bag["tile_size"]], dtype=np.int32),
        stride=np.asarray([bag["stride"]], dtype=np.int32),
    )
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    elapsed_ms = int((time.time() - started) * 1000)

    payload = {
        "slide_id": slide.id,
        "slide_code": slide.code,
        "encoder_code": encoder_code,
        "embedding_dim": int(embeddings.shape[1]) if embeddings.ndim == 2 else 0,
        "tile_count": int(embeddings.shape[0]),
        "magnification": reader.magnitude_label(config.level),
        "tile_size": config.tile_size,
        "stride": config.stride,
        "normalize": config.normalize,
        "feature_path": str(target),
        "coords_path": str(target),
        "checksum": checksum,
        "elapsed_ms": elapsed_ms,
        "job_id": job_id,
    }
    if existing:
        existing.update_from(payload)
        record = existing
    else:
        record = SlideFeature(**payload)
        db.add(record)

    slide.status = "featured"
    slide.tile_count = payload["tile_count"]
    slide.mpp = reader.level_mpp(config.level)
    slide.magnification = reader.magnitude_label(config.level)
    slide.width, slide.height = reader.dimensions(0)
    slide.level_count = reader.level_count
    db.flush()
    return record


def load_feature_bundle(feature: SlideFeature) -> dict[str, Any]:
    """读取特征包。"""
    path = Path(feature.feature_path)
    if not path.exists():
        raise FileNotFoundError(f"特征包不存在：{feature.feature_path}")
    data = np.load(path, allow_pickle=False)
    return {
        "embeddings": np.asarray(data["embeddings"], dtype=np.float32),
        "coords": np.asarray(data["coords"], dtype=np.int32).reshape(-1, 3),
        "tissue_ratios": np.asarray(data["tissue_ratios"], dtype=np.float32).reshape(-1),
        "level": int(data["level"][0]) if "level" in data else 1,
        "tile_size": int(data["tile_size"][0]) if "tile_size" in data else 128,
        "stride": int(data["stride"][0]) if "stride" in data else 128,
        "checksum": feature.checksum,
        "path": str(path),
    }


def get_or_build_bundle(db: Session, slide: Slide, encoder_code: str,
                        deployment_env: str | None = None) -> tuple[SlideFeature, dict[str, Any]]:
    feature = db.execute(
        select(SlideFeature).where(
            SlideFeature.slide_id == slide.id,
            SlideFeature.encoder_code == encoder_code,
        )
    ).scalar_one_or_none()
    if feature is None:
        feature = precompute_slide_feature(db, slide, encoder_code, deployment_env=deployment_env)
    return feature, load_feature_bundle(feature)


# ------------------------------------------------------------------- 模型落盘
def save_mil_model(model: GatedABMIL, version_label: str) -> str:
    path = _artifact_path(version_label)
    return model.save(path)


def load_mil_model(model_version: ModelVersion) -> GatedABMIL:
    config = json.loads(model_version.mil_config_json or "{}")
    model_path = config.get("model_path") or model_version.artifact_path
    if not model_path or not Path(model_path).exists():
        raise FileNotFoundError(
            f"模型版本 {model_version.semver} 缺少可用权重（{model_path}）。"
            "请先执行训练任务，或使用种子数据中的已发布版本。"
        )
    return GatedABMIL.load(model_path)


# ------------------------------------------------------------------- 训练
def train_mil_model(
    db: Session,
    *,
    base: ModelBase,
    encoder_code: str,
    task_code: str,
    train_slides: Sequence[tuple[Slide, float]],
    val_slides: Sequence[tuple[Slide, float]] = (),
    semver: str = "",
    config: MilConfig | None = None,
    deployment_env: str | None = None,
    triggered_by: str = "",
    gpu_hourly_cost: float = 0.0,
    progress_cb: Callable[[float, str], None] | None = None,
    cancel_cb: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Stage C：监督微调 + 切片级聚合训练，产出 ModelVersion 与 TrainingJob。

    progress_cb/cancel_cb：训练是耗时最长、最需要「看得到 + 叫得停」的作业。
    进度按真实阶段划分：特征装配（0—35%）→ 逐轮训练（35—92%）→ 校验与落盘（92—100%）。
    """
    from app.core.audit import record_audit

    def _report(pct: float, stage: str) -> None:
        if progress_cb is not None:
            progress_cb(pct, stage)

    def _check() -> None:
        if cancel_cb is not None:
            cancel_cb()

    meta = task_meta(task_code)
    encoder = encoder_service.resolve(encoder_code, deployment_env=deployment_env)
    cfg = config or MilConfig(in_dim=encoder.embedding_dim, attn_dim=settings.default_mil_attention)

    job = TrainingJob(
        code=f"TJ-{datetime.now().strftime('%Y%m%d%H%M%S')}-{np.random.randint(100, 999)}",
        job_type="supervised_finetune",
        stage="Stage C",
        base_id=base.id,
        encoder_code=encoder_code,
        dataset_ids_json=json.dumps([s.code for s, _ in train_slides]),
        params_json=json.dumps({**cfg.to_dict(), "task_code": task_code, "val_size": len(val_slides)}),
        license_env=(deployment_env or settings.deployment_env),
        train_slide_count=len(train_slides),
        val_slide_count=len(val_slides),
        status="running",
        started_at=datetime.now().isoformat(timespec="seconds"),
        triggered_by=triggered_by,
    )
    db.add(job)
    db.flush()

    started = time.time()
    _report(0.02, f"装配训练集特征包（{len(train_slides)} 张切片）")
    train_bags: list[np.ndarray] = []
    train_labels: list[float] = []
    total_slides = max(len(train_slides) + len(val_slides), 1)
    for index, (slide, label) in enumerate(train_slides, start=1):
        _check()
        _, bundle = get_or_build_bundle(db, slide, encoder_code, deployment_env)
        if index % 4 == 0 or index == len(train_slides):
            _report(min(0.32, 0.02 + 0.30 * (index / total_slides)),
                    f"装配特征包 {index}/{len(train_slides)}（切片 {slide.code}）")
        if bundle["embeddings"].shape[0] == 0:
            continue
        train_bags.append(bundle["embeddings"])
        train_labels.append(float(label))

    val_bags: list[np.ndarray] = []
    val_labels: list[float] = []
    for index, (slide, label) in enumerate(val_slides, start=1):
        _check()
        _, bundle = get_or_build_bundle(db, slide, encoder_code, deployment_env)
        if bundle["embeddings"].shape[0] == 0:
            continue
        val_bags.append(bundle["embeddings"])
        val_labels.append(float(label))
    _report(0.35, f"特征装配完成（训练 {len(train_bags)} 袋 / 验证 {len(val_bags)} 袋），开始训练")

    if not train_bags:
        job.status = "failed"
        job.log_tail = "训练集为空：所有切片的图块袋均为空（请检查组织占比阈值或切片内容）"
        job.finished_at = datetime.now().isoformat(timespec="seconds")
        db.flush()
        raise ValueError(job.log_tail)

    milestones: list[dict[str, Any]] = []

    def _on_epoch(epoch: int, total: int, monitor: float, record: dict[str, Any]) -> None:
        # 训练阶段占进度 35%—92%，用真实轮次换算
        _report(0.35 + 0.57 * (epoch / max(total, 1)),
                f"训练第 {epoch}/{total} 轮 · loss={record.get('loss')} · "
                f"train AUROC={record.get('train_auroc')}"
                + (f" · val AUROC={record.get('val_auroc')}" if record.get("val_auroc") is not None else ""))

    model = GatedABMIL(cfg)
    summary = model.fit(train_bags, train_labels, val_bags or None, val_labels or None,
                        milestones=milestones, epoch_cb=_on_epoch, cancel_cb=cancel_cb)
    _report(0.92, "训练收敛，正在计算指标并落盘模型")

    version_label = semver or f"{base.code}-{datetime.now().strftime('%Y%m%d%H%M')}"
    model_path = save_mil_model(model, version_label)
    elapsed = int(time.time() - started)

    metrics = {
        "task_code": task_code,
        "tile_bag_mean": round(float(np.mean([b.shape[0] for b in train_bags])), 3),
        "train": {
            "bag_count": len(train_bags),
            "positive_count": int(sum(1 for x in train_labels if x >= 0.5)),
            "auroc": summary.get("final_train_auroc", 0.0),
        },
        "validation": {},
        "history_tail": milestones,
        "platt": summary.get("platt", {}),
    }
    if val_bags:
        scores = np.array([model.predict(b)["probability"] for b in val_bags])
        cal = np.array([model.predict(b)["calibrated_probability"] for b in val_bags])
        from app.services.evaluation_service import full_report

        report = full_report(val_labels, cal.tolist(), threshold=0.5, bootstrap_rounds=200, bootstrap=False)
        metrics["validation"] = {
            "bag_count": len(val_bags),
            "auroc": report["auroc"],
            "auroc_raw": round(float(GatedABMIL._auroc(np.asarray(val_labels), scores)), 6),
            "sensitivity": report["sensitivity"],
            "specificity": report["specificity"],
            "ece": report["ece"],
            "brier": report["brier"],
        }

    version = ModelVersion(
        base_id=base.id,
        semver=version_label,
        name=f"{base.name} {version_label}",
        encoder_code=encoder_code,
        mil_config_json=json.dumps({
            "model_path": model_path,
            "in_dim": cfg.in_dim,
            "attn_dim": cfg.attn_dim,
            "tile_size": settings.default_tile_size,
            "stride": settings.default_tile_size,
            "level": DEFAULT_BAG_CONFIG.level,
            "encoder_code": encoder_code,
            "task_code": task_code,
            "bag_config": DEFAULT_BAG_CONFIG.to_dict(),
        }, ensure_ascii=False),
        training_job_id=job.id,
        metrics_json=json.dumps(metrics, ensure_ascii=False),
        artifact_path=model_path,
        param_count=int(model.V.size + model.U.size + model.w.size + model.W.size + 1),
        status="validated",
        released_at=datetime.now().isoformat(timespec="seconds"),
        changelog=f"由训练任务 {job.code} 产出；任务类型 {meta['name']}。",
    )
    db.add(version)
    db.flush()

    job.status = "succeeded"
    job.progress = 1.0
    job.finished_at = datetime.now().isoformat(timespec="seconds")
    job.duration_sec = elapsed
    job.gpu_hours = round(elapsed / 3600.0 * 1.0, 4)
    job.cost_estimate = round(job.gpu_hours * gpu_hourly_cost, 2)
    job.output_version_id = version.id
    job.metrics_json = json.dumps(metrics, ensure_ascii=False)
    job.log_tail = (
        f"训练完成：{len(train_bags)} 个训练袋，最佳监控指标 {summary.get('best_monitor')}，"
        f"耗时 {elapsed}s；产物 {Path(model_path).name}"
    )
    base.default_encoder_code = base.default_encoder_code or encoder_code
    db.flush()

    record_audit(
        db,
        action="train_model_version",
        resource_type="model_version",
        resource_id=version.id,
        actor=triggered_by or "system",
        summary=f"训练产出模型版本 {version.semver}（任务 {task_code}，编码器 {encoder_code}）",
        payload={"metrics": metrics, "job_code": job.code},
    )

    return {"job": job, "version": version, "model": model, "summary": summary, "metrics": metrics}


# ------------------------------------------------------------------- 推理
def _render_attention_overlay(reader: WSIReader, level: int, coords: np.ndarray,
                              attention: np.ndarray) -> np.ndarray:
    """在对应层级的图像上叠加注意力热力图。"""
    width, height = reader.dimensions(level)
    plane = reader.read_region(level, 0, 0, width, height).copy()
    if coords.size == 0 or attention.size == 0:
        return plane

    tile_size = int(settings.default_tile_size)
    attn = np.asarray(attention, dtype=np.float32)
    span = float(attn.max() - attn.min())
    norm = np.zeros_like(attn) if span < 1e-12 else (attn - attn.min()) / span

    hot = np.array([90, 14, 19], dtype=np.float32)   # #5A0E13
    cold = np.array([255, 255, 255], dtype=np.float32)
    base = plane.astype(np.float32)
    for idx in range(coords.shape[0]):
        _, x, y = int(coords[idx][0]), int(coords[idx][1]), int(coords[idx][2])
        y0, y1 = max(0, y), min(height, y + tile_size)
        x0, x1 = max(0, x), min(width, x + tile_size)
        if y1 <= y0 or x1 <= x0:
            continue
        value = float(norm[idx])
        color = cold * (1 - value) + hot * value
        blend = 0.5 * value
        base[y0:y1, x0:x1] = base[y0:y1, x0:x1] * (1 - blend) + color * blend
    return np.clip(base, 0, 255).astype(np.uint8)


def _save_png(array: np.ndarray, path: Path) -> str:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array).save(path)
    return str(path)


def run_inference(
    db: Session,
    *,
    slides: Sequence[Slide],
    model_version: ModelVersion,
    task_code: str = "lymph_node_metastasis",
    threshold: float = 0.5,
    job_kind: str = "batch",
    deployment_env: str | None = None,
    triggered_by: str = "",
    name: str = "",
    progress_cb: Callable[[float, str], None] | None = None,
    cancel_cb: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """批量/单例推理：产出预测、注意力热区、热力图与切片级向量索引。

    progress_cb/cancel_cb：批量推理可能一次上千张切片，必须逐张上报且可中断。
    单张失败只计入 failed_count 并继续，不中断整批 —— 这是批处理的正确语义。
    """
    from app.core.audit import record_audit

    def _report(pct: float, stage: str) -> None:
        if progress_cb is not None:
            progress_cb(pct, stage)

    def _check() -> None:
        if cancel_cb is not None:
            cancel_cb()

    config = json.loads(model_version.mil_config_json or "{}")
    encoder_code = config.get("encoder_code") or model_version.encoder_code
    bag_config = BagConfig(**{k: v for k, v in (config.get("bag_config") or {}).items()
                              if k in BagConfig.__dataclass_fields__})
    model = load_mil_model(model_version)

    job = InferenceJob(
        code=f"IJ-{datetime.now().strftime('%Y%m%d%H%M%S')}-{np.random.randint(100, 999)}",
        name=name or f"{task_meta(task_code)['name']} 推理",
        model_version_id=model_version.id,
        model_version_label=model_version.semver,
        encoder_code=encoder_code,
        job_kind=job_kind,
        slide_ids_json=json.dumps([s.id for s in slides]),
        slice_count=len(slides),
        normalize=bag_config.normalize,
        tile_size=bag_config.tile_size,
        stride=bag_config.stride,
        threshold=threshold,
        params_json=json.dumps(bag_config.to_dict()),
        status="running",
        started_at=datetime.now().isoformat(timespec="seconds"),
        triggered_by=triggered_by,
    )
    db.add(job)
    db.flush()

    started = time.time()
    decisions = {"positive": 0, "negative": 0, "rejected": 0}
    confidences: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    probabilities: list[float] = []

    for index, slide in enumerate(slides, start=1):
        _check()
        _report(0.02 + 0.93 * ((index - 1) / max(len(slides), 1)),
                f"推理 {index}/{len(slides)}（切片 {slide.code}）"
                f" · 已完成 {job.finished_count} · 失败 {job.failed_count}")
        try:
            feature, bundle = get_or_build_bundle(db, slide, encoder_code, deployment_env)
        except Exception as exc:  # pragma: no cover - 单例失败不应中断整批
            logger.warning("切片 %s 特征构建失败：%s", slide.code, exc)
            job.failed_count += 1
            continue

        embeddings = bundle["embeddings"]
        coords = bundle["coords"]
        if embeddings.shape[0] == 0:
            job.failed_count += 1
            continue

        prediction = model.predict(embeddings)
        attention = np.asarray(prediction["attention"], dtype=np.float64)
        calibrated = float(prediction["calibrated_probability"])
        conf = confidence_level(
            calibrated,
            float(prediction.get("attention_entropy", 0.0)),
            int(prediction.get("tile_count", 0)),
            evidence_count=int(min(3, embeddings.shape[0])),
        )
        rejected = False
        reject_reason = ""
        certainty = max(calibrated, 1 - calibrated)
        if embeddings.shape[0] < 8:
            rejected, reject_reason = True, "有效图块数不足（组织占比过低），不具备判定条件"
        elif certainty < settings.agent_confidence_threshold:
            rejected, reject_reason = True, (
                f"校准后置信度 {certainty:.3f} 低于阈值 {settings.agent_confidence_threshold}，"
                "触发拒识并转人工复核"
            )
        elif conf == "low" and settings.reject_requires_manual_review:
            rejected, reject_reason = True, "置信度分级为低，按平台策略转人工复核"

        if rejected:
            decision = "rejected"
        else:
            decision = "positive" if calibrated >= threshold else "negative"

        reader = open_slide(slide)
        heatmap_path = ""
        try:
            overlay = _render_attention_overlay(reader, bag_config.level, coords, attention)
            heatmap_path = _save_png(overlay, Path(settings.wsi_dir) / "heatmaps" / f"{slide.code}_attn.png")
        except Exception as exc:  # pragma: no cover
            logger.warning("热力图生成失败 %s：%s", slide.code, exc)

        row = SlidePrediction(
            job_id=job.id,
            slide_id=slide.id,
            slide_code=slide.code,
            model_version_id=model_version.id,
            model_version_label=model_version.semver,
            encoder_code=encoder_code,
            task_code=task_code,
            label_name=task_meta(task_code)["positive_label"],
            label_truth=task_meta(task_code)["positive_label"] if slide.has_lesion else task_meta(task_code)["negative_label"],
            probability=float(prediction["probability"]),
            calibrated_probability=calibrated,
            threshold=threshold,
            decision=decision,
            rejected=rejected,
            reject_reason=reject_reason,
            confidence_level=conf,
            tile_count=int(prediction["tile_count"]),
            embedding_dim=int(embeddings.shape[1]),
            elapsed_ms=int((time.time() - started) * 1000 / max(len(slides), 1)),
            heatmap_path=heatmap_path,
            attention_summary_json=encode_summary_for_storage(prediction),
            feature_path=feature.feature_path,
        )
        db.add(row)
        db.flush()

        # 注意力热区（取前 24 个，足够 Agent 与可解释性使用）
        order = np.argsort(-attention)[: min(24, attention.size)]
        lesion_mask = None
        try:
            lesion_mask = reader.lesion_mask_at(bag_config.level)
        except Exception:  # pragma: no cover
            lesion_mask = None
        tsize = bag_config.tile_size
        total = float(attention.sum()) or 1.0
        for rank, idx in enumerate(order.tolist(), start=1):
            _, x, y = int(coords[idx][0]), int(coords[idx][1]), int(coords[idx][2])
            overlap = False
            if lesion_mask is not None:
                sub = lesion_mask[y: y + tsize, x: x + tsize]
                if sub.size:
                    overlap = bool(sub.mean() > 0.5)
            db.add(AttentionRegion(
                prediction_id=row.id,
                slide_id=slide.id,
                rank=rank,
                level=int(coords[idx][0]),
                x=x, y=y, w=tsize, h=tsize,
                magnification=reader.magnitude_label(int(coords[idx][0])),
                attention=float(attention[idx]),
                attention_share=float(attention[idx] / total),
                mean_intensity=float(bundle["tissue_ratios"][idx]) if idx < bundle["tissue_ratios"].size else 0.0,
                tissue_ratio=float(bundle["tissue_ratios"][idx]) if idx < bundle["tissue_ratios"].size else 0.0,
                is_lesion_overlap=overlap,
            ))

        # 切片级向量索引（供描述智能体做相似病例检索）
        slide_vector = np.average(embeddings, axis=0, weights=np.maximum(attention, 1e-6))
        norm = float(np.linalg.norm(slide_vector)) or 1.0
        vector_path = _feature_path(slide.code, encoder_code).with_name(f"case_{slide.code}_{encoder_code}.npy")
        np.save(vector_path, (slide_vector / norm).astype(np.float32))
        db.add(CaseEmbedding(
            slide_id=slide.id,
            slide_code=slide.code,
            case_no=slide.case_no,
            model_version_id=model_version.id,
            encoder_code=encoder_code,
            dim=int(slide_vector.size),
            vector_path=str(vector_path),
            diagnosis_text=slide.diagnosis_text,
            cancer_type=slide.cancer_type,
            organ=slide.organ,
            site_code=slide.site_code,
            split=slide.split,
            status="ready",
        ))

        slide.status = "inferred"
        decisions[decision] += 1
        confidences[conf] = confidences.get(conf, 0) + 1
        probabilities.append(calibrated)
        job.finished_count += 1

    elapsed_ms = int((time.time() - started) * 1000)
    _report(0.97, f"批量推理结束（成功 {job.finished_count} / 失败 {job.failed_count}），正在汇总统计")
    job.status = "succeeded" if job.failed_count == 0 else ("failed" if job.finished_count == 0 else "succeeded")
    job.progress = 1.0
    job.finished_at = datetime.now().isoformat(timespec="seconds")
    job.elapsed_ms = elapsed_ms
    summary = {
        "task_code": task_code,
        "task_name": task_meta(task_code)["name"],
        "model_version": model_version.semver,
        "encoder_code": encoder_code,
        "decisions": decisions,
        "confidence_distribution": confidences,
        "threshold": threshold,
        "mean_calibrated_probability": round(float(np.mean(probabilities)), 6) if probabilities else 0.0,
        "reject_rate": round(decisions["rejected"] / max(job.finished_count, 1), 6),
        "elapsed_ms": elapsed_ms,
    }
    job.summary_json = json.dumps(summary, ensure_ascii=False)
    job.log_tail = (
        f"完成 {job.finished_count}/{job.slice_count} 张切片；"
        f"阳性 {decisions['positive']}、阴性 {decisions['negative']}、拒识 {decisions['rejected']}；"
        f"耗时 {elapsed_ms} ms"
    )
    db.flush()

    record_audit(
        db,
        action="run_inference",
        resource_type="inference_job",
        resource_id=job.id,
        actor=triggered_by or "system",
        summary=f"推理任务 {job.code} 完成（{job.finished_count} 张切片，拒识 {decisions['rejected']} 张）",
        payload=summary,
    )
    return {"job": job, "summary": summary}


# ------------------------------------------------------------------ 相似病例
def similar_cases(db: Session, slide: Slide, encoder_code: str, top_k: int = 5,
                  exclude_same_case: bool = True) -> list[dict[str, Any]]:
    """按切片级向量做余弦相似检索（描述智能体的病例参照来源）。"""
    current = db.execute(
        select(CaseEmbedding).where(CaseEmbedding.slide_id == slide.id).limit(1)
    ).scalar_one_or_none()
    if current is None:
        feature, bundle = get_or_build_bundle(db, slide, encoder_code)
        embeddings = bundle["embeddings"]
        if embeddings.shape[0] == 0:
            return []
        vector = embeddings.mean(axis=0)
    else:
        vector = np.load(current.vector_path) if Path(current.vector_path).exists() else None
        if vector is None:
            return []
    vector = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(vector)) or 1.0
    vector = vector / norm

    candidates = list(db.execute(
        select(CaseEmbedding).where(CaseEmbedding.slide_id != slide.id)
    ).scalars())
    scored: list[tuple[float, CaseEmbedding]] = []
    for candidate in candidates:
        path = Path(candidate.vector_path)
        if not path.exists():
            continue
        other = np.load(path).astype(np.float32)
        other = other / (float(np.linalg.norm(other)) or 1.0)
        if other.shape != vector.shape:
            continue
        if exclude_same_case and candidate.case_no and candidate.case_no == slide.case_no:
            continue
        scored.append((float(np.dot(vector, other)), candidate))
    scored.sort(key=lambda x: -x[0])
    return [
        {
            "slide_code": item.slide_code,
            "similarity": round(score, 6),
            "diagnosis_text": item.diagnosis_text,
            "cancer_type": item.cancer_type,
            "organ": item.organ,
            "site_code": item.site_code,
            "split": item.split,
        }
        for score, item in scored[:top_k]
    ]


# ------------------------------------------------------------------ 任务进展
def pipeline_overview(db: Session) -> dict[str, Any]:
    """流水线总览：各阶段切片数与最近任务。"""
    def _count(*conditions) -> int:
        stmt = select(func.count(Slide.id))
        if conditions:
            stmt = stmt.where(*conditions)
        return int(db.execute(stmt).scalar() or 0)

    total = _count()
    featured = int(db.execute(select(func.count(SlideFeature.id))).scalar() or 0)
    inferred = _count(Slide.status == "inferred")
    latest_job = db.execute(select(TrainingJob).order_by(TrainingJob.id.desc()).limit(1)).scalar_one_or_none()
    latest_inference = db.execute(select(InferenceJob).order_by(InferenceJob.id.desc()).limit(1)).scalar_one_or_none()
    latest_version = db.execute(
        select(ModelVersion).order_by(ModelVersion.id.desc()).limit(1)
    ).scalar_one_or_none()
    agent_sessions = int(db.execute(select(func.count(AgentSession.id))).scalar() or 0)
    return {
        "stage_a_feature_ready": featured,
        "slide_total": total,
        "inferred_slide_count": inferred,
        "feature_coverage": round(featured / total, 6) if total else 0.0,
        "agent_session_count": agent_sessions,
        "latest_training_job": latest_job.to_dict() if latest_job else None,
        "latest_inference_job": latest_inference.to_dict() if latest_inference else None,
        "latest_model_version": latest_version.to_dict() if latest_version else None,
        "stages": [
            {"key": "Stage A", "name": "特征预计算", "done": featured, "total": total,
             "note": "把切片转成可复用特征库，一次投入长期复用"},
            {"key": "Stage B", "name": "域自适应继续预训练", "done": 1 if latest_job else 0, "total": 1,
             "note": "在可商用基座上做病理域适配，不从零训练"},
            {"key": "Stage C", "name": "监督微调与切片级聚合", "done": inferred, "total": total,
             "note": "用自有医生标注作监督信号，打通图块到切片的临床结论"},
            {"key": "Stage D", "name": "多模态对齐（探索线）", "done": agent_sessions, "total": max(agent_sessions, 1),
             "note": "视觉-语言对齐，为 Agent 生成可解释的形态学描述"},
        ],
    }
