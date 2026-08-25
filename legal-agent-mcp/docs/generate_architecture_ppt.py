#!/usr/bin/env python3
"""Generate Legal Agent MCP architecture PowerPoint."""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

OUTPUT = Path(__file__).parent / "architecture.pptx"

C_PRIMARY = RGBColor(0x1A, 0x36, 0x5D)
C_ACCENT = RGBColor(0x25, 0x63, 0xEB)
C_TEXT = RGBColor(0x1F, 0x29, 0x37)
C_MUTED = RGBColor(0x6B, 0x72, 0x80)
C_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
C_LIGHT_BG = RGBColor(0xF3, 0xF4, 0xF6)
C_GREEN = RGBColor(0x05, 0x96, 0x69)
C_PURPLE = RGBColor(0x7C, 0x3A, 0xED)
C_LIGHT_BLUE = RGBColor(0xBF, 0xDB, 0xFE)
C_SKY = RGBColor(0x93, 0xC5, 0xFD)
C_GRAY_LINE = RGBColor(0xE5, 0xE7, 0xEB)
C_LIGHT_TEXT = RGBColor(0xE5, 0xE7, 0xEB)


def set_run_font(run, size=18, bold=False, color=C_TEXT, name="PingFang SC"):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = name


def blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def add_title_bar(slide, title: str, subtitle: str | None = None):
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(10), Inches(1.05))
    bar.fill.solid()
    bar.fill.fore_color.rgb = C_PRIMARY
    bar.line.fill.background()
    tf = bar.text_frame
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = title
    set_run_font(run, size=26, bold=True, color=C_WHITE)
    if subtitle:
        sub = slide.shapes.add_textbox(Inches(0.5), Inches(1.12), Inches(9), Inches(0.4))
        r = sub.text_frame.paragraphs[0].add_run()
        r.text = subtitle
        set_run_font(r, size=13, color=C_MUTED)


def add_bullets(slide, items, left=0.5, top=1.55, width=9, height=5.5, base_size=16):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        text, level = item if isinstance(item, tuple) else (item, 0)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = level
        p.space_after = Pt(5)
        run = p.add_run()
        run.text = text
        set_run_font(run, size=base_size - level * 2)


def add_table_slide(prs, title: str, headers, rows, col_widths=None):
    slide = blank_slide(prs)
    add_title_bar(slide, title)
    row_count = len(rows) + 1
    cols = len(headers)
    table_shape = slide.shapes.add_table(
        row_count, cols, Inches(0.35), Inches(1.5), Inches(9.3), Inches(min(0.42 * row_count, 5.5))
    )
    table = table_shape.table
    if col_widths:
        for i, w in enumerate(col_widths):
            table.columns[i].width = Inches(w)
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = C_PRIMARY
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                set_run_font(r, size=11, bold=True, color=C_WHITE)
    for i, row in enumerate(rows, start=1):
        for j, val in enumerate(row):
            cell = table.cell(i, j)
            cell.text = val
            for p in cell.text_frame.paragraphs:
                for r in p.runs:
                    set_run_font(r, size=10)


def add_flow_slide(prs, title: str, steps, note: str | None = None):
    slide = blank_slide(prs)
    add_title_bar(slide, title)
    y = 1.5
    for i, step in enumerate(steps, 1):
        circle = slide.shapes.add_shape(9, Inches(0.4), Inches(y), Inches(0.32), Inches(0.32))
        circle.fill.solid()
        circle.fill.fore_color.rgb = C_ACCENT
        circle.line.fill.background()
        ctf = circle.text_frame
        ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
        cp = ctf.paragraphs[0]
        cp.alignment = PP_ALIGN.CENTER
        cr = cp.add_run()
        cr.text = str(i)
        set_run_font(cr, size=11, bold=True, color=C_WHITE)
        box = slide.shapes.add_textbox(Inches(0.85), Inches(y - 0.03), Inches(8.6), Inches(0.5))
        br = box.text_frame.paragraphs[0].add_run()
        br.text = step
        set_run_font(br, size=13)
        if i < len(steps):
            arr = slide.shapes.add_textbox(Inches(0.48), Inches(y + 0.34), Inches(0.3), Inches(0.22))
            ar = arr.text_frame.paragraphs[0].add_run()
            ar.text = "↓"
            set_run_font(ar, size=13, color=C_MUTED)
        y += 0.62
    if note:
        nb = slide.shapes.add_textbox(Inches(0.5), Inches(6.35), Inches(9), Inches(0.45))
        nr = nb.text_frame.paragraphs[0].add_run()
        nr.text = note
        set_run_font(nr, size=11, color=C_MUTED)


def add_architecture_boxes(slide):
    layers = [
        ("AI 客户端层", "Cursor · Codex · DeepSeek Harness · 其他 MCP Host", C_PRIMARY),
        ("MCP 协议", "stdio JSON-RPC  ·  tools/list  ·  tools/call", C_ACCENT),
        ("legal-agent-mcp", "index.ts → tools.ts → legal-client.ts", C_GREEN),
        ("HTTP/REST", "Bearer JWT  ·  JSON + FormData", C_MUTED),
        ("legal-agent backend", "auth · legal · contract · content · llm_service", C_PURPLE),
    ]
    y = 1.48
    for idx, (name, desc, color) in enumerate(layers):
        rect = slide.shapes.add_shape(1, Inches(0.7), Inches(y), Inches(8.6), Inches(0.82))
        rect.fill.solid()
        rect.fill.fore_color.rgb = color
        rect.line.fill.background()
        tf = rect.text_frame
        r1 = tf.paragraphs[0].add_run()
        r1.text = name
        set_run_font(r1, size=15, bold=True, color=C_WHITE)
        r2 = tf.add_paragraph().add_run()
        r2.text = desc
        set_run_font(r2, size=11, color=C_LIGHT_TEXT)
        if idx < len(layers) - 1:
            arr = slide.shapes.add_textbox(Inches(4.55), Inches(y + 0.84), Inches(0.4), Inches(0.25))
            ar = arr.text_frame.paragraphs[0].add_run()
            ar.text = "▼"
            set_run_font(ar, size=14, bold=True, color=C_MUTED)
        y += 1.0


def build():
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    # 1 Title
    s = blank_slide(prs)
    bg = s.shapes.add_shape(1, Inches(0), Inches(0), Inches(10), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = C_PRIMARY
    bg.line.fill.background()
    tbox = s.shapes.add_textbox(Inches(0.8), Inches(2.1), Inches(8.4), Inches(2))
    tr = tbox.text_frame.paragraphs[0].add_run()
    tr.text = "Legal Agent MCP"
    set_run_font(tr, size=42, bold=True, color=C_WHITE)
    tr2 = tbox.text_frame.add_paragraph().add_run()
    tr2.text = "技术架构与模块实现分析"
    set_run_font(tr2, size=22, color=C_LIGHT_BLUE)
    mr = s.shapes.add_textbox(Inches(0.8), Inches(5.7), Inches(8), Inches(0.6)).text_frame.paragraphs[0].add_run()
    mr.text = "legal-agent-mcp  ·  MCP over stdio  ·  2026-08-24"
    set_run_font(mr, size=13, color=C_SKY)

    # 2 Overview
    s = blank_slide(prs)
    add_title_bar(s, "1. 概述", "MCP 适配层：将 Legal Agent 能力暴露给 AI 客户端")
    add_bullets(s, [
        "legal-agent-mcp 是独立的 Model Context Protocol Server",
        "定位：协议桥接器，不承载法律业务逻辑",
        ("技术栈", 0),
        ("TypeScript + Node.js ≥ 20", 1),
        ("@modelcontextprotocol/sdk + Zod", 1),
        ("传输：stdio（JSON-RPC）", 1),
        ("依赖：Legal Agent FastAPI 后端（默认 :8010）", 1),
        ("集成客户端：Cursor · Codex · DeepSeek Harness", 0),
    ])

    # 3 Design principles
    s = blank_slide(prs)
    add_title_bar(s, "2. 设计原则")
    y = 1.55
    for title, desc in [
        ("薄适配层", "MCP 只做协议转换与 HTTP 封装；推理/解析/比对在后端"),
        ("stdio 优先", "与 Cursor/Codex 集成一致，无需额外端口"),
        ("延迟认证", "启动不登录；首次调用需鉴权 API 时才获取 JWT"),
        ("工具对齐业务", "6 个 MCP 工具直接映射 Legal Agent 核心 API"),
    ]:
        card = s.shapes.add_shape(1, Inches(0.5), Inches(y), Inches(9), Inches(1.1))
        card.fill.solid()
        card.fill.fore_color.rgb = C_LIGHT_BG
        card.line.color.rgb = C_GRAY_LINE
        tf = card.text_frame
        r1 = tf.paragraphs[0].add_run()
        r1.text = title
        set_run_font(r1, size=17, bold=True, color=C_ACCENT)
        r2 = tf.add_paragraph().add_run()
        r2.text = desc
        set_run_font(r2, size=13)
        y += 1.25

    # 4 MCP Server / Client / Host
    add_table_slide(
        prs,
        "3. MCP Server / Client / Host",
        ["概念", "本项目对应", "职责"],
        [
            ["MCP Server", "legal-agent-mcp", "提供 6 个工具\ntools/list · tools/call"],
            ["MCP Client", "Cursor 内置模块", "stdio JSON-RPC\n连接 Server · 转发结果"],
            ["MCP Host", "Cursor / Codex / DSH", "整应用：LLM + Client + UI\n协调对话与工具调用"],
        ],
        [1.8, 2.5, 5.0],
    )
    host_slide = prs.slides[-1]
    note = host_slide.shapes.add_textbox(Inches(0.5), Inches(1.08), Inches(9), Inches(0.35))
    nr = note.text_frame.paragraphs[0].add_run()
    nr.text = "Host 雇 LLM 决策 → Client 跑腿调 Server → Server 调 Legal Agent"
    set_run_font(nr, size=12, bold=True, color=C_ACCENT)

    # 5 LLM vs MCP — roles table
    add_table_slide(
        prs,
        "4. 各角色职责对照",
        ["角色", "职责", "不负责"],
        [
            ["LLM", "理解意图；输出 tool call\n阅读 result；生成回复", "不连 MCP Server"],
            ["MCP Host", "管理对话；spawn Server\n协调 LLM 与 Client", "不实现 MCP 协议细节"],
            ["MCP Client", "tools/list · tools/call\nstdio JSON-RPC", "不做法律推理"],
            ["MCP Server", "MCP ↔ HTTP 转换\nJWT · 参数校验", "不做法律推理"],
        ],
        [1.4, 4.0, 3.9],
    )
    # Add subtitle on roles slide
    roles_slide = prs.slides[-1]
    note = roles_slide.shapes.add_textbox(Inches(0.5), Inches(1.08), Inches(9), Inches(0.35))
    nr = note.text_frame.paragraphs[0].add_run()
    nr.text = "LLM 不直接调用 MCP — 由 Host 内 MCP Client 连接 MCP Server"
    set_run_font(nr, size=12, bold=True, color=C_ACCENT)

    # 6 LLM call chain
    add_flow_slide(
        prs,
        "5. LLM 完整调用链",
        [
            "MCP Host spawn MCP Server → tools/list 获取工具定义",
            "用户提问 → Host 将消息 + 工具 schema 发给 LLM",
            "LLM 返回 tool call 意图（工具名 + 参数）",
            "Host 交给 MCP Client → tools/call (stdio)",
            "MCP Server (legal-agent-mcp) → HTTP API",
            "Client 返回 tool result → Host 注入 LLM 上下文",
            "LLM 整合结果 → 生成自然语言回复 → 用户",
        ],
        "LLM=决策层 · Client=协议层 · Server=适配层 · Host=大管家",
    )

    # 7 Two LLMs distinction
    s = blank_slide(prs)
    add_title_bar(s, "6. 两个 LLM 接入点", "不要混淆对话 LLM 与业务 LLM")
    add_bullets(s, [
        "对话 LLM（Cursor / Codex 内置）",
        ("决定是否调用 MCP 工具、如何回复用户", 1),
        ("与 MCP Host 通信，不直连 legal-agent-mcp", 1),
        "业务 LLM（Legal Agent llm_service）",
        ("执行法律检索、问答、合同审核等生成任务", 1),
        ("由后端 HTTP API 触发，用户不可见", 1),
        "调用路径",
        ("对话 LLM → Host → MCP Client → MCP Server → HTTP → 业务 LLM", 1),
        "常见误解",
        ("LLM 直连 MCP ✗  |  legal-agent 是 MCP Server ✗", 1),
        ("MCP Client = LLM ✗  |  Host = Client ✗", 1),
    ], base_size=14)

    # 8 Architecture
    s = blank_slide(prs)
    add_title_bar(s, "7. 总体分层架构")
    add_architecture_boxes(s)

    # 9 Structure
    s = blank_slide(prs)
    add_title_bar(s, "8. 项目结构")
    add_bullets(s, [
        "legal-agent-mcp/",
        ("src/index.ts         MCP Server 入口，StdioTransport", 1),
        ("src/tools.ts         工具定义 + Zod 校验 + 结果格式化", 1),
        ("src/legal-client.ts  HTTP 客户端 + JWT 管理", 1),
        ("dist/index.js        tsc 编译输出（MCP 启动入口）", 1),
        ("docs/                架构文档与 PPT", 1),
        "三模块职责分离：协议层 → 工具层 → 传输层",
    ], base_size=15)

    # 9 Code chain overview
    add_table_slide(
        prs,
        "9. 调用链代码模块总览",
        ["层级", "路径 / 仓库", "关键模块"],
        [
            ["MCP Host+Client", "Cursor / DSH mcp-client", "connection.ts spawn\ntools.ts callToolUncached"],
            ["MCP Server", "legal-agent-mcp/src", "index.ts · tools.ts · legal-client.ts"],
            ["MCP SDK", "@modelcontextprotocol/sdk", "Server · StdioServerTransport"],
            ["Legal Agent", "legal-agent/backend/app", "legal.py · deps.py · llm_service.py"],
        ],
        [2.0, 3.2, 4.1],
    )

    # 10 legal_search code trace
    add_flow_slide(
        prs,
        "10. legal_search 代码逐步追踪",
        [
            "Client: callToolUncached → tools/call (stdio)",
            "index.ts: CallToolRequestSchema → handleToolCall()",
            "tools.ts: searchArgs.parse → client.search()",
            "legal-client.ts: ensureToken() → request()",
            "POST /api/v1/search → legal.py::search()",
            "deps.py::get_current_user → llm_service.legal_search()",
            "tools.ts: Markdown 格式化 → MCP text content 返回",
        ],
        "编译入口：dist/index.js  ·  配置：~/.cursor/mcp.json",
    )

    # 11 Three files responsibility
    add_table_slide(
        prs,
        "11. 三文件职责与关键符号",
        ["文件", "层级", "关键符号"],
        [
            ["index.ts", "MCP 协议入口", "ListTools / CallTool handler\nStdioServerTransport.connect"],
            ["tools.ts", "工具路由层", "TOOL_DEFINITIONS\nhandleToolCall · Zod schema"],
            ["legal-client.ts", "HTTP 传输层", "fromEnv · ensureToken · login\nsearch/chat/request"],
        ],
        [1.8, 2.0, 5.5],
    )

    # 12 Tool-level code mapping
    add_table_slide(
        prs,
        "12. 工具级代码映射",
        ["MCP 工具", "tools.ts", "legal-client", "后端服务"],
        [
            ["legal_search", "case legal_search", "search()", "llm_service.legal_search"],
            ["legal_chat", "case legal_chat", "chat()", "chat_reply + ORM"],
            ["contract_draft", "case contract_draft", "draftContract()", "draft_contract"],
            ["contract_review", "case review_file", "reviewContractFile()", "upload + review"],
            ["contract_compare", "case compare_files", "compareContractFiles()", "compare_service"],
            ["legal_capabilities", "case capabilities", "getMetadata()", "content.py"],
        ],
        [2.0, 2.2, 2.3, 2.8],
    )

    # 13 contract_review code chain
    add_flow_slide(
        prs,
        "13. contract_review 复合调用链",
        [
            "handleToolCall('contract_review_file')",
            "reviewContractFile(path) = upload + runReview",
            "uploadContract → POST /contract/upload [multipart]",
            "contract.py → document_parser.parse_file",
            "runReview(id) → POST /contract/review/{id}",
            "llm_service.review_contract → Markdown 报告",
        ],
        "一次 tools/call · 两次 HTTP 请求",
    )

    # 14 DSH mcp-client reference
    s = blank_slide(prs)
    add_title_bar(s, "14. Host 侧参考：DSH mcp-client", "Cursor/Codex 闭源，以 Harness 为可读参考")
    add_bullets(s, [
        "deepseek-harness-master/packages/mcp/mcp-client/",
        ("connection.ts — startConnection() spawn 子进程", 1),
        ("transport.ts — StdioClientTransport", 1),
        ("tools.ts — syncTools() · listToolsUncached()", 1),
        ("tools.ts — callToolUncached() 发 tools/call", 1),
        "DSH 公开工具名：mcp__<serverName>__<rawName>",
        ("LLM 见 public name · wire 仍发 legal_search", 1),
        "运行时入口：node dist/index.js（dist/ 由 tsc 编译 src/）",
    ], base_size=14)

    # 15 Modules table (API layer detail)
    add_table_slide(
        prs,
        "15. 核心模块职责",
        ["模块", "层级", "职责"],
        [
            ["index.ts", "MCP Server", "ListTools / CallTool 注册\nStdioServerTransport"],
            ["tools.ts", "工具层", "TOOL_DEFINITIONS · Zod 校验\nhandleToolCall · Markdown 格式化"],
            ["legal-client.ts", "HTTP 层", "JWT 延迟登录 · JSON + FormData\n180s 超时 · 文件上传"],
        ],
        [1.6, 1.4, 6.3],
    )

    # 16 Tools API mapping
    add_table_slide(
        prs,
        "16. MCP 工具 ↔ API 映射",
        ["MCP 工具", "HTTP", "API 路径", "后端服务"],
        [
            ["legal_search", "POST", "/api/v1/search", "llm_service.legal_search"],
            ["legal_chat", "POST", "/api/v1/chat", "chat_reply + DB 会话"],
            ["contract_draft", "POST", "/api/v1/contract/draft", "draft_contract"],
            ["contract_review_file", "POST×2", "upload → review/{id}", "parser + review"],
            ["contract_compare_files", "POST", "/api/v1/contract/compare", "compare_service"],
            ["legal_capabilities", "GET×2", "content/*", "content_service"],
        ],
        [2.1, 0.75, 2.9, 3.55],
    )

    # 17 Auth flow
    add_flow_slide(
        prs,
        "17. JWT 延迟认证",
        [
            "tools/call 触发需鉴权 API → ensureToken()",
            "LEGAL_AGENT_TOKEN 已配置？→ 直接使用",
            "内存有缓存 token？→ 返回缓存",
            "否则 POST /api/v1/auth/login {username, password}",
            "authenticate_user → create_access_token → 缓存内存",
            "后续 request() 附加 Authorization: Bearer <token>",
        ],
        "环境变量优先级：TOKEN > USERNAME/PASSWORD > 默认 admin/admin123",
    )

    # 18 legal_search sequence
    add_flow_slide(
        prs,
        "18. 序列图：legal_search 调用",
        [
            "用户提问 → LLM 决策调用 legal_search",
            "MCP Host → tools/call (stdio JSON-RPC)",
            "index.ts → tools.ts → Zod 校验参数",
            "legal-client.ts → ensureToken() → POST /api/v1/search",
            "FastAPI → llm_service.legal_search()",
            "SearchResponse → Markdown 格式化 → MCP text content",
            "LLM 整合工具结果 → 回复用户",
        ],
    )

    # 19 MCP startup
    add_flow_slide(
        prs,
        "19. 序列图：MCP 启动与工具发现",
        [
            "MCP Host spawn 子进程：node dist/index.js",
            "legal-agent-mcp：LegalAgentClient.fromEnv()",
            "JSON-RPC initialize → 返回 capabilities: tools",
            "tools/list → 返回 6 个工具定义",
            "此阶段不连接 Legal Agent 后端，token 未初始化",
        ],
    )

    # 20 Contract review sequence
    add_flow_slide(
        prs,
        "20. 序列图：合同审核（两步式）",
        [
            "contract_review_file { file_path, review_mode }",
            "本地校验：文件存在，扩展名 .doc/.docx/.pdf",
            "POST /contract/upload → document_parser 提取正文",
            "创建 ContractReview，status=uploaded，返回 review_id",
            "POST /contract/review/{id} → llm_service.review_contract()",
            "status=completed → 返回 Markdown 审核报告",
        ],
    )

    # 21 Chat & compare
    s = blank_slide(prs)
    add_title_bar(s, "21. 序列图：问答与比对")
    add_bullets(s, [
        "多轮法律问答 (legal_chat)",
        ("首轮：无 session_id → 创建 ChatSession + 保存消息", 1),
        ("续轮：带 session_id → 加载会话 + 追加消息", 1),
        ("MCP 返回 session_id 供 LLM 后续调用", 1),
        "合同比对 (contract_compare_files)",
        ("读取两份文件 → POST /contract/compare", 1),
        ("并行 parse_file → compare_texts()", 1),
        ("返回 summary + changes[] + risk_note", 1),
        "合同起草 (contract_draft)：purpose/style → llm_service → 草案文本",
    ], base_size=14)

    # 22 Backend
    s = blank_slide(prs)
    add_title_bar(s, "22. Legal Agent 后端架构")
    add_bullets(s, [
        "FastAPI 分层：api/v1 → services → models/core",
        ("auth.py — JWT 登录", 1),
        ("legal.py — 检索 / 问答", 1),
        ("contract.py — 上传 / 审核 / 起草 / 比对", 1),
        ("content.py — 元数据（检索类型、风格）", 1),
        "llm_service：OpenAI API + Mock 回退（未配置 KEY 时演示模式）",
        "document_parser：PDF/DOCX 解析，可选 OCR（扫描件）",
        "基础设施：SQLite · 文件存储 · OpenAI API",
    ], base_size=14)

    # 23 Client integration
    add_table_slide(
        prs,
        "23. 客户端集成",
        ["客户端", "配置文件", "启动方式"],
        [
            ["Cursor", "~/.cursor/mcp.json", "command: node + args + env"],
            ["Codex", "~/.codex/config.toml", "[mcp_servers.legal-agent]"],
            ["DeepSeek Harness", "cordis.yml", "mcp.servers.legal-agent (stdio)"],
        ],
        [2, 3.5, 3.8],
    )

    # 24 Security
    s = blank_slide(prs)
    add_title_bar(s, "24. 错误处理与安全")
    add_bullets(s, [
        "错误处理",
        ("tools.ts 捕获所有异常 → isError: true，进程不崩溃", 1),
        ("HTTP 4xx/5xx 解析 FastAPI detail 字段", 1),
        ("Zod 参数校验失败 → 友好错误信息", 1),
        ("超时：登录 30s · API/文件 180s", 1),
        "安全考量",
        ("凭据通过 MCP Host env 注入，不硬编码", 1),
        ("文件路径访问依赖 Host 沙箱策略", 1),
        ("生产环境使用 HTTPS + LEGAL_AGENT_TOKEN", 1),
        ("Token 过期不自动刷新，需重启或预设 TOKEN", 1),
    ], base_size=14)

    # 25 Deployment
    s = blank_slide(prs)
    add_title_bar(s, "25. 部署拓扑")
    add_bullets(s, [
        "开发环境（默认）",
        ("Cursor ←stdio→ legal-agent-mcp ←HTTP :8010→ legal-agent", 1),
        "生产环境（建议）",
        ("MCP Server 与 AI Client 同机或容器", 1),
        ("LEGAL_AGENT_URL=https://legal-api.example.com", 1),
        ("LEGAL_AGENT_TOKEN=<service-account-jwt>", 1),
        "扩展方向",
        ("新增 MCP 工具（会话列表、审核历史等）", 1),
        ("MCP Streamable HTTP · 远程部署 + mTLS", 1),
    ], base_size=15)

    # 26 Summary
    s = blank_slide(prs)
    bg = s.shapes.add_shape(1, Inches(0), Inches(0), Inches(10), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = C_PRIMARY
    bg.line.fill.background()
    sum_box = s.shapes.add_textbox(Inches(0.8), Inches(1.7), Inches(8.4), Inches(4.2))
    tf = sum_box.text_frame
    r = tf.paragraphs[0].add_run()
    r.text = "总结"
    set_run_font(r, size=30, bold=True, color=C_WHITE)
    for line in [
        "legal-agent-mcp = MCP 薄适配层 + Legal Agent 能力出口",
        "index.ts → tools.ts → legal-client.ts → HTTP API",
        "LLM 不直连 MCP — Host 内 Client 调 Server",
        "6 个工具 · stdio · 延迟 JWT · Cursor/Codex/DSH",
        "详细文档：docs/architecture.md §1.2",
    ]:
        p = tf.add_paragraph()
        p.space_before = Pt(10)
        r2 = p.add_run()
        r2.text = "▸  " + line
        set_run_font(r2, size=17, color=C_LIGHT_BLUE)

    prs.save(OUTPUT)
    print(f"Generated: {OUTPUT} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    build()
