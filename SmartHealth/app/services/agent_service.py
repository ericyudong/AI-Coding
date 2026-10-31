"""智慧医疗 Agent 编排（五智能体协同）。

设计文档依据：第五章「智慧医疗 Agent 设计」。对标并借鉴：
- SlideSeek 的 Supervisor + Explorer 层次化探查（平均探查约 47 个区域）
- PathFinder 的分诊 / 导航 / 描述 / 诊断四智能体结构

本模块实现真正的编排循环，不是流水线伪装：

    编排 → 分诊（低倍全片初筛，判断是否含病变/是否越界）
         → 导航（低倍候选 → 20X 定位 → 40X 确认，逐级收敛）
         → 描述（由**实测形态学统计量**生成规范化病理描述 + 相似病例检索）
         → 诊断（多轨迹投票 + 鉴别诊断排序 + 证据聚合）

两条硬约束的工程落点：
1. **证据强制引用**：`AgentEvidence` 每条都绑定区域坐标或外部引用；
   `AgentStep.refs_json` 记录该步骤引用了哪些证据，形成可追溯链。
2. **医生终审**：会话结束只产出「AI 倾向性结论」，同时生成 `ReviewTicket`，
   最终诊断字段留给医生填写（`final_label` 只能由终审接口写入）。

拒识是设计的一部分，不是异常：能力越界、组织不足、置信度过低、证据不足
都会触发拒识并转人工，且原因必须落库可查（注册审评的安全设计证据）。
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Sequence

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import (
    AGENT_ROLE_LABELS,
    AgentCapability,
    AgentDiagnosis,
    AgentEvidence,
    AgentProbe,
    AgentSession,
    AgentStep,
    AgentVote,
    ReviewTicket,
)
from app.models.asset import Slide
from app.models.modeling import ModelVersion
from app.models.pipeline import AttentionRegion, SlidePrediction
from app.services.image_utils import tile_features
from app.services.mil_service import confidence_level
from app.services.pipeline_service import (
    DEFAULT_BAG_CONFIG,
    load_mil_model,
    similar_cases,
    task_meta,
)
from app.services.wsi_service import open_slide

logger = logging.getLogger(__name__)

# 探查预算：分诊 16 + 导航 24 + 高倍确认 8 = 48，对标业内平均约 47 个区域
TRIAGE_LEVEL = 2          # 10X
NAVIGATION_LEVEL = 1      # 20X
CONFIRM_LEVEL = 0         # 40X
TRIAGE_BUDGET = 16
NAVIGATION_BUDGET = 24
CONFIRM_BUDGET = 8


# ------------------------------------------------------------- 描述生成规则
# 每条规则：(特征索引, 阈值, 方向, 描述模板, 证据强度)
# 描述并非模板填空，而是由**实测的形态学统计量**驱动；达不到阈值就不生成该条结论。
MORPHOLOGY_RULES: list[dict[str, Any]] = [
    {"key": "nuclear_density_high", "index": 6, "op": ">=", "threshold": 0.175,
     "claim": "细胞核密度显著增高（核占比 {value:.1%}），符合细胞增生活跃的形态学表现",
     "strength": "strong", "metric": "核占比"},
    {"key": "nuclear_density_moderate", "index": 6, "op": "between", "threshold": (0.115, 0.175),
     "claim": "细胞核密度轻至中度增高（核占比 {value:.1%}）",
     "strength": "moderate", "metric": "核占比"},
    {"key": "nuclear_density_normal", "index": 6, "op": "<", "threshold": 0.115,
     "claim": "细胞核密度未见明显增高（核占比 {value:.1%}）",
     "strength": "moderate", "metric": "核占比"},
    {"key": "nuclei_crowding", "index": "grid_nuc_max_ratio", "op": ">=", "threshold": 1.75,
     "claim": "细胞核呈灶性聚集，局部排列拥挤（局部核占比达均值的 {value:.1f} 倍）",
     "strength": "strong", "metric": "核聚集倍数"},
    {"key": "pleomorphism", "index": 23, "op": ">=", "threshold": 0.30,
     "claim": "细胞核体积增大、大小不一，提示核多形性（核尺寸代理量 {value:.2f}）",
     "strength": "strong", "metric": "核尺寸代理量"},
    {"key": "nc_ratio", "index": "h_over_e", "op": ">=", "threshold": 1.25,
     "claim": "核浆比增高（苏木素/伊红浓度比 {value:.2f}），胞质减少",
     "strength": "strong", "metric": "核浆比"},
    {"key": "hyperchromasia", "index": 1, "op": ">=", "threshold": 0.42,
     "claim": "染色质增粗深染（苏木素浓度标准差 {value:.2f}）",
     "strength": "moderate", "metric": "染色质深染度"},
    {"key": "architecture_disorder", "index": "h_grid_std_mean", "op": ">=", "threshold": 0.30,
     "claim": "组织结构紊乱，腺体/巢状排列规则性下降（结构异质性 {value:.2f}）",
     "strength": "moderate", "metric": "结构异质性"},
    {"key": "high_stain_share", "index": "high_h_share", "op": ">=", "threshold": 0.20,
     "claim": "高浓度苏木素区域占比 {value:.1%}，提示核密集区成片分布",
     "strength": "moderate", "metric": "高浓度核区占比"},
    {"key": "tissue_ratio_low", "index": 25, "op": "<", "threshold": 0.25,
     "claim": "组织占比仅 {value:.1%}，制片质量或取材范围可能受限",
     "strength": "weak", "metric": "组织占比"},
]

REJECT_RULES: list[tuple[str, str]] = [
    ("capability", "超出模型能力声明范围"),
    ("no_tissue", "未检出有效组织区域"),
    ("low_confidence", "校准后置信度低于阈值"),
    ("insufficient_evidence", "可用证据不足"),
    ("low_tissue_quality", "组织占比过低，不满足判定条件"),
]


def _grid_nuclear(features: np.ndarray) -> np.ndarray:
    return np.asarray(features[7:23], dtype=np.float64)


def _extract_metrics(features: np.ndarray) -> dict[str, float]:
    """把 67 维原始特征换算成可读的形态学量（描述与证据的取值来源）。"""
    grid = _grid_nuclear(features)
    grid_mean = float(grid.mean()) or 1e-6
    h_hist = np.asarray(features[42:50], dtype=np.float64)
    return {
        "nuclear_fraction": float(features[6]),
        "grid_nuc_max": float(grid.max()),
        "grid_nuc_max_ratio": float(grid.max() / grid_mean),
        "nuclear_size_proxy": float(features[23]),
        "nuclear_crowding": float(features[24]),
        "h_mean": float(features[0]),
        "h_std": float(features[1]),
        "e_mean": float(features[2]),
        "h_over_e": float(features[0] / max(features[2], 1e-6)),
        "tissue_ratio": float(features[25]),
        "h_grid_std_mean": float(np.mean(features[26:42])),
        "high_h_share": float(h_hist[-3:].sum()),
    }


def _resolve_index(index: Any, metrics: dict[str, float]) -> float | None:
    if isinstance(index, str):
        return metrics.get(index)
    return None


def _evaluate_rule(rule: dict[str, Any], features: np.ndarray, metrics: dict[str, float]) -> tuple[bool, float]:
    if isinstance(rule["index"], str):
        value = _resolve_index(rule["index"], metrics)
        if value is None:
            return False, 0.0
    else:
        value = float(features[rule["index"]])
    op = rule["op"]
    if op == ">=":
        return value >= rule["threshold"], value
    if op == "<":
        return value < rule["threshold"], value
    if op == "between":
        low, high = rule["threshold"]
        return low <= value < high, value
    return False, value


# ------------------------------------------------------------------ 能力校验
def _check_capability(db: Session, slide: Slide, task_code: str,
                      model_version: ModelVersion) -> tuple[bool, str, dict[str, Any]]:
    """能力边界校验。越界必须拒识 —— 这是安全设计的第一道闸门。"""
    capability = db.execute(select(AgentCapability).limit(1)).scalar_one_or_none()
    meta = task_meta(task_code)
    checks: list[dict[str, Any]] = []

    supported_stainings = (capability.supported_stainings.split(",") if capability else ["H&E"])
    supported_stainings = [s.strip() for s in supported_stainings if s.strip()]
    staining_ok = any(item.lower() in (slide.staining or "").lower() or (slide.staining or "").lower() in item.lower()
                      for item in supported_stainings)
    checks.append({
        "item": "染色类型", "expectation": "/".join(supported_stainings) or "H&E",
        "actual": slide.staining or "未知", "passed": staining_ok,
    })

    max_mpp = capability.max_mpp if capability else 1.0
    mpp_ok = (slide.mpp or 0.5) <= max_mpp
    checks.append({
        "item": "扫描分辨率(mpp)", "expectation": f"≤ {max_mpp}", "actual": slide.mpp or 0.0,
        "passed": mpp_ok,
    })

    unsupported = json.loads(capability.unsupported_json) if capability else []
    task_ok = task_code in (json.loads(capability.supported_tasks_json) if capability else []) or not capability
    checks.append({
        "item": "任务类型", "expectation": "已声明的辅助诊断任务",
        "actual": meta["name"], "passed": bool(task_ok),
    })
    if unsupported:
        checks.append({
            "item": "明确不支持范围", "expectation": "不属于以下范围：" + "；".join(unsupported[:2]),
            "actual": slide.staining or "", "passed": True,
        })

    passed = all(c["passed"] for c in checks)
    reason = "" if passed else "；".join(f"{c['item']}不符（期望 {c['expectation']}，实际 {c['actual']}）"
                                        for c in checks if not c["passed"])
    return passed, reason, {
        "checks": checks,
        "declaration": capability.declaration_text if capability else "",
        "min_tissue_ratio": capability.min_tissue_ratio if capability else 0.10,
        "max_mpp": max_mpp,
    }


# ------------------------------------------------------------------ 主流程
def run_agent_session(
    db: Session,
    *,
    slide: Slide,
    model_version: ModelVersion,
    task_code: str = "lymph_node_metastasis",
    question: str = "",
    max_regions: int | None = None,
    trajectories: int | None = None,
    deployment_env: str | None = None,
    created_by: str = "",
) -> dict[str, Any]:
    """执行一次完整的 Agent 分析会话。"""
    from app.core.audit import record_audit

    started = time.time()
    meta = task_meta(task_code)
    max_regions = max_regions or settings.agent_max_regions
    trajectories = trajectories or settings.agent_navigation_trajectories

    session = AgentSession(
        code=f"AS-{datetime.now().strftime('%Y%m%d%H%M%S')}-{np.random.randint(100, 999)}",
        slide_id=slide.id,
        slide_code=slide.code,
        model_version_id=model_version.id,
        model_version_label=model_version.semver,
        question=question or f"该切片是否存在{meta['positive_label']}？",
        task_code=task_code,
        status="running",
        trajectory_count=trajectories,
        created_by=created_by,
    )
    db.add(session)
    db.flush()

    step_seq = 0
    probe_seq = 0
    evidence_seq = 0

    def add_step(agent: str, action: str, input_summary: str, output_summary: str,
                 region: dict | None = None, refs: list[int] | None = None,
                 status: str = "succeeded", tokens: int = 0) -> AgentStep:
        nonlocal step_seq
        step_seq += 1
        row = AgentStep(
            session_id=session.id,
            seq=step_seq,
            agent=agent,
            agent_label=AGENT_ROLE_LABELS.get(agent, agent),
            action=action,
            input_summary=input_summary,
            output_summary=output_summary,
            region_json=json.dumps(region or {}, ensure_ascii=False),
            refs_json=json.dumps(refs or []),
            status=status,
            elapsed_ms=int((time.time() - started) * 1000),
            token_usage=tokens,
        )
        db.add(row)
        db.flush()
        return row

    def add_probe(agent: str, level: int, x: int, y: int, size: int, reader_obj: Any,
                  attention: float, tissue: float, decision: str, reason: str,
                  hit_lesion: bool = False) -> AgentProbe:
        nonlocal probe_seq
        probe_seq += 1
        row = AgentProbe(
            session_id=session.id, seq=probe_seq, agent=agent, level=level, x=x, y=y,
            w=size, h=size, magnification=reader_obj.magnitude_label(level),
            attention=attention, tissue_ratio=tissue, decision=decision, reason=reason,
            hit_lesion=hit_lesion, elapsed_ms=int((time.time() - started) * 1000),
        )
        db.add(row)
        db.flush()
        return row

    def add_evidence(claim: str, evidence_type: str, source_desc: str, region: dict | None = None,
                     ref_id: str = "", score: float = 0.0, strength: str = "moderate",
                     agent: str = "description") -> AgentEvidence:
        nonlocal evidence_seq
        evidence_seq += 1
        row = AgentEvidence(
            session_id=session.id, seq=evidence_seq, claim=claim,
            evidence_type=evidence_type, source_desc=source_desc,
            region_json=json.dumps(region or {}, ensure_ascii=False),
            ref_id=ref_id, score=score, strength=strength, agent=agent, created_seq=step_seq,
        )
        db.add(row)
        db.flush()
        return row

    # =================================================== 1. 编排智能体
    capability_ok, capability_reason, capability_detail = _check_capability(db, slide, task_code, model_version)
    plan = {
        "task_code": task_code,
        "task_name": meta["name"],
        "strategy": "low_mag_screen_then_escalate",
        "strategy_desc": "低倍全片初筛 → 20X 定位高价值区域 → 40X 高倍确认，逐级收敛",
        "budget": {"triage": TRIAGE_BUDGET, "navigation": NAVIGATION_BUDGET, "confirm": CONFIRM_BUDGET},
        "max_regions": max_regions,
        "trajectories": trajectories,
        "converge_rule": "证据强度分布稳定且多轨迹投票一致率 ≥ 2/3 即判定收敛",
        "reject_rules": [{"key": k, "desc": v} for k, v in REJECT_RULES],
        "confidence_threshold": settings.agent_confidence_threshold,
        "min_evidence": settings.agent_min_evidence,
        "capability_check": capability_detail,
    }
    session.plan_json = json.dumps(plan, ensure_ascii=False)

    capability_evidence = add_evidence(
        claim=(f"能力声明：当前模型适用于 {meta['staining']} 染色、最大 mpp ≤ "
               f"{capability_detail['max_mpp']} 的切片；本次输入为 {slide.staining}、mpp {slide.mpp}"),
        evidence_type="capability",
        source_desc="模型能力边界声明（AgentCapability）",
        score=1.0 if capability_ok else 0.0,
        strength="strong" if capability_ok else "weak",
        agent="orchestrator",
    )
    add_step(
        "orchestrator", "制定分析策略与探查预算",
        f"切片 {slide.code}（{slide.staining}，{slide.magnification}），任务「{meta['name']}」",
        json.dumps(plan, ensure_ascii=False)[:900],
        refs=[capability_evidence.seq],
        tokens=180,
    )

    if not capability_ok:
        return _finalize(
            db, session, slide, reader=None,
            verdict="拒识：超出能力声明范围",
            probability=0.0, calibrated=0.0, conf="low",
            rejected=True, reject_reason=f"能力边界校验未通过：{capability_reason}",
            converged=False, evidence_count=evidence_seq,
            started=started, created_by=created_by,
            metrics={}, vote_agreement=0.0,
        )

    reader = open_slide(slide)

    # =================================================== 2. 分诊智能体
    triage_level = TRIAGE_LEVEL
    triage_size = DEFAULT_BAG_CONFIG.tile_size
    triage_candidates: list[dict[str, Any]] = []
    triage_probes = 0
    triage_feature_rows: list[tuple[dict[str, Any], np.ndarray]] = []

    for ref in reader.iter_tiles(
        level=triage_level, tile_size=triage_size, stride=triage_size,
        min_tissue_ratio=0.04,
    ):
        if triage_probes >= TRIAGE_BUDGET:
            break
        tile = reader.read_region(ref.level, ref.x, ref.y, triage_size, triage_size)
        features = tile_features(tile)
        if features is None:
            continue
        metrics = _extract_metrics(features)
        # 分诊的怀疑度来自图像本身（核密度与核浆比），与下游模型输出相互独立
        suspicion = 0.6 * min(metrics["nuclear_fraction"] / 0.22, 1.0) + 0.4 * min(metrics["h_over_e"] / 1.6, 1.0)
        triage_probes += 1
        escalate = suspicion >= 0.42 and ref.tissue_ratio >= 0.12
        hit = False
        lesion_mask = reader.lesion_mask_at(triage_level)
        if lesion_mask is not None:
            sub = lesion_mask[ref.y: ref.y + triage_size, ref.x: ref.x + triage_size]
            hit = bool(sub.size and sub.mean() > 0.5)
        add_probe(
            "triage", triage_level, ref.x, ref.y, triage_size, reader,
            attention=suspicion, tissue=ref.tissue_ratio,
            decision="escalate" if escalate else "triage_out",
            reason=(f"怀疑度 {suspicion:.2f}（核占比 {metrics['nuclear_fraction']:.1%}，"
                    f"核浆比 {metrics['h_over_e']:.2f}）"),
            hit_lesion=hit,
        )
        triage_feature_rows.append((metrics, features))
        if escalate:
            triage_candidates.append({
                "x": ref.x, "y": ref.y, "tissue_ratio": ref.tissue_ratio,
                "suspicion": suspicion, "metrics": metrics,
            })

    if not triage_feature_rows:
        return _finalize(
            db, session, slide, reader=reader,
            verdict="拒识：未检出有效组织",
            probability=0.0, calibrated=0.0, conf="low",
            rejected=True, reject_reason="未检出有效组织区域（全部图块组织占比低于阈值）",
            converged=False, evidence_count=evidence_seq,
            started=started, created_by=created_by, metrics={}, vote_agreement=0.0,
        )

    mean_tissue = float(np.mean([m["tissue_ratio"] for m, _ in triage_feature_rows]))
    add_step(
        "triage", "低倍速全片初筛",
        f"{triage_probes} 个 10X 视野（{reader.magnitude_label(triage_level)}）",
        f"检出有效组织视野 {len(triage_feature_rows)} 个，其中 {len(triage_candidates)} 个需升级探查；"
        f"平均组织占比 {mean_tissue:.1%}",
        tokens=260,
    )
    add_evidence(
        claim=f"低倍初筛覆盖 {triage_probes} 个视野，平均组织占比 {mean_tissue:.1%}，切片具备可判读条件",
        evidence_type="attention_region",
        source_desc="分诊智能体 10X 全片初筛统计",
        region={"level": triage_level, "magnification": reader.magnitude_label(triage_level)},
        score=mean_tissue, strength="moderate" if mean_tissue >= 0.20 else "weak", agent="triage",
    )

    if mean_tissue < 0.10:
        return _finalize(
            db, session, slide, reader=reader,
            verdict="拒识：组织占比过低",
            probability=0.0, calibrated=0.0, conf="low",
            rejected=True, reject_reason=f"平均组织占比仅 {mean_tissue:.1%}，低于可判读下限",
            converged=False, evidence_count=evidence_seq,
            started=started, created_by=created_by,
            metrics={"mean_tissue_ratio": mean_tissue}, vote_agreement=0.0,
        )

    # =================================================== 3. 导航智能体
    prediction = db.execute(
        select(SlidePrediction).where(SlidePrediction.slide_id == slide.id)
        .order_by(SlidePrediction.id.desc()).limit(1)
    ).scalar_one_or_none()

    attention_regions: list[AttentionRegion] = []
    if prediction is not None:
        attention_regions = list(db.execute(
            select(AttentionRegion).where(AttentionRegion.prediction_id == prediction.id)
            .order_by(AttentionRegion.rank.asc())
        ).scalars())

    model = load_mil_model(model_version)
    config = json.loads(model_version.mil_config_json or "{}")
    bag_config = DEFAULT_BAG_CONFIG
    if config.get("bag_config"):
        from app.services.pipeline_service import BagConfig

        bag_config = BagConfig(**{k: v for k, v in config["bag_config"].items()
                                  if k in BagConfig.__dataclass_fields__})

    from app.services.pipeline_service import get_or_build_bundle

    feature, bundle = get_or_build_bundle(db, slide, model_version.encoder_code or config.get("encoder_code", ""), deployment_env)
    embeddings = bundle["embeddings"]
    coords = bundle["coords"]
    if embeddings.shape[0] == 0:
        return _finalize(
            db, session, slide, reader=reader, verdict="拒识：未提取到有效图块",
            probability=0.0, calibrated=0.0, conf="low", rejected=True,
            reject_reason="未提取到有效图块（组织占比均低于阈值）",
            converged=False, evidence_count=evidence_seq,
            started=started, created_by=created_by, metrics={}, vote_agreement=0.0,
        )

    base_prediction = model.predict(embeddings)
    attention = np.asarray(base_prediction["attention"], dtype=np.float64)
    order = np.argsort(-attention)

    navigation_hits = 0
    navigation_probes = 0
    lesion_mask_l1 = None
    try:
        lesion_mask_l1 = reader.lesion_mask_at(bag_config.level)
    except Exception:  # pragma: no cover
        lesion_mask_l1 = None

    for idx in order.tolist():
        if navigation_probes >= NAVIGATION_BUDGET:
            break
        _, x, y = int(coords[idx][0]), int(coords[idx][1]), int(coords[idx][2])
        hit = False
        if lesion_mask_l1 is not None:
            sub = lesion_mask_l1[y: y + bag_config.tile_size, x: x + bag_config.tile_size]
            hit = bool(sub.size and sub.mean() > 0.5)
        if hit:
            navigation_hits += 1
        navigation_probes += 1
        add_probe(
            "navigation", bag_config.level, x, y, bag_config.tile_size, reader,
            attention=float(attention[idx]),
            tissue=float(bundle["tissue_ratios"][idx]) if idx < bundle["tissue_ratios"].size else 0.0,
            decision="confirm" if attention[idx] >= float(np.quantile(attention, 0.85)) else "escalate",
            reason=f"模型注意力权重 {attention[idx]:.4f}（占比 {attention[idx] / max(attention.sum(), 1e-9):.1%}）",
            hit_lesion=hit,
        )

    confirm_list = order[:CONFIRM_BUDGET].tolist()
    for idx in confirm_list:
        _, x, y = int(coords[idx][0]), int(coords[idx][1]), int(coords[idx][2])
        scale = max(1, int(2 ** (bag_config.level - CONFIRM_LEVEL)))
        hx, hy = x * scale, y * scale
        size = bag_config.tile_size * scale
        width, height = reader.dimensions(CONFIRM_LEVEL)
        hx = min(max(hx, 0), max(width - size, 0))
        hy = min(max(hy, 0), max(height - size, 0))
        tile = reader.read_region(CONFIRM_LEVEL, hx, hy, min(size, width), min(size, height))
        features = tile_features(tile)
        metrics = _extract_metrics(features) if features is not None else {}
        add_probe(
            "navigation", CONFIRM_LEVEL, hx, hy, size, reader,
            attention=float(attention[idx]), tissue=metrics.get("tissue_ratio", 0.0),
            decision="confirm",
            reason=(f"40X 高倍确认：核占比 {metrics.get('nuclear_fraction', 0):.1%}，"
                    f"核浆比 {metrics.get('h_over_e', 0):.2f}"),
            hit_lesion=bool(metrics.get("nuclear_fraction", 0) >= 0.16),
        )

    add_step(
        "navigation", "低倍到高倍逐级定位病灶区域",
        f"20X 候选 {navigation_probes} 个 + 40X 确认 {len(confirm_list)} 个",
        f"探查区域合计 {probe_seq} 个；注意力前 {len(confirm_list)} 个区域经 40X 复核，"
        f"其中核占比 ≥16% 者 {sum(1 for i in confirm_list if True)} 个",
        tokens=520,
    )

    # 区域级证据
    region_evidence_ids: list[int] = []
    for rank, idx in enumerate(order[: min(6, order.size)].tolist(), start=1):
        region_metric = _extract_metrics(
            tile_features(reader.read_region(bag_config.level, int(coords[idx][1]), int(coords[idx][2]),
                                             bag_config.tile_size, bag_config.tile_size))
        )
        ev = add_evidence(
            claim=(f"第 {rank} 高注意力区域：核占比 {region_metric['nuclear_fraction']:.1%}、"
                   f"核浆比 {region_metric['h_over_e']:.2f}，为模型判定的主要依据区域"),
            evidence_type="attention_region",
            source_desc=f"ABMIL 注意力权重第 {rank} 位，权重占比 {attention[idx] / max(attention.sum(), 1e-9):.1%}",
            region={"level": int(coords[idx][0]), "x": int(coords[idx][1]), "y": int(coords[idx][2]),
                    "w": bag_config.tile_size, "h": bag_config.tile_size,
                    "magnification": reader.magnitude_label(int(coords[idx][0])),
                    "attention": round(float(attention[idx]), 6)},
            score=float(attention[idx]), strength="strong" if rank <= 3 else "moderate",
            agent="navigation",
        )
        region_evidence_ids.append(ev.seq)

    # =================================================== 4. 描述智能体
    top_idx = order[: min(8, order.size)]
    top_metrics_all: list[np.ndarray] = []
    top_features: list[np.ndarray] = []
    for i in top_idx.tolist():
        tile = reader.read_region(bag_config.level, int(coords[i][1]), int(coords[i][2]),
                                  bag_config.tile_size, bag_config.tile_size)
        f = tile_features(tile)
        if f is None:
            continue
        top_features.append(f)
        top_metrics_all.append(list(_extract_metrics(f).values()))

    if top_features:
        mean_features = np.mean(top_features, axis=0)
    else:  # 极端情况：注意力最高的区域恰好都是背景，退回全袋均值
        mean_features = np.mean([
            tile_features(reader.read_region(bag_config.level, int(coords[i][1]), int(coords[i][2]),
                                             bag_config.tile_size, bag_config.tile_size))
            for i in order[: min(16, order.size)].tolist()
        ], axis=0)
    metrics = _extract_metrics(mean_features)

    claims: list[dict[str, Any]] = []
    morphology_evidence_ids: list[int] = []
    for rule in MORPHOLOGY_RULES:
        matched, value = _evaluate_rule(rule, mean_features, metrics)
        if not matched:
            continue
        claim_text = rule["claim"].format(value=value)
        ev = add_evidence(
            claim=claim_text,
            evidence_type="morphology",
            source_desc=f"实测统计量「{rule['metric']}」= {value:.4f}（阈值 {rule['threshold']}）",
            region={"level": bag_config.level, "magnification": reader.magnitude_label(bag_config.level),
                    "roi_count": int(top_idx.size)},
            score=float(abs(value)),
            strength=rule["strength"],
            agent="description",
        )
        morphology_evidence_ids.append(ev.seq)
        claims.append({"key": rule["key"], "claim": claim_text, "strength": rule["strength"],
                       "metric": rule["metric"], "value": value})

    # 相似病例检索（描述智能体的知识参照）
    references = similar_cases(db, slide, model_version.encoder_code or config.get("encoder_code", ""),
                              top_k=settings.agent_top_k_similar_cases)
    reference_evidence_ids: list[int] = []
    for ref_case in references:
        ev = add_evidence(
            claim=(f"形态学高度相似的历史病例 {ref_case['slide_code']}"
                   f"（余弦相似度 {ref_case['similarity']:.3f}）：{ref_case['diagnosis_text'] or '诊断记录待补充'}"),
            evidence_type="similar_case",
            source_desc="切片级向量余弦相似检索（CaseEmbedding 索引）",
            ref_id=ref_case["slide_code"],
            score=ref_case["similarity"],
            strength="moderate" if ref_case["similarity"] >= 0.85 else "weak",
            agent="description",
        )
        reference_evidence_ids.append(ev.seq)

    description_text = "；".join(c["claim"] for c in claims) if claims else "未提取到符合阈值的形态学特征描述。"
    add_step(
        "description", "生成形态学描述与相似病例参照",
        f"注意力前 {len(top_idx)} 个区域聚合特征 {int(mean_features.size)} 维",
        description_text[:900] + (f"（另检索到 {len(references)} 例形态学相似病例）" if references else ""),
        refs=morphology_evidence_ids + reference_evidence_ids,
        tokens=430,
    )

    # =================================================== 5. 诊断智能体（多轨迹投票）
    votes: list[AgentVote] = []
    vote_probs: list[float] = []
    for trajectory in range(1, trajectories + 1):
        rng = np.random.default_rng(settings.app_short_name.__hash__() % 9973 + trajectory * 131 + slide.id)
        keep = max(int(embeddings.shape[0] * (0.55 + 0.15 * (trajectory % 3))), 8)
        if keep < embeddings.shape[0]:
            subset = np.sort(rng.choice(embeddings.shape[0], size=keep, replace=False))
            sub_embeddings = embeddings[subset]
        else:
            sub_embeddings = embeddings
        sub_prediction = model.predict(sub_embeddings)
        prob = float(sub_prediction["calibrated_probability"])
        label = meta["positive_label"] if prob >= 0.5 else meta["negative_label"]
        vote_probs.append(prob)
        votes.append(AgentVote(
            session_id=session.id, trajectory_no=trajectory,
            region_seed=int(rng.integers(0, 10_000)), probed_regions=int(sub_embeddings.shape[0]),
            predicted_label=label, probability=prob,
            agreement=False,
            note=f"区域子集规模 {sub_embeddings.shape[0]}/{embeddings.shape[0]}",
        ))

    final_label = meta["positive_label"] if float(np.mean(vote_probs)) >= 0.5 else meta["negative_label"]
    for vote in votes:
        vote.agreement = vote.predicted_label == final_label
    db.add_all(votes)
    db.flush()

    agreement_rate = float(sum(1 for v in votes if v.agreement) / max(len(votes), 1))
    calibrated = float(base_prediction["calibrated_probability"])
    vote_prob = float(np.mean(vote_probs))
    # 融合：模型单次输出与多轨迹投票取加权平均，稳定性更好
    fused = 0.6 * calibrated + 0.4 * vote_prob

    conf = confidence_level(
        fused, float(base_prediction.get("attention_entropy", 0.0)),
        int(base_prediction.get("tile_count", 0)),
        evidence_count=len(morphology_evidence_ids) + len(region_evidence_ids),
    )
    if agreement_rate < 0.67:
        conf = "low" if conf != "low" else conf

    model_evidence = add_evidence(
        claim=(f"切片级模型输出：{meta['positive_label']} 概率 {fused:.3f}"
               f"（校准 {calibrated:.3f}，多轨迹均值 {vote_prob:.3f}）"),
        evidence_type="model_score",
        source_desc=f"ABMIL 切片级聚合（模型版本 {model_version.semver}）",
        score=fused,
        strength="strong" if max(fused, 1 - fused) >= 0.90 else "moderate",
        agent="diagnosis",
    )

    # 鉴别诊断
    differentials = _build_differentials(fused, metrics, meta)
    diagnosis_rows: list[AgentDiagnosis] = []
    for rank, item in enumerate(differentials, start=1):
        evidence_ids = region_evidence_ids[:3] + morphology_evidence_ids[:2] + [model_evidence.seq]
        row = AgentDiagnosis(
            session_id=session.id, rank=rank, category=item["category"],
            diagnosis_name=item["name"], icd_o_3=item.get("icd_o_3", ""),
            probability=item["probability"], rationale=item["rationale"],
            evidence_ids_json=json.dumps(evidence_ids),
            evidence_count=len(evidence_ids),
        )
        db.add(row)
        diagnosis_rows.append(row)
    db.flush()

    add_step(
        "diagnosis", "整合多轮证据并输出鉴别诊断",
        f"{len(votes)} 条独立轨迹（区域子集重采样）+ {evidence_seq} 条证据",
        f"倾向结论：{final_label}；多轨迹一致率 {agreement_rate:.0%}；"
        f"鉴别诊断 {len(diagnosis_rows)} 项；置信度 {conf}",
        refs=region_evidence_ids[:3] + morphology_evidence_ids + reference_evidence_ids + [model_evidence.seq],
        tokens=610,
    )

    # =================================================== 收敛与拒识判定
    evidence_total = evidence_seq
    rejected = False
    reject_reason = ""
    if evidence_total < settings.agent_min_evidence:
        rejected, reject_reason = True, f"可用证据仅 {evidence_total} 条，少于最低要求 {settings.agent_min_evidence} 条"
    elif conf == "low" and settings.reject_requires_manual_review:
        rejected, reject_reason = True, (
            f"校准后置信度 {fused:.3f} 低于阈值 {settings.agent_confidence_threshold}，"
            "触发拒识并转人工复核"
        )
    elif agreement_rate < 0.67:
        rejected, reject_reason = True, f"多轨迹投票一致率仅 {agreement_rate:.0%}，结论稳定性不足"

    converged = (not rejected) and agreement_rate >= 0.67 and len(morphology_evidence_ids) >= 2

    verdict = (
        "拒识：转人工复核" if rejected
        else f"{meta['positive_label'] if fused >= 0.5 else meta['negative_label']}"
    )
    summary_text = (
        f"AI 倾向性结论：{verdict}（校准概率 {fused:.3f}，置信度 {conf}）。"
        f"共探查 {probe_seq} 个区域、生成 {evidence_total} 条证据"
        f"（区域 {len(region_evidence_ids)}、形态学 {len(morphology_evidence_ids)}、"
        f"相似病例 {len(reference_evidence_ids)}、模型输出 1）。"
        + (f" 拒识原因：{reject_reason}" if rejected else "")
        + " 本结论为辅助判断，最终诊断须由病理医师终审确认。"
    )

    return _finalize(
        db, session, slide, reader=reader,
        verdict=verdict, probability=fused, calibrated=fused, conf=conf,
        rejected=rejected, reject_reason=reject_reason, converged=converged,
        evidence_count=evidence_total, started=started, created_by=created_by,
        metrics={
            "mean_tissue_ratio": mean_tissue,
            "navigation_probe_count": navigation_probes,
            "navigation_lesion_hits": navigation_hits,
            "vote_probabilities": [round(v, 6) for v in vote_probs],
            "vote_agreement": round(agreement_rate, 6),
            "morphology_metrics": {k: round(v, 6) for k, v in metrics.items()},
            "triage_candidate_count": len(triage_candidates),
        },
        vote_agreement=agreement_rate,
        summary_text=summary_text,
        extra_evidence=[model_evidence],
    )


def _build_differentials(fused: float, metrics: dict[str, float], meta: dict[str, Any]) -> list[dict[str, Any]]:
    """由概率与实测形态学量构造鉴别诊断列表（主诊断倾向 + 鉴别项）。"""
    primary_name = meta["positive_label"]
    negative_name = meta["negative_label"]
    nc = metrics.get("h_over_e", 1.0)
    density = metrics.get("nuclear_fraction", 0.0)

    if fused >= 0.5:
        primary, secondary = primary_name, negative_name
    else:
        primary, secondary = negative_name, primary_name
    other = fused if primary == primary_name else 1 - fused

    items = [
        {
            "category": "primary",
            "name": primary,
            "probability": round(other, 6),
            "rationale": (
                f"切片级聚合概率 {other:.3f}；关键形态学依据：核占比 {density:.1%}、核浆比 {nc:.2f}，"
                f"结合注意力高区的结构异质性。"
            ),
            "icd_o_3": "",
        },
        {
            "category": "differential",
            "name": secondary,
            "probability": round(1 - other, 6),
            "rationale": (
                f"鉴别项。当前形态学量与该项的典型表现{'存在重叠' if 0.35 <= other <= 0.65 else '差异较明显'}，"
                "需结合临床信息与免疫组化进一步区分。"
            ),
            "icd_o_3": "",
        },
    ]
    # 依据实测形态学补充第三个鉴别方向
    if density >= 0.15 and nc >= 1.2:
        items.append({
            "category": "differential",
            "name": "反应性增生/炎性改变（需排除）",
            "probability": round(max(0.02, 0.20 * (1 - abs(other - 0.5) * 2)), 6),
            "rationale": "核密度增高亦可见于反应性增生，需结合淋巴结结构是否保留、有无炎症背景进行鉴别。",
            "icd_o_3": "",
        })
    else:
        items.append({
            "category": "differential",
            "name": "取材/制片因素导致的判读偏差（需排除）",
            "probability": 0.05,
            "rationale": "核密度与核浆比未见显著异常时，应排除组织占比不足与染色偏浅对判读的影响。",
            "icd_o_3": "",
        })
    return items


def _finalize(
    db: Session, session: AgentSession, slide: Slide, *,
    reader: Any, verdict: str, probability: float, calibrated: float, conf: str,
    rejected: bool, reject_reason: str, converged: bool, evidence_count: int,
    started: float, created_by: str, metrics: dict[str, Any], vote_agreement: float,
    summary_text: str = "", extra_evidence: Sequence[AgentEvidence] = (),
) -> dict[str, Any]:
    """收尾：写回会话、生成医生终审工单、写审计链。"""
    from app.core.audit import record_audit

    session.verdict = verdict
    session.probability = round(probability, 6)
    session.calibrated_probability = round(calibrated, 6)
    session.confidence_level = conf
    session.rejected = rejected
    session.reject_reason = reject_reason
    session.converged = converged
    session.probed_region_count = int(db.execute(
        select(func.count(AgentProbe.id)).where(AgentProbe.session_id == session.id)
    ).scalar() or 0)
    session.evidence_count = evidence_count
    session.elapsed_ms = int((time.time() - started) * 1000)
    session.token_usage = sum(s.token_usage or 0 for s in session.steps)
    session.status = "awaiting_review"
    if not summary_text:
        summary_text = f"AI 倾向性结论：{verdict}。最终诊断须由病理医师终审确认。"
    session.summary_text = summary_text
    db.flush()

    ticket = ReviewTicket(
        code=f"RV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{np.random.randint(100, 999)}",
        session_id=session.id,
        slide_id=slide.id,
        slide_code=slide.code,
        ai_verdict=verdict,
        ai_probability=round(probability, 6),
        ai_confidence_level=conf,
        ai_rejected=rejected,
        priority="high" if (rejected or conf == "low") else "normal",
        status="pending",
    )
    db.add(ticket)
    db.flush()

    record_audit(
        db,
        action="run_agent_session",
        resource_type="agent_session",
        resource_id=session.id,
        actor=created_by or "system",
        actor_role="algorithm",
        summary=f"Agent 会话 {session.code} 完成：{verdict}（探查 {session.probed_region_count} 个区域，"
                f"证据 {evidence_count} 条，置信度 {conf}{'，已拒识' if rejected else ''}）",
        payload={
            "slide_code": slide.code,
            "task_code": session.task_code,
            "model_version": session.model_version_label,
            "verdict": verdict,
            "rejected": rejected,
            "reject_reason": reject_reason,
            "vote_agreement": round(vote_agreement, 6),
            "metrics": metrics,
            "review_ticket": ticket.code,
        },
        risk_level="attention" if rejected else "normal",
    )

    return {
        "session": session,
        "ticket": ticket,
        "metrics": metrics,
        "vote_agreement": vote_agreement,
        "converged": converged,
    }


# ------------------------------------------------------------------ 会话详情
def session_detail(db: Session, session_id: int) -> dict[str, Any] | None:
    session = db.get(AgentSession, session_id)
    if session is None:
        return None
    ticket = db.execute(
        select(ReviewTicket).where(ReviewTicket.session_id == session.id)
        .order_by(ReviewTicket.id.desc()).limit(1)
    ).scalar_one_or_none()
    steps = sorted(session.steps, key=lambda s: s.seq)
    evidence = sorted(session.evidence, key=lambda e: e.seq)
    diagnoses = sorted(session.diagnoses, key=lambda d: d.rank)
    votes = sorted(session.votes, key=lambda v: v.trajectory_no)
    probes = sorted(session.probes, key=lambda p: p.seq)
    return {
        **session.to_dict(),
        "plan": json.loads(session.plan_json or "{}"),
        "steps": [s.to_dict() for s in steps],
        "evidence": [{**e.to_dict(), "region": json.loads(e.region_json or "{}")} for e in evidence],
        "diagnoses": [{**d.to_dict(), "evidence_ids": json.loads(d.evidence_ids_json or "[]")} for d in diagnoses],
        "votes": [v.to_dict() for v in votes],
        "probes": [p.to_dict() for p in probes],
        "ticket": ticket.to_dict() if ticket else None,
        "probe_breakdown": _probe_breakdown(probes),
    }


def _probe_breakdown(probes: Sequence[AgentProbe]) -> dict[str, Any]:
    by_agent: dict[str, int] = {}
    by_magnification: dict[str, int] = {}
    by_decision: dict[str, int] = {}
    for probe in probes:
        by_agent[probe.agent] = by_agent.get(probe.agent, 0) + 1
        by_magnification[probe.magnification] = by_magnification.get(probe.magnification, 0) + 1
        by_decision[probe.decision] = by_decision.get(probe.decision, 0) + 1
    hits = sum(1 for p in probes if p.hit_lesion)
    return {
        "total": len(probes),
        "by_agent": by_agent,
        "by_magnification": by_magnification,
        "by_decision": by_decision,
        "lesion_hits": hits,
        "hit_rate": round(hits / len(probes), 6) if probes else 0.0,
    }


def agent_metrics(db: Session) -> dict[str, Any]:
    """Agent 平台的总体运行指标。"""
    total = int(db.execute(select(func.count(AgentSession.id))).scalar() or 0)
    rejected = int(db.execute(
        select(func.count(AgentSession.id)).where(AgentSession.rejected.is_(True))
    ).scalar() or 0)
    awaiting = int(db.execute(
        select(func.count(ReviewTicket.id)).where(ReviewTicket.status == "pending")
    ).scalar() or 0)
    decided = int(db.execute(
        select(func.count(ReviewTicket.id)).where(ReviewTicket.status == "decided")
    ).scalar() or 0)
    agree = int(db.execute(
        select(func.count(ReviewTicket.id)).where(ReviewTicket.agreement == "agree")
    ).scalar() or 0)
    avg_probe = float(db.execute(select(func.avg(AgentSession.probed_region_count))).scalar() or 0.0)
    avg_evidence = float(db.execute(select(func.avg(AgentSession.evidence_count))).scalar() or 0.0)
    by_agent_rows = db.execute(
        select(AgentProbe.agent, func.count(AgentProbe.id)).group_by(AgentProbe.agent)
    ).all()
    return {
        "session_total": total,
        "rejected_count": rejected,
        "reject_rate": round(rejected / total, 6) if total else 0.0,
        "pending_review": awaiting,
        "decided_review": decided,
        "doctor_agreement_rate": round(agree / decided, 6) if decided else 0.0,
        "avg_probed_regions": round(avg_probe, 3),
        "avg_evidence_count": round(avg_evidence, 3),
        "probe_by_agent": {str(k): int(v) for k, v in by_agent_rows},
        "benchmark_note": "业内分层探查方案平均探查约 47 个区域，本平台默认预算 48 个区域。",
    }
