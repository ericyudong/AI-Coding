"""种子数据入口：静态数据 + 运行期数据（训练 / 推理 / 评测 / Agent / 联邦 / 看板）。

用法：
    python -m app.seed --reset                 # 重建全部演示数据（含训练与推理，约 3 分钟）
    python -m app.seed --reset --quick         # 减少切片数量，约 1 分钟
    python -m app.seed --reset --skip-model    # 只灌静态数据，不训练（秒级，用于纯接口调试）

数据口径：演示数据集为 50—80 张合成切片（SITE-A 院内主中心 / SITE-B 协作中心 /
SITE-C 外部验证中心），每张切片在 20X 层抽取约 40—64 个图块构成 MIL 袋。
切片图像由 `SyntheticWSIReader` 确定性生成，具备真实 H&E 染色光谱特性与分层难度
（含微灶困难阳性与反应性增生模仿阴性），因此跨中心衰减、概率标定与 MRMC 对照
都是真实可观测的现象，而不是人为造出来的漂亮数字。

真实使用时把 `Slide.file_path` 指向院内实际切片即可，其余链路完全不变。
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal, drop_all, init_db
from app.models.agent import AgentSession, ReviewTicket
from app.models.evaluation import EvalDataset, EvalDatasetItem, EvalMetric, EvalRocPoint, EvalRun, MrMcComparison
from app.models.modeling import ModelBase
from app.models.pipeline import SlidePrediction
from app.models.asset import Slide
from app.services import compliance_service, ops_service
from app.services.agent_service import run_agent_session
from app.services.evaluation_service import full_report, generalization_gap, mrmc_report, roc_curve_points
from app.services.pipeline_service import run_inference, train_mil_model
from app.seed_data import EXTERNAL_SITE, IN_DOMAIN_SITES, seed_all_static

logger = logging.getLogger("seed")
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout, force=True)


def _log(message: str, *args) -> None:
    """同时走 logging 与 print，保证在任何重定向/管道环境下都能看到进度。"""
    text = message % args if args else message
    logger.info(text)


# =============================================================== 训练与推理
def seed_model_runs(db, base: ModelBase, slides: list[Slide]) -> dict:
    he_slides = [s for s in slides if s.staining == "H&E"]
    in_house = [(s, 1.0 if s.has_lesion else 0.0) for s in he_slides if s.site_code in IN_DOMAIN_SITES]
    val_size = max(8, int(len(in_house) * 0.2))
    val = in_house[-val_size:]
    train = in_house[:-val_size] or in_house

    _log("[A] Stage A—C：对 %d 张切片做特征预计算 + ABMIL 训练…", len(train))
    started = time.time()
    result = train_mil_model(
        db, base=base, encoder_code="hibou-b-synth", task_code="lymph_node_metastasis",
        train_slides=train, val_slides=val, semver="SH-PATH-V1-v1.0.0",
        triggered_by="seed", gpu_hourly_cost=28.0,
    )
    version = result["version"]
    version.is_registration_candidate = True
    db.flush()
    _log("[A] 训练完成（%.0fs）：内部验证 AUROC %s，平均袋大小 %s",
                time.time() - started,
                (result["metrics"].get("validation") or {}).get("auroc"),
                result["metrics"].get("tile_bag_mean"))

    _log("[B] 推理：对全部 %d 张 H&E 切片运行切片级推理并生成注意力热力图…", len(he_slides))
    started = time.time()
    inference = run_inference(
        db, slides=he_slides, model_version=version, task_code="lymph_node_metastasis",
        triggered_by="seed", name="淋巴结转移检测 · 批量推理",
    )
    _log("[B] 推理完成（%.0fs）：%s", time.time() - started,
                json.dumps(inference["summary"]["decisions"], ensure_ascii=False))

    _log("[C] 自研编码器对照验证（M4 里程碑证据：许可风险清零）…")
    selfdev = train_mil_model(
        db, base=base, encoder_code="sh-encoder-b0", task_code="lymph_node_metastasis",
        train_slides=train, val_slides=val, semver="SH-PATH-V1-v0.9.0-selfdev",
        triggered_by="seed", gpu_hourly_cost=28.0,
    )
    selfdev_version = selfdev["version"]
    selfdev_version.changelog = (
        "自研编码器（sh-encoder-b0）对照版本，用于 M4 里程碑"
        "「性能不劣于参照权重，许可风险清零」的验收。"
    )
    reference_auroc = float((result["metrics"].get("validation") or {}).get("auroc") or 0.0)
    selfdev_auroc = float((selfdev["metrics"].get("validation") or {}).get("auroc") or 0.0)
    selfdev_version.metrics_json = json.dumps({
        **selfdev["metrics"],
        "milestone_m4": {
            "reference_encoder": "hibou-b-synth",
            "reference_auroc": reference_auroc,
            "selfdev_encoder": "sh-encoder-b0",
            "selfdev_auroc": selfdev_auroc,
            "not_worse": selfdev_auroc >= reference_auroc - 0.02,
            "acceptance": "性能不劣于参照权重（允许 0.02 以内波动），许可风险清零",
        },
    }, ensure_ascii=False)
    db.flush()
    _log("[C] 自研编码器 AUROC %s（参照 %s）", selfdev_auroc, reference_auroc)

    return {
        "version": version, "selfdev_version": selfdev_version,
        "he_slides": he_slides, "eval_slides": [
            (s, 1.0 if s.has_lesion else 0.0) for s in he_slides if s.site_code == EXTERNAL_SITE
        ],
        "inference": inference,
    }


# =============================================================== 评测
def seed_evaluation(db, runs: dict) -> None:
    version = runs["version"]
    he_slides = runs["he_slides"]
    internal = [s for s in he_slides if s.site_code in IN_DOMAIN_SITES]
    external = [s for s in he_slides if s.site_code == EXTERNAL_SITE]

    preds = {
        p.slide_code: p for p in db.execute(
            select(SlidePrediction).where(SlidePrediction.model_version_id == version.id)
        ).scalars()
    }

    datasets = [
        ("DS-INT-VAL", "内部验证集（主中心 + 协作中心）", "internal_val", False, internal),
        ("DS-EXT-C", "外部多中心验证集（SITE-C）", "external", True, external),
        ("DS-REGRESSION", "回归评测集（版本迭代用）", "regression", False, internal[:8]),
    ]
    rng = random.Random(8848)
    dataset_rows: dict[str, EvalDataset] = {}
    for code, name, kind, is_external, slides in datasets:
        if not slides:
            continue
        positives = sum(1 for s in slides if s.has_lesion)
        dataset = EvalDataset(
            code=code, name=name, task_code="lymph_node_metastasis", label_name="转移阳性",
            dataset_kind=kind, is_external=is_external, slide_count=len(slides),
            patient_count=len({s.patient_pseudo_id for s in slides}), positive_count=positives,
            positive_rate=round(positives / len(slides), 6),
            site_count=len({s.site_code for s in slides}), version="v1.0", frozen=True,
            description=f"{name}；以医生标注的最终诊断结论为金标准。", owner_name="赵工",
        )
        db.add(dataset)
        db.flush()
        for slide in slides:
            db.add(EvalDatasetItem(
                dataset_id=dataset.id, slide_id=slide.id, slide_code=slide.code,
                label_truth="转移阳性" if slide.has_lesion else "转移阴性",
                site_code=slide.site_code, case_no=slide.case_no,
                reader_a_label=_reader_label(slide.has_lesion, 0.93, 0.88, rng),
                reader_b_label=_reader_label(slide.has_lesion, 0.90, 0.91, rng),
            ))
        dataset_rows[code] = dataset
    db.flush()

    for code, dataset in dataset_rows.items():
        items = list(db.execute(
            select(EvalDatasetItem).where(EvalDatasetItem.dataset_id == dataset.id)
        ).scalars())
        y = [1.0 if item.label_truth == "转移阳性" else 0.0 for item in items]
        scores = [
            preds[item.slide_code].calibrated_probability if item.slide_code in preds else 0.5
            for item in items
        ]
        groups = [item.site_code for item in items]
        report = full_report(y, scores, threshold=0.5, groups=groups, bootstrap_rounds=300)
        points = roc_curve_points(y, scores, max_points=80)
        gap = generalization_gap(report.get("by_group") or {}, in_domain_keys=IN_DOMAIN_SITES)

        run = EvalRun(
            code=f"ER-{code}", dataset_id=dataset.id, model_version_id=version.id,
            model_version_label=version.semver, task_code="lymph_node_metastasis",
            threshold=0.5, bootstrap_rounds=300, status="succeeded",
            sample_count=report["sample_count"], positive_count=report["positive_count"],
            auroc=report["auroc"], auprc=report["auprc"], accuracy=report["accuracy"],
            sensitivity=report["sensitivity"], specificity=report["specificity"],
            ppv=report["ppv"], npv=report["npv"], f1=report["f1"],
            brier=report["brier"], ece=report["ece"],
            auroc_ci_low=report["auroc_ci_low"], auroc_ci_high=report["auroc_ci_high"],
            confusion_json=json.dumps(report["confusion"], ensure_ascii=False),
            by_site_json=json.dumps(report.get("by_group") or {}, ensure_ascii=False),
            reliability_json=json.dumps(report.get("reliability") or [], ensure_ascii=False),
            generalization_json=json.dumps(gap, ensure_ascii=False),
            started_at=datetime.now().isoformat(timespec="seconds"),
            finished_at=datetime.now().isoformat(timespec="seconds"),
            elapsed_ms=1400,
            passed=report["auroc"] >= 0.90,
            pass_note=("达到预设 AUROC ≥ 0.90 的里程碑门槛" if report["auroc"] >= 0.90
                       else "未达预设 AUROC ≥ 0.90 门槛，需继续迭代或调整适应症范围"),
            triggered_by="seed",
        )
        db.add(run)
        db.flush()
        for point in points:
            db.add(EvalRocPoint(run_id=run.id, group_key="overall", **point))
        for key, label, value, low, high, vtype in (
            ("auroc", "AUROC", report["auroc"], report["auroc_ci_low"], report["auroc_ci_high"], "ratio"),
            ("auprc", "AUPRC", report["auprc"], 0.0, 0.0, "ratio"),
            ("accuracy", "准确率", report["accuracy"], 0.0, 0.0, "ratio"),
            ("sensitivity", "敏感度", report["sensitivity"], 0.0, 0.0, "ratio"),
            ("specificity", "特异度", report["specificity"], 0.0, 0.0, "ratio"),
            ("ppv", "阳性预测值", report["ppv"], 0.0, 0.0, "ratio"),
            ("npv", "阴性预测值", report["npv"], 0.0, 0.0, "ratio"),
            ("f1", "F1", report["f1"], 0.0, 0.0, "ratio"),
            ("brier", "Brier 分数", report["brier"], 0.0, 0.0, "score"),
            ("ece", "期望校准误差(ECE)", report["ece"], 0.0, 0.0, "score"),
        ):
            db.add(EvalMetric(
                run_id=run.id, group_key="overall", metric_key=key, metric_label=label,
                value=value, ci_low=low, ci_high=high,
                sample_count=report["sample_count"], value_type=vtype,
            ))
        for site, payload in (report.get("by_group") or {}).items():
            db.add(EvalMetric(
                run_id=run.id, group_key=f"site:{site}", metric_key="auroc", metric_label="AUROC",
                value=payload["auroc"], sample_count=payload["sample_count"], value_type="ratio",
            ))
        db.flush()

        if code == "DS-EXT-C" and items:
            mrmc = mrmc_report(
                y, scores, [item.reader_a_label for item in items],
                [item.reader_b_label for item in items],
                positive_label="转移阳性", bootstrap_rounds=300,
            )
            db.add(MrMcComparison(
                code=f"MM-{code}", dataset_id=dataset.id, ai_run_id=run.id,
                model_version_label=version.semver,
                reader_a_name="陈医师", reader_a_title="副主任医师",
                reader_b_name="吴医师", reader_b_title="主治医师",
                auc_ai=mrmc["auc_ai"], auc_reader_a=mrmc["auc_reader_a"],
                auc_reader_b=mrmc["auc_reader_b"], reader_average_auc=mrmc["reader_average_auc"],
                delta_ai_vs_reader_a=mrmc["delta_ai_vs_reader_a"],
                delta_ai_vs_reader_a_ci_low=mrmc["delta_ai_vs_reader_a_ci_low"],
                delta_ai_vs_reader_a_ci_high=mrmc["delta_ai_vs_reader_a_ci_high"],
                p_value=mrmc["p_value"], method=mrmc["method"], conclusion=mrmc["conclusion"],
                status="done",
                note="参照《人工智能医疗器械注册审查指导原则》以 MRMC 方式设计对照。",
            ))
            _log("  MRMC：AI AUC %.4f vs 阅片者均值 %.4f（p=%.3f）",
                        mrmc["auc_ai"], mrmc["reader_average_auc"], mrmc["p_value"])
        db.flush()
        _log("  评测 %s：AUROC %.4f（95%%CI %.3f—%.3f）Sens %.3f Spec %.3f ECE %.4f",
                    code, report["auroc"], report["auroc_ci_low"], report["auroc_ci_high"],
                    report["sensitivity"], report["specificity"], report["ece"])
        if gap.get("gap") is not None:
            _log("    跨中心泛化：院内 %.4f → 院外 %.4f（衰减 %.4f，%s）",
                        gap["in_domain_auroc"], gap["out_domain_auroc"], gap["gap"], gap["severity"])


def _reader_label(truth_positive: bool, sensitivity: float, specificity: float,
                  rng: random.Random) -> str:
    if truth_positive:
        return "转移阳性" if rng.random() < sensitivity else "转移阴性"
    return "转移阴性" if rng.random() < specificity else "转移阳性"


# =============================================================== Agent 会话
def seed_agent_sessions(db, runs: dict) -> int:
    version = runs["version"]
    all_human = runs["he_slides"] + [s for s in db.execute(select(Slide)).scalars()
                                     if s.staining != "H&E"]
    he_slides = runs["he_slides"]
    special = [s for s in all_human if s.staining != "H&E"]

    preds = {
        p.slide_code: p for p in db.execute(
            select(SlidePrediction).where(SlidePrediction.slide_code.in_([s.code for s in he_slides]))
        ).scalars()
    }
    ranked = sorted(
        he_slides,
        key=lambda s: abs((preds.get(s.code).calibrated_probability if preds.get(s.code) else 0.5) - 0.5),
    )
    targets: list = []
    for candidate in list(reversed(ranked[-3:])) + ranked[:3]:    # 最确定的 3 例 + 最接近边界的 3 例
        if candidate not in targets:
            targets.append(candidate)
    positives = [s for s in he_slides if s.has_lesion and s not in targets]
    negatives = [s for s in he_slides if not s.has_lesion and s not in targets]
    for candidate in (positives[:1] + negatives[:1]):
        if candidate not in targets:
            targets.append(candidate)

    created = 0
    for slide in targets[:7]:
        run_agent_session(
            db, slide=slide, model_version=version, task_code="lymph_node_metastasis",
            question=f"该淋巴结切片是否存在转移灶？（切片 {slide.code}）",
            created_by="algo01",
        )
        created += 1
    for slide in special[:1]:
        run_agent_session(
            db, slide=slide, model_version=version, task_code="cervical_cytology",
            question="该宫颈细胞学标本是否存在阳性病变？",
            created_by="algo01",
        )
        created += 1
    db.flush()

    # 医生终审
    plan = [
        ("agree", "与 AI 倾向一致，形态学依据充分。"),
        ("agree", "同意，AI 标注的注意力高区与我的判读一致。"),
        ("modify", "AI 提示方向正确，但转移灶范围较其标注更大，已修正区域。"),
        ("agree", "同意，结合临床信息判断一致。"),
        ("disagree", "该区域为反应性增生，AI 判断过于敏感，已否定。"),
    ]
    from app.models.system import User

    doctors = [
        db.execute(select(User).where(User.username == "doctor01")).scalar_one(),
        db.execute(select(User).where(User.username == "doctor02")).scalar_one(),
    ]
    tickets = list(db.execute(select(ReviewTicket).order_by(ReviewTicket.id.asc())).scalars())
    decided = 0
    for index, ticket in enumerate(tickets):
        if index >= 5:
            break
        agreement, comment = plan[index % len(plan)]
        doctor = doctors[index % len(doctors)]
        ticket.status = "decided"
        ticket.claimed_by = doctor.username
        ticket.doctor_name = doctor.real_name
        ticket.agreement = agreement
        ticket.doctor_verdict = ticket.ai_verdict if agreement != "disagree" else "转移阴性"
        ticket.final_label = ticket.doctor_verdict
        ticket.comments = comment
        ticket.turnaround_min = 4 + index * 3
        ticket.decided_at = (datetime.now() - timedelta(minutes=60 - index * 9)).isoformat(timespec="seconds")
        session = db.get(AgentSession, ticket.session_id)
        if session:
            session.status = "reviewed"
        decided += 1
    db.flush()

    rejected = int(db.execute(
        select(__import__("sqlalchemy").func.count(AgentSession.id)).where(AgentSession.rejected.is_(True))
    ).scalar() or 0)
    _log("  Agent 会话 %d 次（其中拒识 %d 次），医生终审已判定 %d 例", created, rejected, decided)
    return created


# =============================================================== 联邦
def seed_federated(db, runs: dict) -> None:
    from app.models.edge import FederatedJob
    from app.services.edge_service import run_federated_job

    job = FederatedJob(
        code="FJ-2026-01", name="跨中心联邦式增量微调（第一轮）",
        base_version_id=runs["version"].id, base_version_label=runs["version"].semver,
        strategy="fedavg", target_rounds=4, min_clients=2, local_epochs=25, learning_rate=0.02,
        metric_key="auroc", target_metric=0.90,
        note="应对风险 R3 跨中心泛化衰减：各中心用本地数据增量训练，只上传模型参数更新。",
    )
    db.add(job)
    db.flush()
    try:
        outcome = run_federated_job(
            db, job=job, base_version=runs["version"], encoder_code="hibou-b-synth",
            rounds=4, local_epochs=25, triggered_by="seed",
        )
        _log("  联邦任务完成：全局 AUROC %.4f → %.4f（%.2f MB 参数上传，样本出域 0 次）",
                    job.global_metric_init, job.global_metric_final,
                    job.upload_bytes_total / 1024 / 1024)
    except Exception as exc:  # pragma: no cover
        _log("  联邦任务未完成（%s），已跳过", exc)
        db.rollback()


# =============================================================== 合规与看板
def seed_compliance_runtime(db, runs: dict) -> None:
    compliance_service.run_boundary_check(db, checked_by="reg01")
    compliance_service.build_explainability_package(db, runs["version"], created_by="reg01")
    if runs.get("selfdev_version"):
        compliance_service.build_explainability_package(db, runs["selfdev_version"], created_by="reg01")
    db.flush()
    readiness = compliance_service.registration_readiness(db)
    _log("  注册就绪度 %.0f%%（%d/%d 项通过）%s", readiness["readiness_score"] * 100,
                readiness["passed_count"], readiness["total_count"], readiness["verdict"])


def seed_dashboards(db) -> None:
    from datetime import date, timedelta

    for offset in range(3, -1, -1):
        lookback = date.today() - timedelta(days=offset * 14)
        ops_service.snapshot_kpi(db, lookback.isoformat())
    db.flush()
    _log("  KPI 快照 %d 期已生成", 4)


# =============================================================== 主流程
def run(reset: bool = False, quick: bool = False, skip_model: bool = False) -> dict:
    started = time.time()
    if reset:
        _log("重建数据库结构…")
        drop_all()
    init_db()

    db = SessionLocal()
    try:
        context = seed_all_static(db, quick=quick)
        runs: dict = {"version": None, "selfdev_version": None, "he_slides": []}
        if not skip_model:
            _log("[训练与推理] …")
            runs = seed_model_runs(db, context["base"], context["slides"])
            db.commit()
            _log("[评测基座] …")
            seed_evaluation(db, runs)
            db.commit()
            _log("[Agent 平台] …")
            seed_agent_sessions(db, runs)
            db.commit()
            _log("[云边协同与联邦学习] …")
            seed_federated(db, runs)
            db.commit()
            _log("[合规与注册就绪度] …")
            seed_compliance_runtime(db, runs)
            db.commit()
        else:
            _log("已跳过训练/推理/评测/Agent/联邦（--skip-model）")
            compliance_service.run_boundary_check(db, checked_by="reg01")
            db.commit()

        _log("[运营看板] …")
        seed_dashboards(db)
        db.commit()

        summary = _summary(db, runs)
        _log("=" * 68)
        _log("种子数据完成，总耗时 %.0f 秒", time.time() - started)
        for key, value in summary.items():
            _log("  %-26s %s", key, value)
        _log("=" * 68)
        _log("启动后端：python run.py            （http://127.0.0.1:8100/docs）")
        _log("启动前端：cd frontend && npm start （http://127.0.0.1:8101）")
        _log("演示账号（口令均满足密码策略）：")
        _log("  admin/Admin@2026        系统管理员（全院数据范围）")
        _log("  cmo/Cmo@2026            首席医学官（本机构）")
        _log("  doctor01/Doctor@2026    病理医师（仅 SITE-A）")
        _log("  algo01/Algo@2026        算法工程师（本机构）")
        _log("  reg01/Reg@2026          注册与合规专员")
        _log("  ops01/Ops@2026          科室运营（只读）")
        return summary
    finally:
        db.close()


def _summary(db, runs: dict) -> dict:
    from sqlalchemy import func

    from app.models.asset import SlideFeature

    def count(model) -> int:
        return int(db.execute(select(func.count(model.id))).scalar() or 0)

    return {
        "数据资产 / 切片": f"{count(EvalDataset) and 3} / {count(Slide)}",
        "已提取特征切片": count(SlideFeature),
        "模型版本": count(__import__("app.models.modeling", fromlist=["ModelVersion"]).ModelVersion),
        "推理任务 / 切片预测": count(__import__("app.models.pipeline", fromlist=["InferenceJob"]).InferenceJob),
        "Agent 会话": count(AgentSession),
        "评测运行": count(EvalRun),
        "医生终审工单": count(ReviewTicket),
        "审计链记录": count(__import__("app.models.compliance", fromlist=["AuditChainRecord"]).AuditChainRecord),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartHealth 种子数据")
    parser.add_argument("--reset", action="store_true", help="先删除全部表再重建")
    parser.add_argument("--quick", action="store_true", help="减少切片数量（约 1 分钟）")
    parser.add_argument("--skip-model", action="store_true", help="跳过训练/推理/评测/Agent/联邦")
    args = parser.parse_args()
    run(reset=args.reset, quick=args.quick, skip_model=args.skip_model)


if __name__ == "__main__":
    main()
