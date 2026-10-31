"""前端契约校验：逐条核对控制台各视图读取的字段是否真实存在。

后端自测（selftest_api.py）验证「接口可达且语义正确」；
本脚本验证「前端读的每个字段后端都给了」——这是前后端联调最容易漏的一层。

    python scripts/selftest_frontend.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PASS, FAIL = [], []


def need(name: str, data, *paths: str) -> None:
    """断言 data 中存在给定的点路径（支持 a.b 与 a[0].b）。"""
    missing = []
    for p in paths:
        cur = data
        ok = True
        for seg in p.split("."):
            key, _, idx = seg.partition("[")
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            elif isinstance(cur, list) and key == "":
                pass
            else:
                ok = False
                break
            if idx:
                i = int(idx.rstrip("]"))
                if isinstance(cur, list) and len(cur) > i:
                    cur = cur[i]
                else:
                    ok = False
                    break
        if not ok:
            missing.append(p)
    if missing:
        FAIL.append(f"{name} 缺字段: {', '.join(missing)}")
        print(f"  [FAIL] {name}  缺字段 {', '.join(missing)}")
    else:
        PASS.append(name)
        print(f"  [PASS] {name}  ({', '.join(paths[:3])}{'…' if len(paths) > 3 else ''})")


def main() -> int:
    # 与后端自测一致：用 with 触发 lifespan，否则作业引擎与调度器不会启动，
    # 涉及作业/调度器的契约校验会误判为"后端没实现"。
    with TestClient(app) as client:
        return _run(client, started=time.time())


def _run(client, started: float) -> int:
    print("=" * 72)
    print("  SmartHealth 前端契约校验")
    print("=" * 72)

    token = client.post("/api/v1/auth/login",
                        json={"username": "admin", "password": "Admin@2026"}).json()["data"]["access_token"]
    H = {"Authorization": f"Bearer {token}"}

    print("\n[00 总览]")
    d = client.get("/api/v1/ops/dashboard", headers=H).json()["data"]
    need("总览 · dashboard", d, "kpi.slide_count", "kpi.annotated_slide_count", "kpi.model_auroc",
         "kpi.external_auroc", "kpi.agent_reject_rate", "kpi.feature_ready_count",
         "kpi.annotation_count", "kpi.audit_record_count", "kpi.edge_online_count",
         "kpi.milestone_done", "kpi.milestone_total", "readiness.readiness_score",
         "readiness.passed_count", "readiness.total_count", "risk.frontloaded_count", "risk.max_risk_score")

    print("\n[02 数据资产]")
    d = client.get("/api/v1/assets/overview", headers=H).json()["data"]
    need("资产 · overview", d, "asset_count", "slide_count", "patient_count",
         "annotated_slide_count", "positive_slide_count", "total_bytes", "by_site", "by_staining")
    d = client.get("/api/v1/slides?page_size=3", headers=H).json()["data"]
    need("资产 · 切片列表", d, "items[0].id", "items[0].code", "items[0].case_no", "items[0].has_lesion",
         "items[0].split", "items[0].tile_count", "meta.total", "meta.pages")
    sid = d["items"][0]["id"]
    d = client.get(f"/api/v1/slides/{sid}/detail", headers=H).json()["data"]
    need("资产 · 切片详情", d, "annotation_by_layer", "lesion_bbox", "code", "case_no", "mpp")
    code = client.get(f"/api/v1/slides/{sid}/preview?level=2&overlay=true", headers=H).status_code
    print(f"  [{'PASS' if code in (200, 404) else 'FAIL'}] 资产 · 切片预览（无特征时允许 404）  status={code}")
    (PASS if code in (200, 404) else FAIL).append("资产 · 切片预览")

    print("\n[03 标签体系]")
    d = client.get("/api/v1/labels/overview", headers=H).json()["data"]
    need("标签 · overview", d, "coverage.schema_total", "coverage.slide_total", "coverage.by_layer.slide.coverage_rate",
         "coverage.registration_gaps", "coverage.registration_required_count", "coverage.registration_ready",
         "coverage.note", "annotation_total", "qc_total", "qc_pass_rate", "sop.sop_total",
         "sop.approved_count", "sop.arbitration_resolved", "sop.arbitration_open", "sop.note")
    d = client.get("/api/v1/labels/schemas?page_size=3", headers=H).json()["data"]
    need("标签 · 定义列表", d, "items[0].code", "items[0].name", "items[0].layer", "items[0].value_type",
         "items[0].required_for_registration")

    print("\n[04 模型与算力]")
    d = client.get("/api/v1/models/encoders/license-audit", headers=H).json()["data"]
    need("模型 · 许可体检", d, "deployment_env", "allowed", "blocked", "total")
    need("模型 · 许可体检条目", d["allowed"][0], "name", "code", "license_name", "is_self_developed")
    d = client.get("/api/v1/models/versions?page_size=3", headers=H).json()["data"]
    need("模型 · 版本列表", d, "items[0].semver", "items[0].name", "items[0].encoder_code",
         "items[0].metrics_json", "items[0].status", "items[0].is_registration_candidate", "items[0].param_count")

    print("\n[05 推理流水线]")
    d = client.get("/api/v1/inference/overview", headers=H).json()["data"]
    need("流水线 · overview", d, "slide_total", "stage_a_feature_ready", "feature_coverage",
         "inferred_slide_count", "agent_session_count", "stages[0].key", "stages[0].done", "stages[0].total")
    d = client.get("/api/v1/features/overview", headers=H).json()["data"]
    need("流水线 · 特征库", d, "by_encoder[0].encoder_code", "by_encoder[0].slide_count")
    d = client.get("/api/v1/inference/summary", headers=H).json()["data"]
    need("流水线 · 推理汇总", d, "by_decision", "by_confidence", "reject_rate",
         "attention_hit_rate", "attention_region_total", "attention_lesion_overlap")
    d = client.get("/api/v1/inference/predictions?page_size=3", headers=H).json()["data"]
    if d["items"]:
        need("流水线 · 预测列表", d, "items[0].id", "items[0].slide_code", "items[0].probability",
             "items[0].calibrated_probability", "items[0].decision", "items[0].rejected", "items[0].elapsed_ms")
        pid = d["items"][0]["id"]
        det = client.get(f"/api/v1/inference/predictions/{pid}/detail", headers=H).json()["data"]
        need("流水线 · 预测详情", det, "id", "probability", "calibrated_probability", "decision")
        hp = client.get(f"/api/v1/inference/predictions/{pid}/heatmap", headers=H)
        print(f"  [{'PASS' if hp.status_code in (200, 404) else 'FAIL'}] 流水线 · 热力图  status={hp.status_code}")
        (PASS if hp.status_code in (200, 404) else FAIL).append("流水线 · 热力图")

    print("\n[06 智慧医疗 Agent]")
    d = client.get("/api/v1/agents/overview", headers=H).json()["data"]
    need("Agent · overview", d, "session_total", "rejected_count", "reject_rate",
         "pending_review", "decided_review", "avg_probed_regions", "evidence_by_type")
    d = client.get("/api/v1/agents/architecture", headers=H).json()["data"]
    need("Agent · 架构说明", d, "agents[0].key", "agents[0].label", "agents[0].responsibility")
    d = client.get("/api/v1/agents/sessions?page_size=10", headers=H).json()["data"]
    need("Agent · 会话列表", d, "items[0].id", "items[0].code", "items[0].slide_code", "items[0].verdict",
         "items[0].confidence_level", "items[0].probed_region_count", "items[0].evidence_count", "items[0].rejected")
    rich = max(d["items"], key=lambda s: s.get("evidence_count") or 0)
    det = client.get(f"/api/v1/agents/sessions/{rich['id']}/detail", headers=H).json()["data"]
    need("Agent · 会话详情", det, "code", "verdict", "confidence_level", "probed_region_count",
         "evidence_count", "steps[0].agent", "steps[0].action", "steps[0].output_summary",
         "evidence[0].claim", "evidence[0].evidence_type", "evidence[0].score", "evidence[0].agent",
         "diagnoses[0].diagnosis_name", "diagnoses[0].probability", "summary_text")

    print("\n[07 评测基座]")
    d = client.get("/api/v1/eval/overview", headers=H).json()["data"]
    need("评测 · overview", d, "dataset_count", "external_dataset_count", "run_count",
         "datasets_by_kind", "recent_runs")
    d = client.get("/api/v1/eval/runs?page_size=3", headers=H).json()["data"]
    need("评测 · 运行列表", d, "items[0].id", "items[0].code", "items[0].model_version_label",
         "items[0].auroc", "items[0].sensitivity", "items[0].specificity", "items[0].ece", "items[0].threshold")
    rid = d["items"][0]["id"]
    det = client.get(f"/api/v1/eval/runs/{rid}/detail", headers=H).json()["data"]
    need("评测 · 运行详情", det, "code", "auroc", "sensitivity", "specificity", "ece",
         "roc_points", "by_site", "confusion", "metrics")
    if det["roc_points"]:
        need("评测 · ROC 点", det["roc_points"][0], "fpr", "tpr")

    print("\n[08 合规与注册]")
    d = client.get("/api/v1/compliance/overview", headers=H).json()["data"]
    need("合规 · overview", d, "readiness.readiness_score", "readiness.passed_count", "readiness.total_count",
         "readiness.items[0].key", "readiness.blocked_review_labels", "audit_chain.total",
         "audit_chain.algorithm", "audit_chain.broken")
    d = client.get("/api/v1/compliance/explainability", headers=H).json()["data"]
    need("合规 · 可解释性", d, "framework[0].key", "framework[0].label", "framework[0].question")
    d = client.get("/api/v1/compliance/review-answers", headers=H).json()["data"]
    need("合规 · 审评应答", d, "items[0].group_label", "items[0].code", "items[0].question",
         "items[0].answer", "items[0].status")

    print("\n[09 云边协同]")
    d = client.get("/api/v1/edge/overview", headers=H).json()["data"]
    need("云边 · overview", d, "node_total", "online_count", "realtime_capable", "local_slide_total",
         "avg_latency_ms", "min_deploy_minutes", "federated_job_count")
    d = client.get("/api/v1/edge/federated-jobs?page_size=1", headers=H).json()["data"]
    fid = d["items"][0]["id"]
    f = client.get(f"/api/v1/edge/federated-jobs/{fid}/detail", headers=H).json()["data"]
    need("云边 · 联邦详情", f, "code", "global_metric_init", "global_metric_final", "current_round",
         "sample_left_domain_count", "metric_series[0].round", "metric_series[0].metric",
         "rounds[0].round_no", "rounds[0].client_count", "rounds[0].global_metric",
         "rounds[0].upload_kb", "rounds[0].aggregated_at")
    d = client.get("/api/v1/edge/nodes?page_size=3", headers=H).json()["data"]
    need("云边 · 节点列表", d, "items[0].code", "items[0].name", "items[0].node_type",
         "items[0].deployment_mode", "items[0].gpu_count", "items[0].realtime_inference", "items[0].status")

    print("\n[10 注册与路线图]")
    d = client.get("/api/v1/registry/timeline", headers=H).json()["data"]
    need("注册 · 时间轴", d, "total_months", "stages[0].name", "stages[0].start_month", "stages[0].end_month",
         "milestones[0].code", "milestones[0].title", "milestones[0].phase", "milestones[0].target_month",
         "milestones[0].status")
    d = client.get("/api/v1/registry/risks/board", headers=H).json()["data"]
    need("注册 · 风险看板", d, "quadrants", "frontloaded", "frontloaded_count", "max_risk_score")
    need("注册 · 前置风险条目", d["frontloaded"][0], "code", "title", "risk_score", "p0_action")
    d = client.get("/api/v1/registry/risks?page_size=3", headers=H).json()["data"]
    need("注册 · 风险列表", d, "items[0].code", "items[0].title", "items[0].layer", "items[0].likelihood",
         "items[0].severity", "items[0].risk_score", "items[0].is_frontloaded", "items[0].status")

    print("\n[11 运营看板]")
    d = client.get("/api/v1/ops/team-plan", headers=H).json()["data"]
    need("运营 · 团队编制", d, "total_suggested", "total_min", "total_max", "by_cluster", "cluster_labels", "mandatory_in_p0")
    d = client.get("/api/v1/ops/cost-structure", headers=H).json()["data"]
    need("运营 · 成本结构", d, "items[0].category", "items[0].ratio_high", "elasticity_note")
    d = client.get("/api/v1/ops/revenue-plan", headers=H).json()["data"]
    need("运营 · 收入路径", d, "items[0].name", "items[0].phase", "items[0].path_type", "items[0].status", "note")
    d = client.get("/api/v1/ops/decision-board", headers=H).json()["data"]
    need("运营 · 立项决策", d, "items[0].title", "items[0].content", "items[0].status", "note")
    d = client.get("/api/v1/ops/kpi-snapshots?page_size=3", headers=H).json()["data"]
    need("运营 · KPI 快照", d, "items[0].snapshot_date", "items[0].model_auroc", "items[0].external_auroc",
         "items[0].agent_reject_rate", "items[0].milestone_done", "items[0].milestone_total")

    print("\n[13 任务中心 · 数据接入 · 标注工作台]")
    d = client.get("/api/v1/jobs?page_size=5", headers=H).json()["data"]
    need("任务中心 · 作业列表", d, "items", "meta.total", "type_options", "status_options")
    if d["items"]:
        need("任务中心 · 作业行字段", d["items"][0], "id", "code", "type_label", "title", "status",
             "status_label", "progress", "stage_text", "is_terminal", "can_cancel", "can_retry",
             "duration_sec", "attempts", "max_attempts")
        jid = d["items"][0]["id"]
        p2 = client.get(f"/api/v1/jobs/{jid}/progress", headers=H).json()["data"]
        need("任务中心 · 进度轻量查询", p2, "progress", "stage_text", "is_terminal", "can_cancel")
        det = client.get(f"/api/v1/jobs/{jid}", headers=H).json()["data"]
        need("任务中心 · 详情含事件流", det, "events", "payload", "result", "status_label")
        if det["events"]:
            need("任务中心 · 事件字段", det["events"][0], "event", "message", "progress", "at")

    st = client.get("/api/v1/jobs/stats", headers=H).json()["data"]
    need("任务中心 · 统计", st, "by_status", "by_type", "queued", "running", "failed",
         "failure_rate", "recent_failures", "engine", "type_labels", "status_labels")

    wb = client.get("/api/v1/jobs/workbench", headers=H).json()["data"]
    need("待办中心", wb, "items", "total_actionable", "active_jobs", "failed_jobs", "generated_at")
    need("待办条目字段", wb["items"][0], "key", "label", "count", "hint", "route")

    need("数据接入 · 作业类型清单",
         client.get("/api/v1/jobs/types", headers=H).json()["data"], "types", "registered", "engine")

    wbd = client.get(f"/api/v1/labels/workbench/{sid}", headers=H).json()["data"]
    need("标注工作台 · 载入", wbd, "slide", "schemas", "values", "filled_count", "required_missing")
    need("标注工作台 · 标签定义字段", wbd["schemas"][0], "code", "name", "layer", "value_type",
         "allowed_values", "required_for_registration")

    need("数据范围自查", client.get("/api/v1/auth/data-scope", headers=H).json()["data"],
         "scope", "label", "org_code", "site_code", "is_unrestricted", "note")
    need("密码策略（登录页提示用）",
         client.get("/api/v1/auth/password-policy", headers=H).json()["data"],
         "min_length", "rules", "lock_policy", "token_policy")
    need("调度器状态", client.get("/api/v1/system/scheduler", headers=H).json()["data"],
         "running", "job_count", "jobs")

    print("\n[14 数据库工程化（供系统管理页展示）]")
    need("迁移状态", client.get("/api/v1/system/migrations", headers=H).json()["data"],
         "ok", "current_version", "registered", "applied", "pending", "checksum_drift",
         "applied_detail")
    need("部署形态自述", client.get("/api/v1/system/deployment", headers=H).json()["data"],
         "process", "database", "coordination", "multi_process_safety")
    need("部署形态 · 进程信息",
         client.get("/api/v1/system/deployment", headers=H).json()["data"]["process"],
         "pid", "role", "role_label", "worker_id")
    need("就绪探针含迁移与协调层", client.get("/readyz").json()["checks"],
         "database", "storage", "job_engine", "scheduler", "migrations", "coordination")

    print("\n[15 模型权重仓库与读取能力]")
    need("模型权重清单", client.get("/api/v1/models/registry", headers=H).json()["data"],
         "total", "installed", "commercial_ready", "self_developed", "by_stage",
         "by_license", "models", "manifest_path")
    need("清单条目字段", client.get("/api/v1/models/registry", headers=H).json()["data"]["models"][0],
         "code", "name", "license_code", "commercial_usable", "sha256", "installed_path",
         "exists", "absolute_path", "stage", "embedding_dim", "tile_size")
    need("ONNX 诊断", client.get("/api/v1/models/onnx-diagnostics", headers=H).json()["data"],
         "total", "using_real_model", "mismatched_dims", "encoders")
    need("运行时能力自述", client.get("/api/v1/models/runtime-capabilities", headers=H).json()["data"],
         "onnx", "wsi_readers", "image", "database", "note")
    need("切片读取自述", client.get("/api/v1/slides/1/reader", headers=H).json()["data"],
         "source", "backend", "capabilities")

    print("\n[12 系统管理]")
    d = client.get("/api/v1/system/users?page_size=3", headers=H).json()["data"]
    need("系统 · 用户列表", d, "items[0].username", "items[0].real_name", "items[0].roles",
         "items[0].deployment_env", "items[0].is_active", "items[0].last_login_at")

    elapsed = time.time() - started
    print("\n" + "=" * 72)
    print(f"  契约字段校验：通过 {len(PASS)} / 失败 {len(FAIL)}，耗时 {elapsed:.1f}s")
    if FAIL:
        print("\n  失败明细：")
        for f in FAIL:
            print("    - " + f)
    print("=" * 72)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
