#!/usr/bin/env python3
"""生成 LiteLLM 中文用户手册（Word .docx）。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


OUT = Path(__file__).resolve().parent / "LiteLLM中文用户手册.docx"


def set_run_font(run, size=11, bold=False, color=None):
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = "微软雅黑"
    r = run._element.rPr.rFonts
    r.set(qn("w:eastAsia"), "微软雅黑")
    if color:
        run.font.color.rgb = RGBColor(*color)


def add_title(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    set_run_font(run, size=22, bold=True, color=(15, 76, 129))


def add_subtitle(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    set_run_font(run, size=12, color=(90, 90, 90))


def h1(doc, text):
    p = doc.add_heading(text, level=1)
    for run in p.runs:
        set_run_font(run, size=16, bold=True, color=(15, 76, 129))


def h2(doc, text):
    p = doc.add_heading(text, level=2)
    for run in p.runs:
        set_run_font(run, size=13, bold=True, color=(30, 100, 160))


def h3(doc, text):
    p = doc.add_heading(text, level=3)
    for run in p.runs:
        set_run_font(run, size=12, bold=True)


def para(doc, text, bold=False):
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run, size=11, bold=bold)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.35
    return p


def bullets(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        run = p.add_run(item)
        set_run_font(run, size=11)
        p.paragraph_format.space_after = Pt(2)


def numbered(doc, items):
    for item in items:
        p = doc.add_paragraph(style="List Number")
        run = p.add_run(item)
        set_run_font(run, size=11)
        p.paragraph_format.space_after = Pt(2)


def code_block(doc, text):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = "Menlo"
    run.font.size = Pt(9)
    r = run._element.rPr.rFonts
    r.set(qn("w:eastAsia"), "微软雅黑")
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.left_indent = Pt(12)


def table(doc, headers, rows):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        set_run_font(run, size=10, bold=True)
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            cell = t.rows[r_idx + 1].cells[c_idx]
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(val))
            set_run_font(run, size=10)
    doc.add_paragraph()


def build():
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Pt(72)
    section.bottom_margin = Pt(72)
    section.left_margin = Pt(72)
    section.right_margin = Pt(72)

    # Cover
    add_title(doc, "LiteLLM 中文用户手册")
    add_subtitle(doc, "统一 LLM 推理网关 · 管理控制台与 API 使用指南")
    add_subtitle(doc, f"适用于本仓库 AIGateway（LiteLLM Proxy）本地部署")
    add_subtitle(doc, f"文档版本 1.0 · 更新日期 {date.today().isoformat()}")
    para(doc, "")
    para(
        doc,
        "本手册面向平台管理员与业务接入方，按功能模块说明 LiteLLM Proxy Admin UI "
        "与 OpenAI 兼容 API 的使用方法，并结合本机 AIGateway 配置（路由、六层护栏、"
        "Redis、Postgres、Presidio）给出可操作步骤。",
    )

    # TOC-like outline
    h1(doc, "目录概览")
    numbered(
        doc,
        [
            "产品概述与架构",
            "访问入口与账号登录",
            "仪表盘（Dashboard）",
            "虚拟密钥（Virtual Keys）",
            "模型管理（Models）",
            "团队与组织（Teams / Organizations）",
            "用户与角色（Users / Roles）",
            "预算、限流与用量（Budgets / Rate Limits / Usage）",
            "路由与负载均衡（Router）",
            "缓存与 Redis",
            "护栏与安全（Guardrails）",
            "Playground / 测试台",
            "日志、审计与可观测性",
            "MCP / Tools / Prompt 相关能力",
            "OpenAI 兼容 API 调用",
            "本机部署运维说明",
            "常见问题与排障",
        ],
    )

    # 1
    h1(doc, "1. 产品概述与架构")
    h2(doc, "1.1 什么是 LiteLLM")
    para(
        doc,
        "LiteLLM 是统一的大模型访问层：对上提供 OpenAI 兼容的 HTTP API，对下对接 "
        "OpenAI、Azure、Anthropic、Gemini、Ollama、Bedrock 等 100+ 后端。"
        "Proxy（网关）模式额外提供鉴权、虚拟密钥、团队配额、限流、路由、缓存、护栏与管理 UI。",
    )
    h2(doc, "1.2 本仓库 AIGateway 定位")
    para(
        doc,
        "AIGateway 在 LiteLLM Proxy 之上叠加金融合规向的六层 Guardrails（输入 / 对话 / "
        "检索 / 工具 / 输出 / 监控），并通过 Docker Compose 编排 Postgres、Redis、"
        "Presidio、OpenTelemetry Collector。默认业务入口：http://localhost:4000 。",
    )
    h2(doc, "1.3 核心组件")
    table(
        doc,
        ["组件", "作用", "本机地址 / 说明"],
        [
            ["LiteLLM Proxy", "API 网关 + Admin UI", "http://localhost:4000"],
            ["PostgreSQL", "密钥、用户、用量、配置持久化", "localhost:5432 / 库 litellm"],
            ["Redis", "限流、预算、路由状态、缓存协调", "localhost:6379"],
            ["Presidio Analyzer/Anonymizer", "PII 检测与脱敏", ":5001 / :5002"],
            ["OTel Collector", "链路与指标导出", ":4317 / :4318"],
        ],
    )
    h2(doc, "1.4 预置模型路由别名")
    para(doc, "业务侧应使用路由别名（model_name），而不是直接写上游真实模型名：")
    table(
        doc,
        ["路由别名", "上游模型（默认）", "典型场景"],
        [
            ["default", "gpt-4o-mini", "通用对话"],
            ["reasoning", "gpt-4o", "复杂推理 / 兜底"],
            ["fast", "ollama/llama3.1:8b", "低延迟本地"],
            ["local", "ollama/llama3.1:8b", "离线 / 合规降级"],
        ],
    )
    para(doc, "回退策略：default → reasoning → local；重试 2 次；超时 60 秒；路由策略 least-busy。")

    # 2
    h1(doc, "2. 访问入口与账号登录")
    h2(doc, "2.1 打开管理控制台")
    numbered(
        doc,
        [
            "确认 LiteLLM 已启动（健康检查 http://localhost:4000/health/liveliness 返回 200）。",
            "浏览器打开 http://localhost:4000 。",
            "使用管理员账号登录。",
        ],
    )
    h2(doc, "2.2 本机默认账号")
    table(
        doc,
        ["项", "值", "说明"],
        [
            ["UI 用户名", "admin", "环境变量 UI_USERNAME"],
            ["UI 密码", "admin123", "环境变量 UI_PASSWORD（可在 .env 修改）"],
            ["Master Key", "见 AIGateway/.env 的 LITELLM_MASTER_KEY", "超级管理员 API 密钥，等同最高权限"],
        ],
    )
    para(
        doc,
        "注意：Master Key 与 UI 密码是不同概念。UI 登录用用户名/密码；程序调用 API "
        "通常使用 Virtual Key 或 Master Key（Authorization: Bearer <key>）。",
    )
    h2(doc, "2.3 登录后首页结构")
    bullets(
        doc,
        [
            "左侧导航：按功能模块切换（Keys、Models、Teams、Usage、Settings 等）。",
            "顶部：当前登录身份、组织/团队上下文切换（若启用多租户）。",
            "主内容区：列表、表单、图表与操作按钮。",
        ],
    )

    # 3
    h1(doc, "3. 仪表盘（Dashboard）")
    para(
        doc,
        "仪表盘汇总网关运行概况，帮助管理员快速判断系统是否健康、用量是否异常。",
    )
    h2(doc, "3.1 常见指标卡片")
    bullets(
        doc,
        [
            "请求量 / 成功率：近期 API 调用次数与成功比例。",
            "Spend（花费）：按 token 单价累计的费用（依赖模型价格表）。",
            "活跃密钥 / 团队：当前可用的 Virtual Key 与团队数量。",
            "模型健康：各部署是否可连通（与 Health Check 联动）。",
        ],
    )
    h2(doc, "3.2 使用建议")
    bullets(
        doc,
        [
            "每日巡检：先看错误率与 Spend 突增。",
            "变更模型或密钥后，回到仪表盘确认流量是否迁移到新路由。",
            "若指标为空，检查 Postgres 是否连通、以及是否已有真实流量写入 Spend Logs。",
        ],
    )

    # 4
    h1(doc, "4. 虚拟密钥（Virtual Keys）")
    para(
        doc,
        "Virtual Key 是发给业务方的访问凭证。推荐业务系统只使用 Virtual Key，"
        "不要直接分发 Master Key。每个 Key 可绑定团队、模型白名单、预算与限流。",
    )
    h2(doc, "4.1 功能说明")
    bullets(
        doc,
        [
            "创建 / 复制 / 删除 / 禁用密钥。",
            "设置密钥别名（Key Alias）、过期时间、允许的模型列表。",
            "绑定 Team / User / Organization，实现隔离计费。",
            "配置 TPM（Tokens Per Minute）、RPM（Requests Per Minute）、最大预算。",
            "查看该密钥历史 Spend 与调用统计。",
        ],
    )
    h2(doc, "4.2 创建步骤")
    numbered(
        doc,
        [
            "进入 Virtual Keys 页面，点击 Create / + New Key。",
            "填写别名（便于识别业务系统，如 hr-agent-prod）。",
            "选择所属 Team（可选但推荐）。",
            "勾选允许调用的模型别名（如 default、reasoning）。",
            "设置预算上限、TPM/RPM，以及过期时间。",
            "创建成功后立刻复制完整密钥字符串（通常只展示一次）。",
            "将密钥安全下发给业务方，禁止提交到 Git。",
        ],
    )
    h2(doc, "4.3 Redis 与 Virtual Keys")
    para(
        doc,
        "限流、预算与跨 Worker 状态依赖 Redis。未配置 Redis 时，UI 会提示 "
        "“No Redis configured”，限流按单进程生效，Spend 可能超标。"
        "本机已配置 Redis（REDIS_HOST/PORT/URL + coordination_redis），告警应消失。"
        "刷新页面（Cmd+Shift+R）后确认 Virtual Keys 页不再显示该横幅。",
    )
    h2(doc, "4.4 最佳实践")
    bullets(
        doc,
        [
            "一业务一密钥，便于吊销与审计。",
            "生产密钥务必设置预算与 RPM。",
            "定期轮换；离职/下线系统立即 Disable 或 Delete。",
            "密钥泄露后优先作废旧 Key，再发新 Key。",
        ],
    )

    # 5
    h1(doc, "5. 模型管理（Models）")
    h2(doc, "5.1 概念")
    bullets(
        doc,
        [
            "Model Alias（对外名称）：业务请求里的 model 字段，如 default。",
            "Deployment / litellm_params：真实上游模型、api_base、api_key、护栏列表。",
            "同一 Alias 可挂多个 Deployment，由 Router 做负载与故障转移。",
        ],
    )
    h2(doc, "5.2 UI 能做什么")
    bullets(
        doc,
        [
            "新增 / 编辑 / 删除模型部署。",
            "配置上游凭证（建议用环境变量引用，避免明文落库）。",
            "为模型绑定 Guardrails。",
            "测试连通性（Test Connection / Health）。",
            "在 STORE_MODEL_IN_DB=True 时，UI 变更可写入数据库并热生效。",
        ],
    )
    h2(doc, "5.3 配置文件与 UI 的关系")
    para(
        doc,
        "本机启动使用 config/config.local.yaml 预置模型列表。UI 中新增的模型"
        "（开启 DB 存储后）会写入 Postgres，与 YAML 并存。生产环境建议："
        "基础模型走 Git 管理的 YAML，临时实验模型可用 UI。",
    )
    h2(doc, "5.4 添加 OpenAI 兼容上游示例")
    numbered(
        doc,
        [
            "准备 OPENAI_KEY（或私有兼容端点的 API Key）。",
            "在 Models 中新建：Alias=my-gpt，model=gpt-4o-mini，api_key 引用环境变量。",
            "保存后用 Playground 或 curl 以 model=my-gpt 调用验证。",
        ],
    )

    # 6
    h1(doc, "6. 团队与组织（Teams / Organizations）")
    h2(doc, "6.1 Organization（组织）")
    para(
        doc,
        "组织是更大的租户边界，适合多事业部 / 多客户隔离。可包含多个 Team，"
        "并设置组织级预算与管理员。",
    )
    h2(doc, "6.2 Team（团队）")
    para(
        doc,
        "团队是日常协作与计费的基本单位。团队可拥有成员、共享密钥策略、模型权限与预算。",
    )
    bullets(
        doc,
        [
            "创建团队：设置 Team Name、管理员、允许模型。",
            "成员管理：邀请用户加入团队并分配角色。",
            "团队预算：月度 / 总额度；超限后拒绝新请求。",
            "团队密钥：可为团队批量签发 Virtual Key。",
        ],
    )
    h2(doc, "6.3 推荐治理模型")
    table(
        doc,
        ["层级", "职责", "示例"],
        [
            ["Organization", "公司或业务域", "零售事业部"],
            ["Team", "项目或产品线", "智能客服 / 法务 Agent"],
            ["Virtual Key", "具体应用实例", "legal-agent-prod"],
            ["User", "自然人操作者", "平台管理员 / 开发者"],
        ],
    )

    # 7
    h1(doc, "7. 用户与角色（Users / Roles）")
    h2(doc, "7.1 用户管理")
    bullets(
        doc,
        [
            "创建内部用户账号，重置密码。",
            "禁用离职人员账号。",
            "查看用户所属团队与操作审计。",
        ],
    )
    h2(doc, "7.2 角色权限（概念）")
    table(
        doc,
        ["角色", "典型权限"],
        [
            ["Proxy Admin / 超级管理员", "全部配置、密钥、账单、用户"],
            ["Org / Team Admin", "本组织或团队内的密钥、成员、预算"],
            ["Internal User", "使用 Playground、查看自身用量"],
            ["API 调用身份", "仅凭 Virtual Key 调用推理接口，无 UI 权限"],
        ],
    )
    para(doc, "具体菜单可见性以当前 LiteLLM 版本 UI 与角色策略为准。")

    # 8
    h1(doc, "8. 预算、限流与用量（Budgets / Rate Limits / Usage）")
    h2(doc, "8.1 预算（Budget）")
    bullets(
        doc,
        [
            "可设在 Key / User / Team / Organization 等层级。",
            "达到 soft budget 可告警；达到 max budget 通常拒绝后续请求。",
            "预算重置策略（按日/月）取决于版本与配置字段。",
        ],
    )
    h2(doc, "8.2 限流（Rate Limit）")
    table(
        doc,
        ["指标", "含义", "用途"],
        [
            ["RPM", "每分钟请求数", "防止刷接口"],
            ["TPM", "每分钟 token 数", "控制成本与上游配额"],
            ["并行请求数", "同时进行中的调用", "保护下游容量"],
        ],
    )
    para(
        doc,
        "限流状态存储在 Redis。多 Worker 部署时必须共享同一 Redis，否则每个进程各自计数。",
    )
    h2(doc, "8.3 用量（Usage / Spend Logs）")
    bullets(
        doc,
        [
            "按时间、模型、密钥、团队筛选 Spend。",
            "导出报表用于财务对账。",
            "排查异常高消耗请求（可关联 Request ID）。",
        ],
    )

    # 9
    h1(doc, "9. 路由与负载均衡（Router）")
    h2(doc, "9.1 路由策略")
    para(doc, "本机默认 routing_strategy: least-busy（优先把流量打到当前更空闲的部署）。")
    bullets(
        doc,
        [
            "simple-shuffle / least-busy / latency-based-routing / usage-based-routing 等策略因版本而异。",
            "可配置 fallbacks：主模型失败时自动切到备用模型。",
            "num_retries、timeout 控制瞬时故障重试与超时。",
        ],
    )
    h2(doc, "9.2 请求头路由（本仓库扩展）")
    para(
        doc,
        "AIGateway 的 TierRoutingCallback 支持通过请求头 x-model-tier 改写模型档位："
        "local | fast | premium。需确保回调已加入 litellm_settings.callbacks（本机已配置）。",
    )
    h2(doc, "9.3 健康检查与冷却")
    bullets(
        doc,
        [
            "Router 可对失败部署进入 cooldown，避免持续打到坏节点。",
            "Redis 用于跨进程共享 cooldown / 使用量状态。",
            "Admin UI 的 Health 页面可手动探测模型可用性。",
        ],
    )

    # 10
    h1(doc, "10. 缓存与 Redis")
    h2(doc, "10.1 响应缓存")
    para(
        doc,
        "litellm_settings.cache=true 且 cache_params.type=redis 时，对相同请求可返回缓存结果，"
        "降低成本与延迟。缓存命名空间本机为 litellm.cache。",
    )
    h2(doc, "10.2 协调 Redis（coordination_redis）")
    para(
        doc,
        "用于 Virtual Key 校验缓存、限流、预算、跨 Pod 协调。本机 general_settings.coordination_redis "
        "指向 REDIS_HOST/PORT；并开启 enable_redis_auth_cache=true。",
    )
    h2(doc, "10.3 运维检查")
    code_block(
        doc,
        "docker exec deployments-redis-1 redis-cli ping   # 应返回 PONG\n"
        "docker exec deployments-redis-1 redis-cli DBSIZE",
    )

    # 11
    h1(doc, "11. 护栏与安全（Guardrails）")
    h2(doc, "11.1 六层护栏总览")
    table(
        doc,
        ["层级", "时机", "本机实现", "作用"],
        [
            ["Input", "pre_call", "Presidio PII + InjectionRail", "拦截敏感信息与注入攻击"],
            ["Dialog", "pre_call", "DialogRail", "话题/轮次约束"],
            ["Retrieval", "策略侧", "policy.yaml rails.retrieval", "要求引用与来源白名单"],
            ["Tool", "pre_call", "ToolRail", "工具白名单与参数 schema"],
            ["Output", "post_call", "OutputPiiRail / LlamaGuard 等", "输出侧 PII 与安全审核"],
            ["Monitoring", "callbacks", "OTel + AuditCallback", "审计与可观测"],
        ],
    )
    h2(doc, "11.2 策略文件")
    para(
        doc,
        "策略即代码文件：AIGateway/guardrails/policy.yaml。建议变更走 MR 审批，禁止生产热改。"
        "可配置 PII 拒绝类型、注入关键词、允许/拒绝话题、工具白名单、人审工具等。",
    )
    h2(doc, "11.3 在模型上挂载护栏")
    para(
        doc,
        "在 model_list[].litellm_params.guardrails 中声明护栏名称列表，例如 default 模型挂载："
        "presidio-pii, injection-rail, dialog-rail, tool-rail, output-pii-rail。",
    )
    h2(doc, "11.4 UI 中的 Guardrails")
    bullets(
        doc,
        [
            "查看已注册护栏及其 mode（pre_call / post_call）。",
            "为模型或密钥附加护栏（视版本能力）。",
            "结合红队样本（eval/redteam.jsonl）做回归验证：python scripts/eval_gate.py。",
        ],
    )
    h2(doc, "11.5 合规门禁阈值（本项目目标）")
    bullets(
        doc,
        [
            "越狱绕过率 ≤ 2%",
            "误报率 ≤ 2%",
            "PII 泄露 = 0",
            " groundedness（接地性）≥ 0.9",
        ],
    )

    # 12
    h1(doc, "12. Playground / 测试台")
    para(
        doc,
        "Playground 提供浏览器内对话调试，无需写代码即可验证模型、密钥与护栏是否生效。",
    )
    h2(doc, "12.1 使用步骤")
    numbered(
        doc,
        [
            "选择模型别名（如 default）。",
            "可选填 Virtual Key（或使用当前登录管理员权限）。",
            "输入提示词，发送请求。",
            "观察返回内容、耗时、token、错误信息。",
            "故意输入邮箱/手机号或注入语句，验证护栏是否拦截或脱敏。",
        ],
    )
    h2(doc, "12.2 适用场景")
    bullets(
        doc,
        [
            "上线前冒烟测试。",
            "对比不同模型别名的回答质量。",
            "复现业务方报错（贴 Request ID 到日志模块查询）。",
        ],
    )

    # 13
    h1(doc, "13. 日志、审计与可观测性")
    h2(doc, "13.1 Request / Spend Logs")
    bullets(
        doc,
        [
            "查看每次调用的模型、密钥、状态码、token、费用。",
            "按时间窗口过滤失败请求。",
            "定位护栏拦截与上游 4xx/5xx。",
        ],
    )
    h2(doc, "13.2 审计回调（本仓库）")
    para(
        doc,
        "custom_callbacks.audit_callback 将关键审计事件写入 JSONL（默认路径由 "
        "AUDIT_LOG_PATH 控制，容器内 /var/lib 或本机 deployments/audit.jsonl）。"
        "可用于安全审计与事后追溯。",
    )
    h2(doc, "13.3 OpenTelemetry")
    para(
        doc,
        "回调 otel 将 trace/metrics 发往 OTEL_EXPORTER_OTLP_ENDPOINT"
        "（本机 http://127.0.0.1:4317）。可再对接 Jaeger、Grafana Tempo、Datadog 等后端。",
    )
    h2(doc, "13.4 Langfuse（可选）")
    para(
        doc,
        "若在 .env 配置 LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST，可将对话追踪同步到 Langfuse。",
    )

    # 14
    h1(doc, "14. MCP / Tools / Prompt 相关能力")
    h2(doc, "14.1 MCP（Model Context Protocol）")
    para(
        doc,
        "较新版本的 LiteLLM Proxy 支持在管理台登记 MCP Server，把外部工具以受控方式暴露给 Agent。"
        "可配置传输类型（HTTP/SSE/stdio）、鉴权与权限范围。业务 Agent（如 Legal Agent MCP）"
        "也可独立运行，通过网关只消费 LLM 能力。",
    )
    h2(doc, "14.2 Tools / 函数调用治理")
    para(
        doc,
        "ToolRail 依据 policy.yaml 的 allowlist/deny_list/schemas 校验工具名与参数。"
        "高风险工具（如 wire_transfer）可要求 human_approval。",
    )
    h2(doc, "14.3 Prompt 管理")
    para(
        doc,
        "部分版本提供 Prompt 表与版本管理，便于在 UI 中维护系统提示词模板并绑定到应用。"
        "若菜单可见，按「创建 → 版本化 → 发布 → 应用引用」流程使用。",
    )

    # 15
    h1(doc, "15. OpenAI 兼容 API 调用")
    h2(doc, "15.1 Chat Completions")
    code_block(
        doc,
        "curl http://localhost:4000/v1/chat/completions \\\n"
        "  -H \"Authorization: Bearer <VIRTUAL_OR_MASTER_KEY>\" \\\n"
        "  -H \"Content-Type: application/json\" \\\n"
        "  -d '{\n"
        "    \"model\": \"default\",\n"
        "    \"messages\": [{\"role\": \"user\", \"content\": \"你好\"}]\n"
        "  }'",
    )
    h2(doc, "15.2 作为 OpenAI SDK 基座")
    code_block(
        doc,
        "export OPENAI_BASE_URL=http://localhost:4000/v1\n"
        "export OPENAI_API_KEY=<VIRTUAL_KEY>\n"
        "# 然后按 OpenAI SDK 正常调用，model 使用路由别名",
    )
    h2(doc, "15.3 其他常见端点")
    table(
        doc,
        ["端点", "用途"],
        [
            ["/v1/chat/completions", "对话补全"],
            ["/v1/embeddings", "向量嵌入（若已配置 embedding 模型）"],
            ["/v1/models", "列出可用模型别名"],
            ["/health/liveliness", "存活探针"],
            ["/health/readiness", "就绪探针（含 DB/缓存等详情，需鉴权）"],
            ["/ui 或根路径", "Admin 控制台"],
        ],
    )
    h2(doc, "15.4 错误码解读（常见）")
    bullets(
        doc,
        [
            "401：未传密钥或密钥无效。",
            "429：触发 RPM/TPM 或上游限流。",
            "预算相关错误：Key/Team 超额。",
            "护栏拦截：请求被 Injection/PII/Tool 策略拒绝（查看响应 detail / 日志）。",
            "DB 未连接：UI 登录或密钥功能失败（检查 Postgres 与 DATABASE_URL）。",
        ],
    )

    # 16
    h1(doc, "16. 本机部署运维说明")
    h2(doc, "16.1 依赖服务启动")
    code_block(
        doc,
        "cd /Users/yudong/AI-Coding/AIGateway/deployments\n"
        "docker compose up -d db redis presidio-analyzer presidio-anonymizer otel-collector",
    )
    h2(doc, "16.2 启动 LiteLLM（本机 Python 方式）")
    para(
        doc,
        "因官方 Docker 镜像在部分 Apple Silicon 环境会 Illegal instruction，本机采用 venv 进程："
        "读取 .env，连接 127.0.0.1 的 Postgres/Redis，配置文件为 config/config.local.yaml，端口 4000。",
    )
    code_block(
        doc,
        "cd /Users/yudong/AI-Coding/AIGateway\n"
        "source .venv/bin/activate\n"
        "export DATABASE_URL=postgresql://litellm:litellm@127.0.0.1:5432/litellm\n"
        "export REDIS_HOST=127.0.0.1 REDIS_PORT=6379 REDIS_URL=redis://127.0.0.1:6379/0\n"
        "export PYTHONPATH=$PWD\n"
        "litellm --config config/config.local.yaml --port 4000 --num_workers 1",
    )
    h2(doc, "16.3 关键服务")
    code_block(
        doc,
        "pkill -f 'litellm --config'\n"
        "cd deployments && docker compose stop",
    )
    h2(doc, "16.4 关键配置文件")
    table(
        doc,
        ["文件", "用途"],
        [
            [".env", "密钥、DB、Redis、上游 Key"],
            ["config/config.local.yaml", "本机路由/护栏/缓存"],
            ["config/config.dev.yaml", "Compose 容器内开发配置"],
            ["guardrails/policy.yaml", "护栏策略即代码"],
            ["deployments/docker-compose.yml", "依赖容器编排"],
        ],
    )
    h2(doc, "16.5 紧急降级")
    code_block(
        doc,
        "python scripts/rollback.py --mode route --target local --config config/config.local.yaml",
    )

    # 17
    h1(doc, "17. 常见问题与排障")
    h2(doc, "17.1 登录报 Not connected to DB")
    para(
        doc,
        "说明 Proxy 未连上 Postgres。检查 deployments-db-1 是否 healthy，"
        "DATABASE_URL 是否指向 127.0.0.1:5432（本机进程不要用主机名 db）。",
    )
    h2(doc, "17.2 Virtual Keys 提示 No Redis configured")
    para(
        doc,
        "启动 Redis 并设置 REDIS_* / coordination_redis，重启 Proxy 后强制刷新浏览器。",
    )
    h2(doc, "17.3 Docker 镜像启动即退出（Illegal instruction）")
    para(
        doc,
        "改用本机 Python venv 运行 litellm；依赖仍用 Compose。",
    )
    h2(doc, "17.4 调用上游失败")
    bullets(
        doc,
        [
            "检查 OPENAI_KEY / Ollama 是否可达（11434）。",
            "确认 model 使用的是别名 default/reasoning/fast/local。",
            "查看 Spend/Logs 中的上游错误信息。",
        ],
    )
    h2(doc, "17.5 护栏误杀 / 未拦截")
    bullets(
        doc,
        [
            "核对模型是否挂载了对应 guardrails。",
            "调整 policy.yaml 的 deny_patterns / PII 类型后重启 Proxy。",
            "跑 scripts/eval_gate.py 做回归。",
        ],
    )

    # Appendix
    h1(doc, "附录 A：功能速查表")
    table(
        doc,
        ["功能模块", "主要用户", "关键操作"],
        [
            ["Dashboard", "管理员", "巡检健康与花费"],
            ["Virtual Keys", "管理员 / 团队管理员", "发钥、限流、吊销"],
            ["Models", "管理员", "接入上游、挂护栏"],
            ["Teams / Orgs", "管理员", "隔离与配额"],
            ["Users / Roles", "管理员", "账号与权限"],
            ["Usage / Logs", "管理员 / 财务", "对账与排障"],
            ["Playground", "开发者", "联调验证"],
            ["Guardrails", "安全 / 合规", "策略与拦截"],
            ["Settings", "管理员", "全局开关、回调、Redis"],
            ["API /v1/*", "业务系统", "推理调用"],
        ],
    )

    h1(doc, "附录 B：安全建议")
    numbered(
        doc,
        [
            "Master Key 仅限运维保管，不进入业务仓库。",
            "业务统一使用带预算的 Virtual Key。",
            "生产开启 Redis 与 Postgres 备份。",
            "护栏策略变更走代码评审。",
            "定期审查高权限用户与长期有效密钥。",
            "日志中可能含提示词片段，按数据分级保护。",
        ],
    )

    h1(doc, "附录 C：参考链接")
    bullets(
        doc,
        [
            "LiteLLM 官方文档：https://docs.litellm.ai/",
            "本仓库说明：AIGateway/README.md",
            "护栏分析：AIGateway/docs/six-layer-guardrails-analysis.md",
            "项目根 README 中 AIGateway 章节",
        ],
    )

    para(doc, "")
    para(doc, "—— 文档结束 ——", bold=True)
    add_subtitle(doc, "如需增补截图版操作手册或英文版，可基于本文档继续扩展。")

    doc.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
