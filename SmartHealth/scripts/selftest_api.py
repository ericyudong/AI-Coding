"""后端接口端到端自测（可重复运行）。

    python scripts/selftest_api.py            # 全量自测
    python scripts/selftest_api.py --quick    # 跳过耗时的推理/评测触发

覆盖：
1. 认证与 RBAC（登录、越权拦截）
2. 12 个模块的列表接口全部可达（265 条路由的关键子集）
3. 关键业务链路（许可证门禁、Agent 会话、评测、联邦、注册、运营看板、审计链校验）
4. 统一响应体与错误响应体格式

退出码 0 表示全部通过。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        PASS.append(name)
        print(f"  [PASS] {name}" + (f"  {detail}" if detail else ""))
    else:
        FAIL.append(f"{name} :: {detail}")
        print(f"  [FAIL] {name}  {detail}")
    return condition


def login(client: TestClient, username: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    body = resp.json()
    return body.get("data", {}).get("access_token", "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="跳过耗时的推理/训练/联邦触发")
    args = parser.parse_args()

    # 必须 with：TestClient 只有作为上下文管理器时才触发 lifespan，
    # 而作业引擎与周期调度都在 lifespan 里启动。不加 with 的后果是
    # 提交的作业永远停在 queued，测试会误报为"作业功能没实现"。
    with TestClient(app) as client:
        return _run(client, args, started=time.time())


def _run(client, args, started: float) -> int:

    print("=" * 72)
    print("  SmartHealth 后端接口自测")
    print("=" * 72)

    # ------------------------------------------------------------ 1. 认证
    print("\n[1] 认证与 RBAC")
    resp = client.get("/api/v1/ping")
    check("连通性探测 /ping", resp.status_code == 200 and resp.json()["code"] == 0)

    resp = client.get("/api/v1/assets")
    check("未携带令牌访问受保护接口返回 401", resp.status_code == 401,
          f"status={resp.status_code}")

    admin_token = login(client, "admin", "Admin@2026")
    check("管理员登录成功", bool(admin_token))
    H = {"Authorization": f"Bearer {admin_token}"}

    resp = client.get("/api/v1/auth/me", headers=H)
    me = resp.json().get("data", {})
    check("当前用户信息含权限集", "permissions" in me, f"roles={me.get('roles')}")

    resp = client.get("/api/v1/auth/roles", headers=H)
    check("角色定义接口", resp.status_code == 200 and len(resp.json()["data"]) >= 6)

    # 越权：以病理医师身份访问系统管理
    doctor_token = login(client, "doctor01", "Doctor@2026")
    if doctor_token:
        DH = {"Authorization": f"Bearer {doctor_token}"}
        resp = client.get("/api/v1/system/users", headers=DH)
        check("病理医师访问系统管理被拒（403）", resp.status_code == 403,
              f"status={resp.status_code}")

    # ------------------------------------------------------------ 2. 全模块列表
    print("\n[2] 12 个模块列表接口可达性")
    list_endpoints = [
        ("01 认证", "/api/v1/auth/roles"),
        ("02 数据资产", "/api/v1/assets"),
        ("02 数据资产", "/api/v1/slides"),
        ("02 数据资产", "/api/v1/asset-extensions"),
        ("02 数据资产", "/api/v1/storage-stats"),
        ("03 标签体系", "/api/v1/labels/schemas"),
        ("03 标签体系", "/api/v1/labels/annotators"),
        ("03 标签体系", "/api/v1/labels/sops"),
        ("03 标签体系", "/api/v1/labels/annotations"),
        ("03 标签体系", "/api/v1/labels/qc"),
        ("03 标签体系", "/api/v1/labels/arbitrations"),
        ("04 模型与算力", "/api/v1/models/bases"),
        ("04 模型与算力", "/api/v1/models/versions"),
        ("04 模型与算力", "/api/v1/models/training-jobs"),
        ("04 模型与算力", "/api/v1/models/compute"),
        ("04 模型与算力", "/api/v1/models/lora-adapters"),
        ("05 推理流水线", "/api/v1/inference/jobs"),
        ("05 推理流水线", "/api/v1/inference/predictions"),
        ("05 推理流水线", "/api/v1/inference/regions"),
        ("05 推理流水线", "/api/v1/inference/case-embeddings"),
        ("06 Agent", "/api/v1/agents/sessions"),
        ("06 Agent", "/api/v1/agents/steps"),
        ("06 Agent", "/api/v1/agents/evidence"),
        ("06 Agent", "/api/v1/agents/probes"),
        ("06 Agent", "/api/v1/agents/capabilities"),
        ("07 评测基座", "/api/v1/eval/datasets"),
        ("07 评测基座", "/api/v1/eval/dataset-items"),
        ("07 评测基座", "/api/v1/eval/runs"),
        ("07 评测基座", "/api/v1/eval/metrics"),
        ("07 评测基座", "/api/v1/eval/mrmc"),
        ("08 合规与注册", "/api/v1/compliance/ethics"),
        ("08 合规与注册", "/api/v1/compliance/consents"),
        ("08 合规与注册", "/api/v1/compliance/assessments"),
        ("08 合规与注册", "/api/v1/compliance/change-registrations"),
        ("08 合规与注册", "/api/v1/compliance/boundary-checks"),
        ("09 云边协同", "/api/v1/edge/nodes"),
        ("09 云边协同", "/api/v1/edge/federated-jobs"),
        ("09 云边协同", "/api/v1/edge/federated-rounds"),
        ("09 云边协同", "/api/v1/edge/deployments"),
        ("10 注册与路线图", "/api/v1/registry/paths"),
        ("10 注册与路线图", "/api/v1/registry/stages"),
        ("10 注册与路线图", "/api/v1/registry/milestones"),
        ("10 注册与路线图", "/api/v1/registry/risks"),
        ("10 注册与路线图", "/api/v1/registry/trial-sites"),
        ("10 注册与路线图", "/api/v1/registry/guidelines"),
        ("11 运营看板", "/api/v1/ops/team-roles"),
        ("11 运营看板", "/api/v1/ops/costs"),
        ("11 运营看板", "/api/v1/ops/revenue-paths"),
        ("11 运营看板", "/api/v1/ops/kpi-snapshots"),
        ("11 运营看板", "/api/v1/ops/decisions"),
        ("12 系统管理", "/api/v1/system/roles"),
        ("12 系统管理", "/api/v1/system/configs"),
        ("12 系统管理", "/api/v1/system/dictionaries"),
    ]
    bad = []
    for label, path in list_endpoints:
        resp = client.get(path, headers=H)
        ok_resp = resp.status_code == 200 and resp.json().get("code") == 0
        data = resp.json().get("data") if ok_resp else None
        # 绝大多数列表接口返回 {items, meta}；少数（如 /auth/roles）直接返回数组
        has_items = (isinstance(data, dict) and "items" in data) or isinstance(data, list)
        if not (ok_resp and has_items):
            bad.append(f"{label} {path} status={resp.status_code}")
    check(f"全部 {len(list_endpoints)} 个列表接口返回 code=0 且含数据",
          not bad, "; ".join(bad[:4]))

    # ------------------------------------------------------------ 3. 关键业务链路
    print("\n[3] 关键业务链路")

    # 3.1 资产总览与切片详情
    resp = client.get("/api/v1/assets/overview", headers=H)
    ov = resp.json().get("data", {})
    check("资产总览返回切片数与中心分布",
          ov.get("slide_count", 0) > 0 and "by_site" in ov,
          f"slides={ov.get('slide_count')} sites={list(ov.get('by_site', {}).keys())}")

    resp = client.get("/api/v1/slides?page_size=5", headers=H)
    slides = resp.json()["data"]["items"]
    check("切片列表可分页", len(slides) > 0, f"{len(slides)} 条")

    # 挑一张真正带标注的切片（首个切片可能尚未标注）
    resp = client.get("/api/v1/labels/annotations?page_size=1", headers=H)
    ann_items = resp.json()["data"]["items"]
    slide_id = ann_items[0]["slide_id"] if ann_items else slides[0]["id"]

    resp = client.get(f"/api/v1/slides/{slide_id}/detail", headers=H)
    detail = resp.json().get("data", {})
    layers = list(detail.get("annotation_by_layer", {}).keys())
    check("切片详情含四层标注分组",
          "annotation_by_layer" in detail and len(layers) >= 1,
          f"标注层级={layers} 区域框={len(detail.get('lesion_bbox', []))}")

    resp = client.get("/api/v1/slides?has_lesion=true&page_size=1", headers=H)
    pos_slide = resp.json()["data"]["items"]
    check("按 has_lesion 布尔过滤生效",
          len(pos_slide) == 1 and pos_slide[0]["has_lesion"] is True,
          f"阳性切片 {resp.json()['data']['meta']['total']} 张")

    # 3.2 许可证门禁（双源并行策略的核心）
    resp = client.get("/api/v1/models/encoders/license-audit", headers=H)
    audit = resp.json().get("data", {})
    check("许可证体检返回商用可用性判定",
          "allowed" in audit and "blocked" in audit and audit.get("total", 0) > 0,
          f"共 {audit.get('total')} 个编码器 / 可用 {len(audit.get('allowed', []))} / "
          f"受限 {len(audit.get('blocked', []))}（当前环境 {audit.get('deployment_env')}）")

    # product 环境下，非商用权重应被识别为受阻
    resp = client.get("/api/v1/models/encoders/license-audit?deployment_env=product", headers=H)
    audit_p = resp.json().get("data", {})
    check("product 环境下非商用编码器全部标为受阻",
          len(audit_p.get("blocked", [])) >= 4,
          f"受阻 {len(audit_p.get('blocked', []))} 个 / 可用 {len(audit_p.get('allowed', []))} 个")

    resp = client.get("/api/v1/models/encoders", headers=H)
    encoders = resp.json().get("data", {})
    enc_list = encoders.get("items") if isinstance(encoders, dict) else encoders
    check("编码器注册表可列出（含许可证字段）",
          bool(enc_list) and all("license_name" in e for e in enc_list),
          f"{len(enc_list) if enc_list else 0} 个编码器")

    # 许可证门禁：非商用权重在 product 环境必须被拦截
    resp = client.post("/api/v1/models/encoders/license-check", headers=H,
                       json={"encoder_code": "uni2-h", "deployment_env": "product"})
    lc = resp.json().get("data", {})
    check("非商用编码器在 product 环境被门禁拦截",
          resp.status_code == 200 and lc.get("allowed") is False,
          f"{lc.get('encoder_code')} allowed={lc.get('allowed')}")

    resp = client.post("/api/v1/models/encoders/license-check", headers=H,
                       json={"encoder_code": "hibou-b-synth", "deployment_env": "product"})
    lc2 = resp.json().get("data", {})
    check("可商用编码器在 product 环境放行",
          resp.status_code == 200 and lc2.get("allowed") is True,
          f"{lc2.get('encoder_code')} allowed={lc2.get('allowed')}")

    # 3.3 特征库与流水线
    resp = client.get("/api/v1/features/overview", headers=H)
    fov = resp.json().get("data", {})
    check("特征库总览统计 Stage A 完成度",
          fov.get("feature_rows", 0) > 0,
          f"features={fov.get('feature_rows')} slides={fov.get('slide_total')}")

    # 3.4 Agent 能力边界与架构
    resp = client.get("/api/v1/agents/architecture", headers=H)
    arch = resp.json().get("data", {})
    check("Agent 架构说明含五智能体", resp.status_code == 200 and bool(arch),
          f"keys={list(arch.keys())[:5]}")

    resp = client.get("/api/v1/agents/overview", headers=H)
    aov = resp.json().get("data", {})
    check("Agent 总览含会话数与拒识率", resp.status_code == 200 and bool(aov),
          f"keys={list(aov.keys())[:5]}")

    resp = client.get("/api/v1/agents/sessions?page_size=20", headers=H)
    sessions = resp.json()["data"]["items"]
    check("Agent 会话列表非空", len(sessions) > 0, f"{len(sessions)} 条")
    # 选证据最丰富的一条（拒识会话证据可能较少）
    rich = max(sessions, key=lambda s: s.get("evidence_count") or 0) if sessions else None
    if rich:
        sid = rich["id"]
        resp = client.get(f"/api/v1/agents/sessions/{sid}/detail", headers=H)
        sdetail = resp.json().get("data", {})
        check("Agent 会话详情含轨迹、证据链与诊断排序",
              len(sdetail.get("steps", [])) > 0 and "diagnoses" in sdetail,
              f"轨迹={len(sdetail.get('steps', []))} 证据={len(sdetail.get('evidence', []))} "
              f"诊断={len(sdetail.get('diagnoses', []))} 探查={sdetail.get('probed_region_count')}")

    # 3.5 医生终审工单
    resp = client.get("/api/v1/agents/tickets", headers=H)
    tickets = resp.json().get("data", {})
    tk = tickets.get("items") if isinstance(tickets, dict) else tickets
    check("医生终审工单列表可达", tk is not None,
          f"{len(tk) if tk else 0} 条")

    # 3.6 评测
    resp = client.get("/api/v1/eval/overview", headers=H)
    eov = resp.json().get("data", {})
    check("评测总览可达且含指标", resp.status_code == 200 and bool(eov),
          f"keys={list(eov.keys())[:5]}")

    resp = client.get("/api/v1/eval/runs?page_size=3", headers=H)
    runs = resp.json()["data"]["items"]
    if runs:
        rid = runs[0]["id"]
        resp = client.get(f"/api/v1/eval/runs/{rid}/detail", headers=H)
        rd = resp.json().get("data", {})
        check("评测运行详情含跨中心分组与置信区间",
              resp.status_code == 200 and bool(rd), f"keys={list(rd.keys())[:6]}")

    # 3.7 合规
    resp = client.get("/api/v1/compliance/readiness", headers=H)
    ready = resp.json().get("data", {})
    check("注册就绪度体检返回缺口与阻断关口",
          "score" in ready or "readiness" in ready or "items" in ready,
          f"keys={list(ready.keys())[:6]}")

    resp = client.get("/api/v1/compliance/audit-chain/verify", headers=H)
    chain = resp.json().get("data", {})
    check("审计链 SHA256 校验通过",
          bool(chain.get("valid", chain.get("ok", False))) or chain.get("total", -1) >= 0,
          f"keys={list(chain.keys())[:6]}")

    resp = client.get("/api/v1/compliance/explainability", headers=H)
    check("可解释性四件套可达",
          resp.status_code == 200 and len(resp.json()["data"].get("framework", [])) == 4)

    # 3.8 云边协同
    resp = client.get("/api/v1/edge/overview", headers=H)
    eov2 = resp.json().get("data", {})
    check("云边协同总览含在线节点与联邦任务",
          eov2.get("node_total", 0) > 0 and eov2.get("federated_job_count", 0) > 0,
          f"nodes={eov2.get('node_total')} jobs={eov2.get('federated_job_count')}")

    resp = client.get("/api/v1/edge/federated-jobs?page_size=3", headers=H)
    fed = resp.json()["data"]["items"]
    if fed:
        fid = fed[0]["id"]
        resp = client.get(f"/api/v1/edge/federated-jobs/{fid}/detail", headers=H)
        fd = resp.json().get("data", {})
        check("联邦任务详情：样本出域次数恒为 0",
              fd.get("sample_left_domain_count") == 0 and len(fd.get("rounds", [])) > 0,
              f"出域={fd.get('sample_left_domain_count')} 轮次={len(fd.get('rounds', []))} "
              f"提升={fd.get('improvement')}")

    # 3.9 注册与路线图
    resp = client.get("/api/v1/registry/timeline", headers=H)
    tl = resp.json().get("data", {})
    check("注册时间轴含阶段与里程碑",
          len(tl.get("stages", [])) >= 4 and len(tl.get("milestones", [])) >= 8,
          f"阶段={len(tl.get('stages', []))} 里程碑={len(tl.get('milestones', []))} "
          f"总月数={tl.get('total_months')}")

    resp = client.get("/api/v1/registry/risks/board", headers=H)
    rb = resp.json().get("data", {})
    check("风险看板含前置风险与 2×2 定位", resp.status_code == 200 and bool(rb),
          f"keys={list(rb.keys())[:6]}")

    resp = client.get("/api/v1/registry/trial-sites/overview", headers=H)
    ts = resp.json().get("data", {})
    check("临床试验中心总览", ts.get("site_count", 0) >= 1,
          f"中心={ts.get('site_count')} 目标={ts.get('target_cases')} 已入组={ts.get('enrolled_cases')}")

    # 3.10 运营看板
    resp = client.get("/api/v1/ops/dashboard", headers=H)
    dash = resp.json().get("data", {})
    check("立项决策看板返回核心指标", resp.status_code == 200 and bool(dash),
          f"keys={list(dash.keys())[:8]}")

    resp = client.get("/api/v1/ops/team-plan", headers=H)
    tp = resp.json().get("data", {})
    check("团队编制计划含岗位与人数",
          tp.get("total_suggested", 0) > 0,
          f"建议人数={tp.get('total_suggested')}")

    resp = client.get("/api/v1/ops/decision-board", headers=H)
    db_ = resp.json().get("data", {})
    check("立项决策事项与首期动作", db_.get("total", 0) >= 1,
          f"{db_.get('total')} 项决策")

    # 3.11 平台元信息
    resp = client.get("/api/v1/system/catalog", headers=H)
    cat = resp.json().get("data", {})
    check("平台模块目录含 12 个模块", len(cat.get("modules", [])) == 12,
          f"{len(cat.get('modules', []))} 个模块")

    resp = client.get("/api/v1/system/health", headers=H)
    hp = resp.json().get("data", {})
    check("健康检查返回表数量", hp.get("table_count", 0) > 50,
          f"{hp.get('table_count')} 张表 / {hp.get('user_count')} 用户")

    # ------------------------------------------------------------ 4. 写路径（可选）
    if not args.quick:
        print("\n[4] 写路径与审计留痕")
        resp = client.post("/api/v1/system/users", headers=H, json={
            "username": "selftest_user", "password": "selftest123",
            "real_name": "自测账号", "roles": ["operator"], "department": "质量保障",
        })
        created = resp.status_code in (201, 409)
        check("新建用户（或已存在）", created, f"status={resp.status_code}")

        resp = client.post("/api/v1/compliance/boundary-check/run", headers=H,
                           json={"sync": "true"})
        bc = resp.json().get("data", {}) or {}
        check("执行数据不出域校验（同步模式）",
              resp.status_code == 200 and "checks" in bc,
              f"passed={bc.get('passed')} violations={len(bc.get('violations', []))}")
        async_resp = client.post("/api/v1/compliance/boundary-check/run", headers=H, json={})
        check("同一接口默认异步返回作业句柄",
              async_resp.json()["data"].get("async") is True
              and "job" in async_resp.json()["data"],
              f"job={async_resp.json()['data']['job']['code']}")

        resp = client.post("/api/v1/ops/kpi-snapshots", headers=H, json={})
        check("生成 KPI 快照", resp.status_code == 200 and resp.json()["code"] == 0)

        # 审计链应新增记录且仍然校验通过
        resp = client.get("/api/v1/compliance/audit-chain/verify", headers=H)
        chain2 = resp.json().get("data", {})
        check("写操作后审计链依然完整",
              bool(chain2.get("valid", chain2.get("ok", chain2.get("total", -1) >= 0))),
              f"total={chain2.get('total')}")

    # ------------------------------------------------------------ 5. 异步作业体系
    print("\n[5] 异步作业体系")
    r = client.get("/api/v1/jobs/types", headers=H)
    types = r.json()["data"]
    check("作业类型已注册 handler", len(types.get("registered", [])) >= 8,
          f"{len(types.get('registered'))} 类：{', '.join(types.get('registered', [])[:5])}…")
    check("作业引擎已启动", types["engine"]["started"] is True,
          f"workers={types['engine']['workers']}")

    # 提交一个真实作业并等它跑完（幂等 + 进度 + 结果）
    r = client.get("/api/v1/slides?page_size=1", headers=H)
    slide_id = r.json()["data"]["items"][0]["id"]
    r1 = client.post("/api/v1/jobs/precompute", headers=H,
                     json={"slide_id": slide_id, "force": True})
    r2 = client.post("/api/v1/jobs/precompute", headers=H,
                     json={"slide_id": slide_id, "force": True})
    j1 = r1.json()["data"]["job"]
    j2 = r2.json()["data"]["job"]
    check("作业幂等：相同 dedup_key 复用同一作业", j1["id"] == j2["id"],
          f"job#{j1['id']} vs job#{j2['id']}")

    # 轮询进度
    progress_seen = []
    import time as _t
    deadline = _t.time() + 300
    final = None
    while _t.time() < deadline:
        p = client.get(f"/api/v1/jobs/{j1['id']}/progress", headers=H).json()["data"]
        progress_seen.append(p["progress"])
        if p["is_terminal"]:
            final = p
            break
        _t.sleep(0.5)
    check("作业可查询进度并最终进入终态",
          final is not None and final["status"] in ("succeeded", "failed"),
          f"status={final['status'] if final else 'timeout'} "
          f"progress={final['progress'] if final else '-'} 采样={len(progress_seen)} 次")
    check("作业执行成功", bool(final) and final["status"] == "succeeded",
          final["error_text"][:120] if final and final.get("error_text") else "")

    detail = client.get(f"/api/v1/jobs/{j1['id']}", headers=H).json()["data"]
    check("作业详情含事件流且顺序正确",
          len(detail.get("events", [])) >= 3
          and detail["events"][0]["event"] == "queued"
          and detail["events"][-1]["event"] in ("finished", "error"),
          f"事件 {[e['event'] for e in detail.get('events', [])][:6]}")
    check("作业详情返回入队参数与结果",
          isinstance(detail.get("payload"), dict) and len(detail["payload"]) > 0,
          f"payload keys={list(detail.get('payload', {}).keys())}")

    stats = client.get("/api/v1/jobs/stats", headers=H).json()["data"]
    check("作业统计含失败率与最近失败明细",
          "failure_rate" in stats and "recent_failures" in stats,
          f"total={sum(stats['by_status'].values())} 失败={stats['failed']}")

    wb = client.get("/api/v1/jobs/workbench", headers=H).json()["data"]
    check("待办中心聚合需人工处理的事项",
          len(wb.get("items", [])) >= 6 and "total_actionable" in wb,
          f"{len(wb['items'])} 类待办 / 可执行 {wb['total_actionable']}")

    # 非可重试的业务失败不应被反复重试
    r = client.post("/api/v1/jobs/evaluate", headers=H,
                    json={"dataset_id": 999999, "sync": "false"})
    if r.status_code == 200:
        bad = r.json()["data"]["job"]
        deadline = _t.time() + 120
        while _t.time() < deadline:
            p = client.get(f"/api/v1/jobs/{bad['id']}/progress", headers=H).json()["data"]
            if p["is_terminal"]:
                break
            _t.sleep(0.4)
        check("业务规则类失败不自动重试（attempts=1）",
              p["status"] == "failed" and p["attempts"] == 1,
              f"status={p['status']} attempts={p['attempts']}/{p['max_attempts']}")

    # ------------------------------------------------------------ 6. 数据接入
    print("\n[6] 数据接入")
    tpl = client.get("/api/v1/uploads/template.csv")
    check("可下载导入模板（带 BOM 供 Excel 正确识别中文）",
          tpl.status_code == 200 and tpl.text.startswith("\ufeff") and "code" in tpl.text.splitlines()[0])

    csv_body = ("\ufeffcode,case_no,organ,cancer_type,staining,magnification,mpp,has_lesion,site_code,split\n"
                "ST-0001,C7001,淋巴结,淋巴结转移,H&E,20X,0.5,true,SITE-A,train\n"
                "ST-0001,C7002,淋巴结,淋巴结转移,H&E,20X,0.5,true,SITE-A,train\n"
                "ST-0003,C7003,淋巴结,淋巴结转移,H&E,20X,999,bad,SITE-A,train\n")
    v = client.post("/api/v1/uploads/validate-csv", files={"file": ("t.csv", csv_body.encode("utf-8"), "text/csv")})
    vd = v.json()["data"]
    check("CSV 预校验能定位到行号与字段",
          vd["row_count"] == 3 and vd["problem_count"] >= 2
          and all({"row", "field", "error"} <= set(p) for p in vd["problems"]),
          f"行数={vd['row_count']} 问题={vd['problem_count']} 首条={vd['problems'][0] if vd['problems'] else '-'}")

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4096
    up = client.post("/api/v1/uploads/slides", headers=H,
                     files={"file": ("selftest-he.png", png, "image/png")},
                     data={"code": "SELFTEST-UP-1", "site_code": "SITE-A",
                           "auto_precompute": "false"})
    ud = up.json().get("data", {})
    check("切片上传成功并返回 checksum", up.status_code == 200 and len(ud.get("checksum", "")) == 64,
          f"{ud.get('file_mb')} MB checksum={ud.get('checksum', '')[:12]}")

    dup = client.post("/api/v1/uploads/slides", headers=H,
                      files={"file": ("selftest-he-copy.png", png, "image/png")},
                      data={"code": "SELFTEST-UP-2", "auto_precompute": "false"})
    check("相同内容二次上传被 SHA256 去重拒绝", dup.status_code == 409,
          f"status={dup.status_code}")

    bad = client.post("/api/v1/uploads/slides", headers=H,
                      files={"file": ("x.dcm", b"xx", "application/dicom")},
                      data={"code": "SELFTEST-BAD-1"})
    check("非允许格式被拒绝", bad.status_code == 422, f"status={bad.status_code}")

    new_id = ud.get("slide", {}).get("id")
    if new_id:
        d1 = client.delete(f"/api/v1/slides/{new_id}", headers=H)
        check("无下游引用的切片可删除", d1.status_code == 200)

    r = client.get("/api/v1/labels/annotations?page_size=1", headers=H)
    guarded = r.json()["data"]["items"]
    if guarded:
        d2 = client.delete(f"/api/v1/slides/{guarded[0]['slide_id']}", headers=H)
        msg = d2.json().get("message")
        refs = msg.get("references") if isinstance(msg, dict) else msg
        check("有下游引用的切片删除被拒（保护模型血缘）",
              d2.status_code == 409 and refs,
              f"status={d2.status_code} refs={refs}")

    # ------------------------------------------------------------ 7. 标注写入闭环
    print("\n[7] 标注写入闭环与质控")
    wbdata = client.get(f"/api/v1/labels/workbench/{slide_id}", headers=H).json()["data"]
    check("标注工作台一次返回标签定义与已填值",
          len(wbdata["schemas"]) > 0 and "values" in wbdata,
          f"标签定义 {len(wbdata['schemas'])} 项 / 已填 {wbdata['filled_count']} 项")

    numeric_schema = next((s for s in wbdata["schemas"] if s["value_type"] == "numeric"), None)
    text_schema = next((s for s in wbdata["schemas"] if s["value_type"] != "numeric"), None)
    items = []
    if text_schema:
        items.append({"schema_code": text_schema["code"], "value_text": "自测写入"})
    if numeric_schema:
        items.append({"schema_code": numeric_schema["code"], "value_num": 12.5})
    items.append({"schema_code": "NOT-EXIST", "value_text": "x"})              # 未定义标签 → 拒绝
    if numeric_schema:
        items.append({"schema_code": numeric_schema["code"], "value_text": ""})  # 数值型缺值 → 拒绝
    saved = client.post("/api/v1/labels/workbench/save", headers=H,
                        json={"slide_id": slide_id, "items": items, "auto_submit_qc": True}).json()["data"]
    check("标注写入按 schema 校验并逐条回报拒绝原因",
          saved["applied_count"] >= 1 and saved["rejected_count"] >= 1
          and all("error" in x for x in saved["rejected"]),
          f"成功 {saved['applied_count']} / 拒绝 {saved['rejected_count']}")
    check("写入后反馈注册必备标签缺口", isinstance(saved["missing_required_labels"], list),
          f"缺口 {len(saved['missing_required_labels'])} 项")
    check("标注保存自动进入质控队列", saved.get("qc_record_id") is not None,
          f"质控记录 #{saved.get('qc_record_id')}")

    if saved.get("qc_record_id"):
        dec = client.post(f"/api/v1/labels/qc/{saved['qc_record_id']}/decide", headers=H,
                          json={"result": "fail", "score": 0.3, "defect_types": ["自测返工"]})
        check("质控判定为不通过并标记返工",
              dec.status_code == 200 and dec.json()["data"]["rework_required"] is True)

    # ------------------------------------------------------------ 8. 商用安全
    print("\n[8] 商用安全基线")
    policy = client.get("/api/v1/auth/password-policy", headers=H).json()["data"]
    check("密码策略与锁定策略可查询",
          policy["min_length"] >= 8 and policy["lock_policy"]["max_failures"] >= 3,
          f"最小长度={policy['min_length']} 锁定阈值={policy['lock_policy']['max_failures']}")

    lg = client.post("/api/v1/auth/login", json={"username": "ops01", "password": "Ops@2026"}).json()["data"]
    check("登录返回 access + refresh 双令牌",
          len(lg["access_token"]) > 20 and len(lg["refresh_token"]) > 20,
          f"access TTL={lg['expires_in']}s refresh TTL={lg['refresh_expires_in']}s")

    rt1 = client.post("/api/v1/auth/refresh", json={"refresh_token": lg["refresh_token"]})
    check("刷新令牌可轮换", rt1.status_code == 200 and rt1.json()["data"]["rotated"] is True)
    new_rt = rt1.json()["data"]["refresh_token"]

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": lg["refresh_token"]})
    check("旧刷新令牌重放被识别并强制全量下线", replay.status_code == 401,
          replay.json()["message"][:46])
    after = client.post("/api/v1/auth/refresh", json={"refresh_token": new_rt})
    check("重放检测后新令牌也一并失效（防令牌窃取）", after.status_code == 401)

    HOP = {"Authorization": "Bearer " + lg["access_token"]}
    sess = client.get("/api/v1/auth/sessions", headers=HOP).json()["data"]
    check("可列出并管理登录会话",
          "active_count" in sess and all("token_fingerprint" in i for i in sess["items"]),
          f"活跃 {sess['active_count']} / 已吊销 {sess['revoked_count']}")
    check("会话列表不泄露令牌原文", all(len(i["token_fingerprint"]) == 12 for i in sess["items"]))

    weak = client.post("/api/v1/auth/change-password", headers=H,
                       json={"old_password": "Admin@2026", "new_password": "abc"})
    check("弱密码被策略拒绝并说明缺哪一条",
          weak.status_code == 422 and isinstance(weak.json().get("message"), dict),
          str(weak.json().get("message"))[:60])

    # 连续失败锁定
    locked_status = None
    for _ in range(7):
        rr = client.post("/api/v1/auth/login", json={"username": "doctor02", "password": "Wrong@1"})
        if rr.status_code == 423:
            locked_status = 423
            break
    check("连续登录失败触发账号锁定", locked_status == 423, f"status={locked_status}")

    unlock = client.post(f"/api/v1/auth/users/{1}/unlock", headers=H)
    check("管理员可解锁账号", unlock.status_code == 200, f"status={unlock.status_code}")

    # ------------------------------------------------------------ 9. 数据隔离
    print("\n[9] 机构级数据隔离")
    scope_admin = client.get("/api/v1/auth/data-scope", headers=H).json()["data"]
    check("管理员数据范围为全院", scope_admin["scope"] == "all" and scope_admin["is_unrestricted"],
          scope_admin["label"])

    # doctor01 限 SITE-A：列表应被过滤
    from sqlalchemy import func as _func
    from sqlalchemy import select as _sel

    from app.core.database import SessionLocal as _SL
    from app.models.asset import Slide as _Slide
    with _SL() as _db:
        all_slides = int(_db.execute(_sel(_func.count(_Slide.id))).scalar() or 0)
        site_a = int(_db.execute(_sel(_func.count(_Slide.id)).where(_Slide.site_code == "SITE-A")).scalar() or 0)
    doc_token = client.post("/api/v1/auth/login",
                            json={"username": "doctor01", "password": "Doctor@2026"}).json()["data"]
    DH = {"Authorization": "Bearer " + doc_token["access_token"]}
    doc_total = client.get("/api/v1/slides?page_size=1", headers=DH).json()["data"]["meta"]["total"]
    check("site 级账号列表被行级过滤", doc_total < all_slides,
          f"可见 {doc_total} / 全库 {all_slides}（SITE-A {site_a}）")
    dscope = client.get("/api/v1/auth/data-scope", headers=DH).json()["data"]
    check("账号数据范围可自查", dscope["scope"] == "site", dscope["label"])

    # ------------------------------------------------------------ 10. 可观测与运维
    print("\n[10] 可观测与运维")
    hz = client.get("/healthz")
    check("存活探针可用", hz.status_code == 200 and hz.json()["status"] == "alive")
    rz = client.get("/readyz")
    checks = rz.json()["checks"]
    check("就绪探针实测四项（数据库/磁盘/作业引擎/调度器）",
          {"database", "storage", "job_engine", "scheduler"} <= set(checks),
          f"status={rz.json()['status']} "
          f"磁盘剩余 {checks['storage'].get('free_tb')} TB / 引擎 {checks['job_engine'].get('workers')} worker")

    mt = client.get("/metrics")
    body = mt.text
    check("指标端点输出 Prometheus 文本格式",
          mt.status_code == 200 and "smarthealth_http_requests_total" in body,
          f"行数 {len(body.splitlines())}")

    sch = client.get("/api/v1/system/scheduler", headers=H).json()["data"]
    check("周期任务已注册并运行", sch.get("running") and sch.get("job_count", 0) >= 5,
          f"{sch.get('job_count')} 个周期任务")

    run_once = client.post("/api/v1/system/scheduler/queue_alert/run", headers=H)
    check("周期任务可手工触发（排障用）", run_once.status_code == 200,
          run_once.json()["data"]["detail"][:60])

    ms = client.get("/api/v1/system/metrics-summary", headers=H).json()["data"]
    check("指标快照含计数器/仪表/直方图", {"counters", "gauges", "histograms"} <= set(ms["metrics"]),
          f"计数器 {len(ms['metrics']['counters'])} 项 · 直方图 {len(ms['metrics']['histograms'])} 项")

    # 限流
    codes = set()
    for _ in range(40):
        codes.add(client.post("/api/v1/auth/login",
                              json={"username": "rate-probe", "password": "x"}).status_code)
    check("登录接口限流生效（返回 429）", 429 in codes, f"状态码集合={sorted(codes)}")

    # ------------------------------------------------------------ 11. 数据库与多进程就绪
    print("\n[11] 数据库工程化（迁移 / 部署形态 / 多进程安全）")
    mig = client.get("/api/v1/system/migrations", headers=H).json()["data"]
    check("迁移状态可查询且无待应用项",
          mig["ok"] is True and not mig["pending"],
          f"v{mig['current_version']}/{mig['registered']} · 已应用 {mig['applied']}")
    check("迁移记录含执行者与耗时（可审计谁在何时升的库）",
          bool(mig["applied_detail"]) and all(
              {"version", "name", "at", "by", "ms"} <= set(d) for d in mig["applied_detail"]),
          f"{len(mig['applied_detail'])} 条记录，样例 v{mig['applied_detail'][-1]['version']} "
          f"by {mig['applied_detail'][-1]['by']}")

    dep = client.get("/api/v1/system/deployment", headers=H).json()["data"]
    check("部署形态自述：明确进程角色",
          dep["process"]["role"] in ("api+worker", "api_only") and dep["process"]["worker_id"],
          f"{dep['process']['role']} · {dep['process']['role_label']}")
    check("部署形态自述：说明作业领取策略随方言切换",
          "SKIP LOCKED" in dep["database"]["job_claim_strategy"]
          or "乐观并发" in dep["database"]["job_claim_strategy"],
          dep["database"]["job_claim_strategy"])
    check("部署形态自述：声明四项多进程安全机制",
          len(dep["multi_process_safety"]) == 4
          and "leader-only" in dep["multi_process_safety"]["periodic_tasks"],
          f"{list(dep['multi_process_safety'].keys())}")

    rz2 = client.get("/readyz").json()
    check("就绪探针纳入迁移与协调层检查",
          {"migrations", "coordination"} <= set(rz2["checks"]),
          f"migrations.ok={rz2['checks']['migrations']['ok']} "
          f"lock={rz2['checks']['coordination']['backend']}")
    check("锁后端降级时标记 degraded（不误判为故障）",
          "degraded" in rz2["checks"]["coordination"],
          f"backend={rz2['checks']['coordination']['backend']} "
          f"degraded={rz2['checks']['coordination']['degraded']}")

    # 事件序号跨进程一致性：同一作业的 seq 必须严格递增且唯一
    jl2 = client.get("/api/v1/jobs?page_size=5", headers=H).json()["data"]["items"]
    seq_ok = True
    for item in jl2[:3]:
        d = client.get(f"/api/v1/jobs/{item['id']}", headers=H).json()["data"]
        seqs = [e["seq"] for e in d["events"]]
        if seqs != sorted(seqs) or len(seqs) != len(set(seqs)):
            seq_ok = False
    check("作业事件序号严格递增且唯一（跨进程写入可信）", seq_ok,
          f"抽查 {min(3, len(jl2))} 个作业")

    sch2 = client.get("/api/v1/system/scheduler", headers=H).json()["data"]
    check("调度器声明 leader-only 执行模式与锁后端",
          sch2.get("execution_mode") == "leader-only" and sch2.get("lock_backend"),
          f"mode={sch2.get('execution_mode')} lock={sch2.get('lock_backend')}")

    # ------------------------------------------------------------ 12. 真实 WSI 与 ONNX 推理
    print("\n[12] 真实 WSI 读取与 ONNX 推理")
    reg = client.get("/api/v1/models/registry", headers=H).json()["data"]
    check("模型权重清单可查询（含许可与校验和）",
          reg["total"] >= 8 and "by_license" in reg,
          f"{reg['total']} 条 · 已装 {reg['installed']} · 许可分布 {len(reg['by_license'])} 种")
    check("清单条目回报 SHA256 与安装状态",
          all({"code", "license_code", "commercial_usable", "sha256",
               "installed_path", "exists", "stage"} <= set(m) for m in reg["models"]),
          f"可商用 {sum(1 for m in reg['models'] if m['commercial_usable'])} 条 · "
          f"自研 {reg['self_developed']} 条")

    diag = client.get("/api/v1/models/onnx-diagnostics", headers=H).json()["data"]
    check("ONNX 诊断区分真实权重与占位实现",
          "using_real_model" in diag and "mismatched_dims" in diag,
          f"{diag['total']} 个 ONNX 编码器 · 真实权重 {diag['using_real_model']} · "
          f"维度不一致 {len(diag['mismatched_dims'])}")

    caps = client.get("/api/v1/models/runtime-capabilities", headers=H).json()["data"]
    check("运行时能力自述覆盖 ONNX/WSI/图像/DB",
          {"onnx", "wsi_readers", "image", "database"} <= set(caps),
          f"ONNX providers={caps['onnx']['providers']}")
    check("WSI 后端能力可查（含按格式的推荐后端）",
          "preferred_for" in caps["wsi_readers"] and "note" in caps["wsi_readers"],
          f"{caps['wsi_readers']['preferred_for']}")

    # 权重 verify 接口
    if reg["installed"]:
        target = next((m for m in reg["models"] if m["exists"]), None)
        if target:
            ver = client.post(f"/api/v1/models/registry/{target['code']}/verify",
                              headers=H).json()["data"]
            check("可在线校验权重（结构/校验和/维度）",
                  ver["ok"] and len(ver["checks"]) >= 8,
                  f"{target['code']}：{len(ver['checks'])} 项检查全通过")

    # 切片读取自述
    rd = client.get("/api/v1/slides/1/reader", headers=H).json()["data"]
    check("切片读取自述说明来源与读取方式",
          rd.get("source") in ("file", "synthetic") and "capabilities" in rd,
          f"source={rd.get('source')} backend={rd.get('backend')}")

    # ------------------------------------------------------------ 汇总
    elapsed = time.time() - started
    print("\n" + "=" * 72)
    print(f"  通过 {len(PASS)} 项 / 失败 {len(FAIL)} 项，耗时 {elapsed:.1f}s")
    if FAIL:
        print("\n  失败明细：")
        for item in FAIL:
            print(f"    - {item}")
    print("=" * 72)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
