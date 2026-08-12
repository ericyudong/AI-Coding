"""
Agent Harness 系统架构设计文档生成器
生成 Word 格式的系统架构设计文档
"""
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
import datetime

def set_cell_shading(cell, color):
    """设置单元格背景色"""
    shading_elm = cell._element.get_or_add_tcPr()
    shading = shading_elm.makeelement('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd', {
        '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fill': color,
        '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val': 'clear'
    })
    shading_elm.append(shading)

def add_styled_table(doc, headers, rows, col_widths=None):
    """添加样式化表格"""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    # 表头
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.bold = True
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_shading(cell, '2B579A')
    # 数据行
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            cell = table.rows[r_idx + 1].cells[c_idx]
            cell.text = str(val)
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(9)
            if r_idx % 2 == 1:
                set_cell_shading(cell, 'EDF2F9')
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Cm(w)
    doc.add_paragraph()
    return table

def build_document():
    doc = Document()

    # ===== 页面设置 =====
    section = doc.sections[0]
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.8)
    section.right_margin = Cm(2.8)

    # ===== 封面 =====
    for _ in range(6):
        doc.add_paragraph()
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run('Agent Harness 框架')
    run.bold = True
    run.font.size = Pt(32)
    run.font.color.rgb = RGBColor(0x2B, 0x57, 0x9A)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run('系统架构设计文档')
    run.bold = True
    run.font.size = Pt(22)
    run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    doc.add_paragraph()
    ver = doc.add_paragraph()
    ver.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = ver.add_run('Version 1.0')
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    doc.add_paragraph()
    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = date_p.add_run(f'日期: {datetime.date.today().strftime("%Y年%m月%d日")}')
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    doc.add_page_break()

    # ===== 目录页 =====
    doc.add_heading('目录', level=1)
    toc_items = [
        ('1', '系统概述', '3'),
        ('2', '架构设计总览', '4'),
        ('3', '核心模块设计', '5'),
        ('3.1', 'Agent 核心运行时', '5'),
        ('3.2', '内存管理子系统', '6'),
        ('3.3', '遥测数据收集子系统', '8'),
        ('3.4', '自进化引擎子系统', '9'),
        ('3.5', 'Web 控制台子系统', '10'),
        ('4', '数据流设计', '11'),
        ('5', '技术选型', '12'),
        ('6', '接口设计', '13'),
        ('7', '部署架构', '14'),
        ('8', '扩展性设计', '15'),
    ]
    for num, title_text, page in toc_items:
        p = doc.add_paragraph()
        indent = '    ' if '.' in num else ''
        run = p.add_run(f'{indent}{num}  {title_text}')
        run.font.size = Pt(11)
        if '.' not in num:
            run.bold = True

    doc.add_page_break()

    # ===== 1. 系统概述 =====
    doc.add_heading('1. 系统概述', level=1)

    doc.add_heading('1.1 项目背景', level=2)
    doc.add_paragraph(
        'Agent Harness 是一个面向 AI Agent 的工程化运行框架，旨在为智能体提供完整的运行时管理能力。'
        '随着大语言模型（LLM）驱动的 Agent 应用日益复杂，传统的单次调用模式已无法满足多步骤推理、'
        '长期记忆保持、运行时可观测性和持续自我优化等需求。本框架通过模块化的架构设计，'
        '为 Agent 提供从初始化到终止的完整生命周期管理。'
    )

    doc.add_heading('1.2 设计目标', level=2)
    goals = [
        '运行时管理: 提供 Agent 完整的生命周期管理（创建→就绪→运行→暂停→恢复→终止）',
        '内存管理: 实现多层次内存架构（短期记忆/工作记忆/长期记忆），支持记忆的存储、检索、整合与淘汰',
        '可观测性: 自动收集 Agent 运行时的行为数据、性能指标和交互记录，支持全链路追踪',
        '自进化: 基于收集的运行时数据，自动分析性能瓶颈、优化策略参数和调优提示词',
        '可扩展性: 通过插件机制支持自定义工具、存储后端和进化策略',
        '可视化: 提供 Web 控制台实现实时监控和交互操作',
    ]
    for g in goals:
        p = doc.add_paragraph(g, style='List Bullet')

    doc.add_heading('1.3 适用范围', level=2)
    doc.add_paragraph(
        '本框架适用于以下场景：\n'
        '• 基于 LLM 的对话式 Agent 系统\n'
        '• 多步骤任务规划与执行 Agent\n'
        '• 需要长期记忆保持的知识助手\n'
        '• 需要持续优化的自动化工作流 Agent\n'
        '• Agent 系统的研发调试与性能分析'
    )

    doc.add_page_break()

    # ===== 2. 架构设计总览 =====
    doc.add_heading('2. 架构设计总览', level=1)

    doc.add_heading('2.1 分层架构', level=2)
    doc.add_paragraph(
        '系统采用经典的分层架构设计，自底向上分为五层：'
    )
    add_styled_table(doc,
        ['层次', '名称', '职责', '核心组件'],
        [
            ['L1', '基础设施层', '配置管理、日志、存储抽象', 'ConfigManager, Logger, StorageBackend'],
            ['L2', '核心运行时层', 'Agent生命周期、任务调度', 'AgentHarness, BaseAgent, LifecycleManager'],
            ['L3', '能力服务层', '内存管理、遥测收集、自进化', 'MemoryManager, TelemetryCollector, EvolutionEngine'],
            ['L4', '接口层', 'REST API、WebSocket、CLI', 'FastAPI Server, WebSocket Handler'],
            ['L5', '展示层', 'Web控制台、可视化', 'Frontend SPA (HTML/CSS/JS)'],
        ],
        col_widths=[1.5, 3, 5, 6]
    )

    doc.add_heading('2.2 架构全景图', level=2)
    doc.add_paragraph(
        '┌─────────────────────────────────────────────────────────────────┐\n'
        '│                    L5 展示层 (Web Console)                        │\n'
        '│   Dashboard │ Agent管理 │ 内存管理 │ 遥测数据 │ 自进化中心        │\n'
        '├─────────────────────────────────────────────────────────────────┤\n'
        '│                    L4 接口层 (API Gateway)                        │\n'
        '│   REST API (/api/*)  │  WebSocket (/ws)  │  Static Files         │\n'
        '├─────────────────────────────────────────────────────────────────┤\n'
        '│                    L3 能力服务层                                  │\n'
        '│  ┌──────────┐  ┌──────────────┐  ┌────────────────┐             │\n'
        '│  │ Memory   │  │  Telemetry   │  │   Evolution    │             │\n'
        '│  │ Manager  │  │  Collector   │  │    Engine      │             │\n'
        '│  │ STM/WM/  │  │  Metrics/    │  │ Analyzer/      │             │\n'
        '│  │ LTM      │  │  Storage     │  │ Optimizer/     │             │\n'
        '│  │          │  │              │  │ PromptTuner    │             │\n'
        '│  └──────────┘  └──────────────┘  └────────────────┘             │\n'
        '├─────────────────────────────────────────────────────────────────┤\n'
        '│                    L2 核心运行时层                                │\n'
        '│  ┌──────────────────────────────────────────────────┐           │\n'
        '│  │  AgentHarness (主控制器)                          │           │\n'
        '│  │  ├── BaseAgent (Agent基类/运行时)                 │           │\n'
        '│  │  ├── LifecycleManager (生命周期状态机)            │           │\n'
        '│  │  └── PluginManager (插件管理)                     │           │\n'
        '│  └──────────────────────────────────────────────────┘           │\n'
        '├─────────────────────────────────────────────────────────────────┤\n'
        '│                    L1 基础设施层                                  │\n'
        '│  ConfigManager │ Logger │ FileStorage │ SQLite │ VectorStore     │\n'
        '└─────────────────────────────────────────────────────────────────┘'
    )

    doc.add_heading('2.3 核心设计原则', level=2)
    principles = [
        '异步优先: 所有 I/O 操作采用 async/await 模式，确保高并发下的性能',
        '依赖注入: 各子系统通过构造函数注入，降低耦合度',
        '事件驱动: 生命周期状态变化通过事件机制通知，支持松耦合扩展',
        '可插拔存储: 内存和遥测数据的存储后端可替换（文件/SQLite/向量数据库）',
        '渐进式进化: 自进化采用分析→建议→应用的三阶段模式，避免破坏性变更',
    ]
    for p_text in principles:
        doc.add_paragraph(p_text, style='List Bullet')

    doc.add_page_break()

    # ===== 3. 核心模块设计 =====
    doc.add_heading('3. 核心模块设计', level=1)

    # 3.1 Agent 核心运行时
    doc.add_heading('3.1 Agent 核心运行时', level=2)

    doc.add_heading('3.1.1 模块职责', level=3)
    doc.add_paragraph(
        'Agent 核心运行时负责管理 Agent 的完整生命周期，包括初始化、任务执行、'
        '状态转换和异常处理。核心类包括：'
    )
    add_styled_table(doc,
        ['类名', '职责', '关键方法'],
        [
            ['AgentHarness', '主控制器，协调各子系统', 'initialize(), run_task(), shutdown()'],
            ['BaseAgent', 'Agent基类，定义思考-行动循环', 'think(), act(), observe()'],
            ['LifecycleManager', '生命周期状态机管理', 'transition(), get_state(), on_event()'],
        ],
        col_widths=[3.5, 5.5, 6.5]
    )

    doc.add_heading('3.1.2 生命周期状态机', level=3)
    doc.add_paragraph(
        'Agent 生命周期由以下状态组成，状态转换由 LifecycleManager 管理：\n\n'
        '  CREATED ──→ INITIALIZING ──→ READY ──→ RUNNING ──→ COMPLETED\n'
        '                                    │         │\n'
        '                                    │         ├──→ PAUSED ──→ RUNNING\n'
        '                                    │         │\n'
        '                                    │         └──→ ERROR\n'
        '                                    │\n'
        '                                    └──→ STOPPED\n\n'
        '状态转换规则：\n'
        '• CREATED → INITIALIZING: 调用 initialize() 时触发\n'
        '• INITIALIZING → READY: 所有子系统初始化完成\n'
        '• READY → RUNNING: 接收到任务时触发\n'
        '• RUNNING → PAUSED: 调用 pause() 时触发\n'
        '• PAUSED → RUNNING: 调用 resume() 时触发\n'
        '• RUNNING → COMPLETED: 任务执行完成\n'
        '• RUNNING → ERROR: 发生未捕获异常\n'
        '• 任意状态 → STOPPED: 调用 stop() 时触发'
    )

    doc.add_heading('3.1.3 Think-Act-Observe 循环', level=3)
    doc.add_paragraph(
        'Agent 执行任务时遵循 TAO（Think-Act-Observe）循环模式：\n\n'
        '1. Think（思考）: 基于当前观察和记忆上下文，推理下一步行动\n'
        '2. Act（行动）: 执行推理得出的动作（调用工具/API/生成回复）\n'
        '3. Observe（观察）: 收集行动结果，更新记忆和遥测数据\n\n'
        '循环持续直到任务完成或达到最大迭代次数。'
    )

    doc.add_page_break()

    # 3.2 内存管理子系统
    doc.add_heading('3.2 内存管理子系统', level=2)

    doc.add_heading('3.2.1 模块职责', level=3)
    doc.add_paragraph(
        '内存管理子系统为 Agent 提供多层次的记忆能力，模拟人类认知架构中的'
        '感觉记忆、短期记忆和长期记忆机制。'
    )

    doc.add_heading('3.2.2 三层内存架构', level=3)
    add_styled_table(doc,
        ['内存类型', '容量', '生命周期', '淘汰策略', '存储后端', '用途'],
        [
            ['短期记忆 (STM)', '100条(可配)', 'TTL 1小时', 'LRU', '内存', '最近对话/操作上下文'],
            ['工作记忆 (WM)', '7槽位(可配)', '任务期间', '优先级', '内存', '当前任务活跃信息'],
            ['长期记忆 (LTM)', '无限制', '持久化', '重要性衰减', '文件/SQLite', '知识/经验/偏好'],
        ],
        col_widths=[3, 2.5, 2.5, 2.5, 2.5, 4]
    )

    doc.add_heading('3.2.3 MemoryManager 统一接口', level=3)
    doc.add_paragraph(
        'MemoryManager 作为统一入口，协调三层内存的读写操作：\n\n'
        '• store(content, metadata): 将信息存入适当的内存层\n'
        '• retrieve(query, top_k): 基于相关性从各层检索记忆\n'
        '• consolidate(): 将短期记忆中高重要性的条目整合到长期记忆\n'
        '• get_stats(): 返回各层内存的统计信息\n\n'
        '检索流程：\n'
        '1. 并行查询 STM、WM、LTM\n'
        '2. 基于关键词匹配 + 重要性权重计算相关性分数\n'
        '3. 合并去重后按分数排序返回 Top-K 结果'
    )

    doc.add_heading('3.2.4 记忆整合机制', level=3)
    doc.add_paragraph(
        '记忆整合（Consolidation）是将短期记忆转化为长期记忆的过程：\n\n'
        '触发条件：\n'
        '• 定时触发（默认每30分钟）\n'
        '• STM 利用率超过阈值（默认80%）\n'
        '• 手动调用 consolidate()\n\n'
        '整合规则：\n'
        '• 重要性分数 > 0.7 的条目直接转入 LTM\n'
        '• 被检索次数 > 3 的条目转入 LTM\n'
        '• 重复内容合并，保留最新版本\n'
        '• 转入后从 STM 中移除，释放空间'
    )

    doc.add_page_break()

    # 3.3 遥测数据收集子系统
    doc.add_heading('3.3 遥测数据收集子系统', level=2)

    doc.add_heading('3.3.1 模块职责', level=3)
    doc.add_paragraph(
        '遥测子系统负责自动收集 Agent 运行时的全量行为数据，'
        '为性能分析、问题诊断和自进化提供数据基础。'
    )

    doc.add_heading('3.3.2 指标体系', level=3)
    add_styled_table(doc,
        ['指标类型', '说明', '示例'],
        [
            ['Counter (计数器)', '单调递增的累计值', '任务总数、错误次数、工具调用次数'],
            ['Gauge (仪表)', '可升可降的瞬时值', '内存使用量、活跃会话数'],
            ['Histogram (直方图)', '值的分布统计', '任务耗时分布、Token消耗分布'],
        ],
        col_widths=[3.5, 5, 7]
    )

    doc.add_heading('3.3.3 会话追踪', level=3)
    doc.add_paragraph(
        '每次任务执行创建一个 Session，记录完整的执行链路：\n\n'
        'Session {\n'
        '  session_id: UUID\n'
        '  task: 任务描述\n'
        '  start_time / end_time: 起止时间\n'
        '  duration_ms: 执行耗时\n'
        '  events: [ThinkEvent, ActEvent, ObserveEvent, ...]\n'
        '  metrics: {token_count, tool_calls, errors, ...}\n'
        '  outcome: success | failure | timeout\n'
        '}'
    )

    doc.add_heading('3.3.4 存储策略', level=3)
    doc.add_paragraph(
        '• 默认后端: 文件系统（JSON Lines 格式），按日期分片\n'
        '• 可选后端: SQLite（支持复杂查询）、OpenTelemetry Collector（生产环境）\n'
        '• 数据保留: 默认保留30天，可配置自动清理策略\n'
        '• 采样率: 支持配置采样率以降低存储开销（默认100%全量采集）'
    )

    doc.add_page_break()

    # 3.4 自进化引擎子系统
    doc.add_heading('3.4 自进化引擎子系统', level=2)

    doc.add_heading('3.4.1 模块职责', level=3)
    doc.add_paragraph(
        '自进化引擎基于遥测数据自动分析 Agent 的运行表现，'
        '生成优化建议并可选地自动应用，实现 Agent 的持续改进。'
    )

    doc.add_heading('3.4.2 进化流水线', level=3)
    doc.add_paragraph(
        '自进化遵循三阶段流水线：\n\n'
        '┌──────────┐     ┌──────────┐     ┌──────────┐\n'
        '│  Analyze │ ──→ │ Optimize │ ──→ │  Apply   │\n'
        '│  (分析)  │     │ (优化)   │     │  (应用)  │\n'
        '└──────────┘     └──────────┘     └──────────┘\n\n'
        '阶段一 - 分析 (Analyzer):\n'
        '• 统计任务成功率、平均耗时、错误分布\n'
        '• 识别性能瓶颈（慢操作、高频错误）\n'
        '• 检测行为模式异常\n\n'
        '阶段二 - 优化 (Optimizer + PromptTuner):\n'
        '• 策略优化: 调整超时参数、重试策略、并发度\n'
        '• 提示词调优: 基于成功/失败案例优化系统提示词\n'
        '• 工具选择优化: 调整工具优先级和选择策略\n\n'
        '阶段三 - 应用:\n'
        '• 生成优化建议报告（人工审核模式）\n'
        '• 或自动应用非破坏性变更（自动模式）\n'
        '• 记录变更历史，支持回滚'
    )

    doc.add_heading('3.4.3 分析器输出', level=3)
    add_styled_table(doc,
        ['洞察类型', '说明', '触发条件'],
        [
            ['performance', '性能瓶颈识别', '平均耗时超过阈值'],
            ['reliability', '可靠性问题', '错误率超过5%'],
            ['efficiency', '效率优化机会', '存在冗余操作或重复调用'],
            ['pattern', '行为模式发现', '检测到可固化的成功模式'],
        ],
        col_widths=[3, 5, 6]
    )

    doc.add_page_break()

    # 3.5 Web 控制台子系统
    doc.add_heading('3.5 Web 控制台子系统', level=2)

    doc.add_heading('3.5.1 模块职责', level=3)
    doc.add_paragraph(
        'Web 控制台提供可视化的 Agent 运行时监控和管理界面，'
        '支持实时状态查看、任务提交、内存检索和进化触发等操作。'
    )

    doc.add_heading('3.5.2 技术架构', level=3)
    doc.add_paragraph(
        '• 后端: FastAPI (异步REST API + WebSocket)\n'
        '• 前端: 原生 HTML/CSS/JS 单页应用（无框架依赖）\n'
        '• 通信: REST API（请求-响应）+ WebSocket（实时推送）\n'
        '• 样式: 工业风深色主题，Chakra Petch + IBM Plex 字体组合'
    )

    doc.add_heading('3.5.3 功能模块', level=3)
    add_styled_table(doc,
        ['模块', '功能', '对应API'],
        [
            ['仪表盘', 'Agent状态、统计卡片、实时日志', 'GET /api/status'],
            ['Agent管理', '任务提交、暂停/恢复/停止', 'POST /api/agent/*'],
            ['内存管理', '三层内存监控、检索、整合', 'GET/POST /api/memory/*'],
            ['遥测数据', '会话历史、指标统计', 'GET /api/telemetry/*'],
            ['自进化', '触发分析、查看洞察和建议', 'POST /api/evolution/analyze'],
        ],
        col_widths=[2.5, 6, 6]
    )

    doc.add_page_break()

    # ===== 4. 数据流设计 =====
    doc.add_heading('4. 数据流设计', level=1)

    doc.add_heading('4.1 任务执行数据流', level=2)
    doc.add_paragraph(
        '用户提交任务后的完整数据流：\n\n'
        'User → [Web Console] → POST /api/agent/run\n'
        '  → AgentHarness.run_task()\n'
        '    → LifecycleManager: READY → RUNNING\n'
        '    → TelemetryCollector: 创建 Session\n'
        '    → BaseAgent.think(observation)\n'
        '      → MemoryManager.retrieve(context)\n'
        '      → LLM/规则引擎推理\n'
        '    → BaseAgent.act(action)\n'
        '      → 执行工具/生成回复\n'
        '    → BaseAgent.observe(result)\n'
        '      → MemoryManager.store(result)\n'
        '      → TelemetryCollector: 记录事件\n'
        '    → [循环直到完成]\n'
        '  → LifecycleManager: RUNNING → COMPLETED\n'
        '  → TelemetryCollector: 关闭 Session\n'
        '  → WebSocket: 推送完成通知\n'
        '→ User 收到结果'
    )

    doc.add_heading('4.2 自进化数据流', level=2)
    doc.add_paragraph(
        '进化分析的数据流：\n\n'
        'TelemetryStorage (历史Session数据)\n'
        '  → EvolutionEngine.analyze()\n'
        '    → Analyzer: 统计分析 → 生成 Insights\n'
        '    → Optimizer: 基于Insights → 生成策略建议\n'
        '    → PromptTuner: 基于案例 → 生成提示词优化\n'
        '  → 返回 {insights, suggestions}\n'
        '  → [可选] 自动应用到 Agent 配置'
    )

    doc.add_page_break()

    # ===== 5. 技术选型 =====
    doc.add_heading('5. 技术选型', level=1)

    add_styled_table(doc,
        ['领域', '技术选择', '选型理由'],
        [
            ['编程语言', 'Python 3.10+', 'AI生态丰富，async支持完善'],
            ['异步框架', 'asyncio + anyio', '标准库异步，兼容性强'],
            ['Web框架', 'FastAPI', '高性能异步API，自动文档生成'],
            ['WSGI服务器', 'Uvicorn', 'ASGI服务器，支持WebSocket'],
            ['数据验证', 'Pydantic v2', '高性能数据校验，与FastAPI深度集成'],
            ['配置管理', 'PyYAML', '人类可读的配置格式'],
            ['持久化存储', 'aiosqlite / 文件系统', '轻量级，无外部依赖'],
            ['向量检索', 'FAISS (可选)', '高效的相似度检索'],
            ['可观测性', 'OpenTelemetry (可选)', '行业标准遥测框架'],
            ['前端', '原生 HTML/CSS/JS', '零依赖，加载快速'],
            ['测试', 'pytest + pytest-asyncio', 'Python标准测试框架'],
        ],
        col_widths=[3, 4, 8]
    )

    doc.add_page_break()

    # ===== 6. 接口设计 =====
    doc.add_heading('6. 接口设计', level=1)

    doc.add_heading('6.1 REST API 接口列表', level=2)
    add_styled_table(doc,
        ['方法', '路径', '说明', '请求体', '响应'],
        [
            ['GET', '/api/status', '获取系统状态', '-', '{agent, memory_stats, telemetry_stats}'],
            ['POST', '/api/agent/run', '执行任务', '{task: str}', '{success, result}'],
            ['POST', '/api/agent/pause', '暂停Agent', '-', '{success, state}'],
            ['POST', '/api/agent/resume', '恢复Agent', '-', '{success, state}'],
            ['POST', '/api/agent/stop', '停止Agent', '-', '{success, state}'],
            ['GET', '/api/memory/stats', '内存统计', '-', '{short_term, working, long_term}'],
            ['GET', '/api/memory/search', '记忆检索', '?query=str', '{results: [...]}'],
            ['POST', '/api/memory/consolidate', '记忆整合', '-', '{consolidated, moved}'],
            ['GET', '/api/telemetry/stats', '遥测统计', '-', '{total_sessions, metrics}'],
            ['GET', '/api/telemetry/sessions', '会话列表', '-', '{sessions: [...]}'],
            ['POST', '/api/evolution/analyze', '进化分析', '-', '{insights, suggestions}'],
        ],
        col_widths=[1.5, 4, 2.5, 3, 5]
    )

    doc.add_heading('6.2 WebSocket 接口', level=2)
    doc.add_paragraph(
        '端点: ws://host:port/ws\n\n'
        '服务端推送消息格式：\n'
        '{\n'
        '  "type": "task_complete" | "state_change" | "metric_update",\n'
        '  "task": "任务描述",\n'
        '  "result": "执行结果",\n'
        '  "timestamp": "ISO8601时间戳"\n'
        '}'
    )

    doc.add_heading('6.3 内部编程接口', level=2)
    doc.add_paragraph(
        '核心类接口设计：\n\n'
        'class BaseAgent(ABC):\n'
        '    async def think(self, observation: Any) -> Action\n'
        '    async def act(self, action: Action) -> Result\n'
        '    async def observe(self, result: Result) -> None\n\n'
        'class MemoryManager:\n'
        '    async def store(self, content, metadata=None) -> str\n'
        '    async def retrieve(self, query, top_k=5) -> List[Memory]\n'
        '    async def consolidate(self) -> ConsolidationReport\n\n'
        'class EvolutionEngine:\n'
        '    async def analyze(self) -> EvolutionReport\n'
        '    async def apply_optimizations(self, report) -> None'
    )

    doc.add_page_break()

    # ===== 7. 部署架构 =====
    doc.add_heading('7. 部署架构', level=1)

    doc.add_heading('7.1 单机部署（开发/测试）', level=2)
    doc.add_paragraph(
        '最简部署模式，所有组件运行在单一进程内：\n\n'
        '┌─────────────────────────────────┐\n'
        '│  python -m agent_harness.web    │\n'
        '│  ┌───────────────────────────┐  │\n'
        '│  │  Uvicorn (ASGI Server)    │  │\n'
        '│  │  ├── FastAPI App          │  │\n'
        '│  │  ├── AgentHarness         │  │\n'
        '│  │  ├── MemoryManager        │  │\n'
        '│  │  ├── TelemetryCollector   │  │\n'
        '│  │  └── EvolutionEngine      │  │\n'
        '│  └───────────────────────────┘  │\n'
        '│  数据: ./data/ (文件存储)        │\n'
        '└─────────────────────────────────┘\n\n'
        '启动命令: python -m agent_harness.web.server\n'
        '访问地址: http://localhost:8000'
    )

    doc.add_heading('7.2 生产部署建议', level=2)
    doc.add_paragraph(
        '生产环境建议：\n\n'
        '• 使用 Gunicorn + Uvicorn Workers 提升并发能力\n'
        '• 遥测数据接入 OpenTelemetry Collector → Prometheus/Grafana\n'
        '• 长期记忆存储切换为 PostgreSQL + pgvector\n'
        '• 使用 Redis 作为短期记忆缓存层\n'
        '• 前端静态文件通过 Nginx/CDN 分发\n'
        '• 启用 HTTPS 和身份认证（OAuth2/JWT）'
    )

    doc.add_page_break()

    # ===== 8. 扩展性设计 =====
    doc.add_heading('8. 扩展性设计', level=1)

    doc.add_heading('8.1 插件机制', level=2)
    doc.add_paragraph(
        '框架通过 Plugin 基类提供扩展点：\n\n'
        'class BasePlugin(ABC):\n'
        '    name: str\n'
        '    version: str\n\n'
        '    async def on_install(self, harness) -> None\n'
        '    async def on_uninstall(self) -> None\n'
        '    async def on_task_start(self, task) -> None\n'
        '    async def on_task_end(self, result) -> None\n'
        '    async def on_think(self, observation) -> None\n'
        '    async def on_act(self, action) -> None\n\n'
        '插件可实现：自定义工具注册、记忆预处理、遥测增强、进化策略替换等。'
    )

    doc.add_heading('8.2 存储后端扩展', level=2)
    doc.add_paragraph(
        '存储后端通过抽象接口实现可替换：\n\n'
        '• MemoryStorageBackend: 内存存储抽象\n'
        '  - FileMemoryBackend (默认)\n'
        '  - SQLiteMemoryBackend\n'
        '  - VectorMemoryBackend (FAISS/Chroma)\n\n'
        '• TelemetryStorageBackend: 遥测存储抽象\n'
        '  - FileTelemetryBackend (默认)\n'
        '  - OTLPTelemetryBackend (OpenTelemetry)'
    )

    doc.add_heading('8.3 进化策略扩展', level=2)
    doc.add_paragraph(
        '自进化引擎支持自定义分析器和优化器：\n\n'
        '• 自定义 Analyzer: 继承 BaseAnalyzer，实现 analyze() 方法\n'
        '• 自定义 Optimizer: 继承 BaseOptimizer，实现 optimize() 方法\n'
        '• 自定义 PromptTuner: 实现基于 LLM 的提示词自动优化\n\n'
        '通过配置 evolution.strategies 指定启用的进化策略组合。'
    )

    doc.add_heading('8.4 未来规划', level=2)
    roadmap = [
        '多Agent协作: 支持多个Agent之间的消息传递和任务委派',
        '分布式部署: 支持Agent运行在远程节点，通过RPC通信',
        '可视化编排: 提供拖拽式的Agent工作流编排界面',
        'A/B测试: 支持进化策略的A/B对比验证',
        '安全沙箱: Agent工具执行的安全隔离环境',
        '多模态记忆: 支持图像、音频等多模态记忆的存储和检索',
    ]
    for item in roadmap:
        doc.add_paragraph(item, style='List Bullet')

    # ===== 保存 =====
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, 'Agent_Harness_系统架构设计文档.docx')
    doc.save(output_path)
    print(f'文档已生成: {output_path}')
    return output_path

if __name__ == '__main__':
    build_document()