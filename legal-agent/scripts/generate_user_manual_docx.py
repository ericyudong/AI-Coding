"""Generate legal-agent user manual Word document."""
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

OUTPUT = Path(__file__).resolve().parents[1] / "doc" / "legal-agent用户手册.docx"


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x00, 0x63, 0x64)


def add_table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = val
    doc.add_paragraph()


def add_steps(doc: Document, steps: list[str]) -> None:
    for i, step in enumerate(steps, start=1):
        doc.add_paragraph(f"{i}. {step}", style="List Number")


def build_document() -> Document:
    doc = Document()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("益慧科技 AI+ · 法务\nLegal-Agent 用户手册")
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = RGBColor(0x00, 0x63, 0x64)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run(f"文档版本：1.0　　更新日期：{date.today().isoformat()}").font.size = Pt(10)

    doc.add_paragraph(
        "本文档面向企业法务、合规及业务人员，介绍 Legal-Agent 智能法务平台的功能模块、"
        "日常操作步骤与使用注意事项，帮助您快速上手并高效完成法务工作。"
    )

    # ── 一、产品简介 ──
    add_heading(doc, "一、产品简介", 1)
    doc.add_paragraph(
        "益慧科技 AI+ · 法务（Legal-Agent）是一套面向企业法务与合规团队的智能化工作平台。"
        "平台整合法律检索、合同全生命周期管理、合同审核与起草、专业领域问答等能力，"
        "采用 AI 大模型与知识库相结合的技术路线，在保障数据安全的前提下提供智能分析与辅助决策。"
    )
    doc.add_paragraph(
        "系统分为两大界面："
        "① 法务门户——提供法律检索、合同审核/起草/比对、专题问答等 AI 工具；"
        "② 合同管理系统（CMS）——提供合同台账、导入、检索、版本对比与基于正文的 AI 问答。"
    )

    add_heading(doc, "1.1 四大核心模块", 2)
    add_table(
        doc,
        ["模块", "主要功能"],
        [
            ["检索 AI", "综合分析、法规查询、类案检索、行政处罚检索、专业解读"],
            ["合同 AI", "合同台账、导入识别、多模态检索、版本对比、审核、起草、文件比对"],
            ["诉讼 AI", "诉讼策略、诉讼文书、要素式文书等（当前入口跳转至法律检索）"],
            ["问答 AI", "劳动法、金融合规、企业出海等专业多轮对话"],
        ],
    )

    # ── 二、登录与账号 ──
    add_heading(doc, "二、登录与账号", 1)
    doc.add_paragraph("访问系统后，若未登录将自动跳转到登录页。")
    add_steps(
        doc,
        [
            "在登录页输入用户名和密码，点击「登录」。",
            "登录成功后进入首页；若此前访问了其他页面，将自动返回原目标页。",
            "登录状态默认保持约 8 小时，过期后需重新登录。",
            "点击首页右上角「退出」，或功能页顶栏用户菜单中的「退出」可安全登出。",
        ],
    )
    doc.add_paragraph(
        "说明：各用户只能查看和管理自己账号下的合同、审核记录与对话数据；"
        "首次使用请联系管理员获取账号。演示环境可使用 admin / admin123。"
    )

    # ── 三、首页与导航 ──
    add_heading(doc, "三、首页与导航", 1)
    doc.add_paragraph("登录后进入首页，主要区域包括：")
    doc.add_paragraph("搜索框：选择「法律法规 / 裁判文书 / 行政处罚」，输入关键词后搜索或点击「益慧AI+」进入智能检索。", style="List Bullet")
    doc.add_paragraph("快捷入口：法律法规、裁判文书、行政处罚、实务指南、文书模板、专题聚焦等。", style="List Bullet")
    doc.add_paragraph("四大 AI 模块卡片：检索 AI、合同 AI（进入 CMS）、诉讼 AI、问答 AI。", style="List Bullet")
    doc.add_paragraph("资讯区：益慧速递、益慧精选、益慧模块等资讯展示。", style="List Bullet")
    doc.add_paragraph(
        "左侧导航栏按功能分组：AI 检索、AI 合同、AI 诉讼、AI 问答。"
        "顶部菜单提供产品模块切换与「帮助 → 用户手册 / 联系益慧」。"
    )

    # ── 四、法律检索 ──
    add_heading(doc, "四、法律检索（检索 AI）", 1)
    doc.add_paragraph("入口：首页搜索框、左侧「AI 检索」子菜单，或顶部产品菜单「检索 AI」。")
    add_heading(doc, "4.1 检索类型", 2)
    add_table(
        doc,
        ["类型", "适用场景"],
        [
            ["综合分析", "对法律问题进行多维度综合分析，给出结论与实务建议"],
            ["法规查询", "检索并解读相关法律法规条文"],
            ["类案检索", "查找类似司法裁判观点与案例"],
            ["行政处罚", "分析行政处罚规定与相关案例"],
            ["专业解读", "对特定法律问题进行深度专业解读"],
        ],
    )
    add_heading(doc, "4.2 操作步骤", 2)
    add_steps(
        doc,
        [
            "选择检索类型（如「类案检索」）。",
            "在输入框中描述法律问题，可按 Ctrl+Enter 快速提交。",
            "可选点击「问题优化」，系统自动补充分析维度提示。",
            "等待 AI 返回分析结果与参考引用列表。",
            "可点击「试一试」示例问题快速体验。",
        ],
    )

    # ── 五、合同 AI 工具 ──
    add_heading(doc, "五、合同 AI 工具（法务门户）", 1)
    doc.add_paragraph("入口：左侧「AI 合同」子菜单。")

    add_heading(doc, "5.1 合同审核", 2)
    doc.add_paragraph("对上传的合同文件进行 AI 智能审核，生成结构化审核报告。")
    add_table(
        doc,
        ["项目", "说明"],
        [
            ["支持格式", "doc、docx、pdf"],
            ["文件大小", "最大 50 MB"],
            ["审核模式", "清单审核（7 大维度逐项分析）；参照审核"],
            ["审核维度", "主体资质、权利义务、付款交付、违约责任、保密知识产权、争议解决、合规风险"],
        ],
    )
    add_steps(
        doc,
        [
            "进入「合同审核」页面，选择审核模式。",
            "拖拽或点击上传合同文件；也可加载示例合同体验。",
            "查看系统解析的字数与警告信息（如扫描件 OCR 提示）。",
            "点击「进入审核」，等待 AI 生成审核报告。",
            "可复制报告内容；在「历史记录」中查看以往审核（最近 20 条）。",
        ],
    )

    add_heading(doc, "5.2 合同起草", 2)
    doc.add_paragraph("根据业务需求 AI 生成完整合同或单个条款。")
    add_steps(
        doc,
        [
            "进入「合同起草」页面。",
            "选择「生成合同」或「生成条款」。",
            "填写合同目的（必填）、我方立场、其他补充信息。",
            "选择起草风格：简明居中、详细严谨、偏向甲方、偏向乙方。",
            "点击发送，查看生成结果并复制使用；可在起草历史中回顾。",
        ],
    )

    add_heading(doc, "5.3 合同比对（文件比对）", 2)
    doc.add_paragraph(
        "直接上传任意两个合同文件进行差异对比，无需先入库。"
        "适用于临时比对两份文件的修订内容。"
    )
    add_steps(
        doc,
        [
            "进入「合同比对」页面。",
            "分别上传「原始合同」和「修订合同」。",
            "点击「开始比对」。",
            "查看变更摘要（总数/风险/新增/删除）、逐条款左右对比及 AI 风险标注。",
        ],
    )

    # ── 六、问答 AI ──
    add_heading(doc, "六、问答 AI", 1)
    add_table(
        doc,
        ["专题", "入口路径", "说明"],
        [
            ["劳动法", "/qa/labor", "劳动法专业多轮对话，支持示例问题与真实数据溯源"],
            ["金融合规", "/qa/financial", "金融合规领域专业咨询"],
            ["企业出海", "/qa/overseas", "跨境合规与企业出海相关问答"],
        ],
    )
    add_steps(
        doc,
        [
            "从左侧「AI 问答」选择专题进入。",
            "点击示例问题卡片可一键提问，或在输入框自行描述问题。",
            "按 Ctrl+Enter 发送，与 AI 进行多轮对话。",
        ],
    )

    # ── 七、合同管理系统 CMS ──
    add_heading(doc, "七、合同管理系统（CMS）", 1)
    doc.add_paragraph(
        "入口：首页「合同 AI」卡片、顶部产品菜单「合同 AI」，或直接访问 /cms。"
        "CMS 采用独立导航布局，提供合同全生命周期管理能力。"
    )

    add_heading(doc, "7.1 台账管理", 2)
    doc.add_paragraph("路径：/cms/ledger")
    doc.add_paragraph("功能概览：")
    doc.add_paragraph("统计卡片：合同总数、履行中、即将到期（30 天内）、高风险。", style="List Bullet")
    doc.add_paragraph("列表筛选：按关键词（名称/编号/签约主体）、状态（履行中/待签署/已到期/已归档等）过滤。", style="List Bullet")
    doc.add_paragraph("视图切换：表格视图 / 卡片视图。", style="List Bullet")
    doc.add_paragraph("批量操作：勾选多条记录后批量修改状态。", style="List Bullet")
    doc.add_paragraph("新建合同、导出 CSV、删除合同。", style="List Bullet")
    add_table(
        doc,
        ["字段", "可选值"],
        [
            ["合同类型", "采购、销售、租赁、劳务、保密协议、技术开发、其他"],
            ["合同状态", "待签署、履行中、已到期、已归档、已终止"],
        ],
    )

    add_heading(doc, "7.2 合同导入", 2)
    doc.add_paragraph("路径：/cms/import")
    doc.add_paragraph(
        "支持上传 PDF、Word（doc/docx）、Excel（xlsx）、JPG、PNG，单文件最大 50 MB。"
        "系统自动完成格式预处理、OCR 文字识别（扫描件/图片）与 AI 结构化字段提取。"
    )
    doc.add_paragraph(
        "AI 自动提取字段：合同名称、编号、类型、甲乙双方、金额、签署/到期日期、关键条款。"
    )
    add_steps(
        doc,
        [
            "进入「合同导入」，拖拽或点击上传文件。",
            "等待 OCR 识别与 AI 结构化提取完成。",
            "核对 AI 提取的字段与关键条款，必要时手动修正。",
            "选择入库方式：「新建合同台账」或「关联已有合同（追加新版本）」。",
            "若关联已有合同，系统会智能推荐名称/主体相似的合同；填写版本说明后确认入库。",
            "入库成功后自动跳转至合同详情页。",
        ],
    )
    doc.add_paragraph(
        "提示：扫描件 PDF 或图片合同依赖本地 OCR 识别，识别效果与扫描清晰度有关；"
        "若识别不完整，建议上传 Word 版或提高扫描质量。"
    )

    add_heading(doc, "7.3 合同检索", 2)
    doc.add_paragraph("路径：/cms/search")
    add_table(
        doc,
        ["检索模式", "说明"],
        [
            ["混合检索", "默认模式，综合多种检索方式"],
            ["语义检索", "基于合同语义相似度搜索"],
            ["关键词", "传统关键词匹配"],
            ["字段检索", "按结构化字段条件过滤"],
            ["正则检索", "使用正则表达式匹配"],
            ["自然语言", "用自然语言描述搜索意图"],
        ],
    )
    doc.add_paragraph("高级搜索：可组合金额、状态、类型、甲乙方、编号等多字段条件，并保存/加载搜索预设。")
    doc.add_paragraph("其他：搜索历史（浏览器本地保存）、智能标签云（点击即搜索）、AI 搜索建议。")
    add_steps(
        doc,
        [
            "输入自然语言或关键词，选择检索模式。",
            "可选展开「高级搜索」添加字段条件。",
            "点击搜索结果条目进入合同详情。",
        ],
    )

    add_heading(doc, "7.4 版本对比", 2)
    doc.add_paragraph(
        "路径：/cms/compare。"
        "针对已入库合同的多个历史版本进行 AI 差异对比（与「合同比对」文件上传工具不同）。"
    )
    add_steps(
        doc,
        [
            "进入「版本对比」，搜索并选择目标合同。",
            "选择左侧（旧版本）和右侧（新版本），需至少 2 个版本。",
            "点击「开始对比」，查看变更摘要、风险变更数、逐条款 diff 与 AI 标注。",
        ],
    )
    doc.add_paragraph(
        "快捷方式：在合同详情页「版本历史」Tab 中，点击某历史版本的「对比」按钮，"
        "系统自动跳转版本对比页并预填版本。"
    )

    add_heading(doc, "7.5 合同详情与 AI 问答", 2)
    doc.add_paragraph("路径：/cms/contracts/:id（从台账、检索或导入完成后进入）")
    add_table(
        doc,
        ["Tab", "内容"],
        [
            ["基本信息", "状态、类型、金额、甲乙双方、日期、负责人、风险等级、AI 标签"],
            ["AI 摘要", "简短 / 详细 / 风险 / 时间线 四种摘要"],
            ["版本历史", "版本列表，可跳转版本对比"],
            ["原文预览", "合同全文内容"],
        ],
    )
    doc.add_paragraph("右侧「AI 问答助手」：基于合同正文的 RAG 检索增强问答。")
    doc.add_paragraph("输入问题（如「违约金是多少？」「合同何时到期？」「付款条件是什么？」），系统返回答案、引用片段与置信度。", style="List Bullet")

    # ── 八、两种比对功能对比 ──
    add_heading(doc, "八、两种「比对」功能说明", 1)
    add_table(
        doc,
        ["对比项", "合同比对（文件比对）", "版本对比（CMS）"],
        [
            ["入口", "侧边栏「AI 合同 → 合同比对」", "CMS「版本对比」"],
            ["输入", "任意两个文件（原始版 + 修订版）", "已入库合同的两个历史版本"],
            ["适用场景", "临时比对两份文件，无需入库", "追踪合同修订历史、版本管理"],
            ["路径", "/contract/compare", "/cms/compare"],
        ],
    )

    # ── 九、文件与 AI 使用须知 ──
    add_heading(doc, "九、文件上传与 AI 使用须知", 1)
    add_table(
        doc,
        ["场景", "支持格式", "大小限制", "备注"],
        [
            ["合同审核 / 文件比对", "doc、docx、pdf", "50 MB", "扫描件 PDF 需 OCR 支持"],
            ["CMS 合同导入", "PDF、doc、docx、xlsx、jpg、png", "50 MB", "支持图片 OCR"],
        ],
    )
    doc.add_paragraph("AI 能力说明：", style="List Bullet")
    doc.add_paragraph("AI 回答质量取决于企业是否配置大模型 API；未配置时系统以演示模式运行，返回示例性内容。", style="List Bullet")
    doc.add_paragraph("合同审核、起草、检索、问答、摘要、版本对比等功能均标注「益慧AI+」或「Powered by AI」。", style="List Bullet")
    doc.add_paragraph("CMS 合同问答（RAG）基于合同正文向量检索，回答附带引用片段与置信度。", style="List Bullet")
    doc.add_paragraph("扫描件识别使用本地 OCR（RapidOCR），无需云端 API，识别效果受扫描清晰度影响。", style="List Bullet")

    # ── 十、常见问题 ──
    add_heading(doc, "十、常见问题（FAQ）", 1)
    faqs = [
        ("AI 功能需要额外配置吗？", "管理员在服务端配置大模型 API 后即可启用完整 AI 能力；未配置时部分功能以演示模式运行。"),
        ("合同数据存储在哪里？", "合同数据存储在企业部署的服务端数据库中，可按企业安全策略进行备份与权限管理。"),
        ("扫描件 PDF 无法识别怎么办？", "确认服务端已启用本地 OCR；尝试提高扫描清晰度，或上传 Word 版合同。"),
        ("两个「比对」功能有什么区别？", "「合同比对」上传任意两个文件；「版本对比」对比已入库合同的历史版本。详见第八章。"),
        ("搜索预设和历史会丢失吗？", "搜索预设保存在服务端；搜索历史保存在浏览器本地，换设备或清缓存后会丢失。"),
        ("如何获取技术支持？", "通过系统顶部「帮助 → 联系益慧」获取官方联系方式。"),
    ]
    for q, a in faqs:
        p = doc.add_paragraph()
        p.add_run(f"Q：{q}").bold = True
        doc.add_paragraph(f"A：{a}")

    # ── 十一、功能限制说明 ──
    add_heading(doc, "十一、当前功能限制", 1)
    doc.add_paragraph("诉讼 AI：侧边栏有入口，当前跳转至法律检索页，尚无独立诉讼文书生成页面。", style="List Bullet")
    doc.add_paragraph("法律检索历史：「历史记录」链接暂无独立历史页面。", style="List Bullet")
    doc.add_paragraph("问答历史：后端保存会话，前端当前页不展示历史对话列表。", style="List Bullet")
    doc.add_paragraph("用户权限：暂无多角色分级，所有登录用户权限相同，数据按账号隔离。", style="List Bullet")
    doc.add_paragraph("右侧浮动工具栏（推送、客服、反馈等）为 UI 占位，暂不可用。", style="List Bullet")

    doc.add_paragraph()
    footer = doc.add_paragraph("—— 文档结束 ——")
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    copy = doc.add_paragraph("© 益慧科技有限公司 · 益慧科技 AI+ · 法务")
    copy.alignment = WD_ALIGN_PARAGRAPH.CENTER

    return doc


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = build_document()
    doc.save(OUTPUT)
    print(f"已生成: {OUTPUT}")


if __name__ == "__main__":
    main()
