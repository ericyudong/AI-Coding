"""Generate legal-agent algorithms & models summary Word document."""
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

OUTPUT = Path(__file__).resolve().parents[1] / "legal-agent算法与模型总结.docx"


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x1E, 0x1B, 0x4B)


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


def build_document() -> Document:
    doc = Document()
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("益慧科技 Legal-Agent 项目\n算法与模型总结")
    run.bold = True
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor(0x1E, 0x1B, 0x4B)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run(f"文档生成日期：{date.today().isoformat()}").font.size = Pt(10)

    doc.add_paragraph(
        "本文档基于 legal-agent 代码库（backend/app/services 等模块）梳理，"
        "汇总当前系统实际使用的 AI 模型、检索算法、文本处理与业务规则引擎。"
    )

    add_heading(doc, "一、项目概览", 1)
    doc.add_paragraph(
        "Legal-Agent 是面向企业法务场景的智能合同与法律知识平台，"
        "前端采用 Vue 3 + TypeScript，后端采用 FastAPI + SQLAlchemy + SQLite。"
        "AI 能力通过 OpenAI 兼容 API 接入，向量检索使用 Qdrant 本地存储；"
        "扫描件 PDF 使用 RapidOCR 本地 OCR 识别，无需云端服务；"
        "未配置 API Key 或向量服务不可用时，系统自动降级为规则引擎 + 演示模式。"
    )

    add_heading(doc, "二、AI 模型清单", 1)

    add_heading(doc, "2.1 大语言模型（LLM）", 2)
    add_table(
        doc,
        ["配置项", "默认值 / 示例", "用途"],
        [
            ["OPENAI_MODEL", "gpt-4o-mini（可配置为 deepseek-v4 等）", "法律检索、智能问答、合同审核/起草、RAG 问答、版本差异解读、NL 检索解析、字段抽取、摘要生成"],
            ["OPENAI_BASE_URL", "OpenAI 兼容端点", "统一 Chat Completions API 调用"],
            ["调用方式", "httpx 异步 HTTP", "temperature 0.1~0.3，按任务区分"],
        ],
    )

    add_heading(doc, "2.2 向量嵌入模型（Embedding）", 2)
    add_table(
        doc,
        ["配置项", "默认值 / 示例", "用途"],
        [
            ["EMBEDDING_MODEL", "text-embedding-3-small / bge-m3", "合同分块向量化、语义检索、RAG 召回"],
            ["EMBEDDING_DIMENSIONS", "1024", "与 Qdrant 集合维度一致"],
            ["EMBEDDING_BATCH_SIZE", "32", "批量嵌入，降低 API 调用次数"],
        ],
    )

    add_heading(doc, "2.3 向量数据库", 2)
    doc.add_paragraph(
        "Qdrant（本地文件模式，路径 data/qdrant），集合名 contract_chunks，"
        "距离度量：余弦相似度（Cosine Distance）。"
        "每条向量携带 user_id、contract_id、chunk_index、section_title、content 等 payload。"
    )

    add_heading(doc, "2.4 本地 OCR 模型（扫描件 PDF）", 2)
    add_table(
        doc,
        ["组件", "说明"],
        [
            ["RapidOCR（rapidocr-onnxruntime）", "本地 ONNX 推理 OCR 引擎，无需云端 API，支持中英文识别"],
            ["PyMuPDF（fitz）", "将 PDF 页面按 DPI 渲染为 PNG 位图，供 OCR 输入"],
            ["pypdf", "优先提取 PDF 文字层；文字不足时再触发 OCR"],
            ["python-docx", "Word 合同正文解析（段落 + 表格）"],
        ],
    )
    doc.add_paragraph(
        "OCR 为纯本地推理，不依赖 OPENAI_API_KEY；"
        "识别结果写入合同正文后，供分块索引、RAG 问答、字段抽取、版本对比等下游流程使用。"
    )

    add_heading(doc, "2.5 其他非 AI 组件", 2)
    add_table(
        doc,
        ["组件", "说明"],
        [
            ["JWT（HS256）", "用户登录鉴权，python-jose"],
            ["bcrypt", "密码哈希存储"],
        ],
    )

    add_heading(doc, "三、核心算法与处理流程", 1)

    add_heading(doc, "3.1 RAG（检索增强生成）", 2)
    doc.add_paragraph("应用于：合同详情页 AI 问答助手。", style="List Bullet")
    doc.add_paragraph("流程：合同正文分块 → 嵌入向量 → Qdrant 索引 → 用户提问向量化 → Top-K 召回 → LLM 基于片段回答。", style="List Bullet")
    doc.add_paragraph("降级策略：① 向量不可用时按关键词/同义词在分块内打分召回；② LLM 不可用时使用规则问答引擎（金额、付款、违约等）；③ 再降级为关键词模板回答。", style="List Bullet")
    doc.add_paragraph("关键参数：chunk_size=800，chunk_overlap=100，rag_top_k=5，rag_max_context_chars=6000。", style="List Bullet")

    add_heading(doc, "3.2 文档解析与本地 OCR", 2)
    doc.add_paragraph("应用于：合同导入、上传解析、正文索引前的文本提取。", style="List Bullet")
    doc.add_paragraph(
        "PDF 解析流程：pypdf 逐页 extract_text → 统计每页字符数 → "
        "单页文字 < parser_ocr_min_page_chars（默认 20）则标记为扫描页 → "
        "PyMuPDF 按 DPI 渲染 PNG → RapidOCR 识别 → 按行框坐标排序合并文本 → "
        "与原有文字层拼接为 page_texts → 输出 ParsedDocument。",
        style="List Bullet",
    )
    doc.add_paragraph(
        "DOCX 解析：python-docx 提取段落与表格单元格，不涉及 OCR。",
        style="List Bullet",
    )
    doc.add_paragraph(
        "OCR 行排序算法：取每个识别框 quad 的最小 y、最小 x 坐标，"
        "先按 y（四舍五入到 0.1）再按 x 排序，还原阅读顺序。",
        style="List Bullet",
    )
    doc.add_paragraph(
        "降级与提示：依赖缺失时在 warnings 中说明；"
        "OCR 关闭且全文无文字层时提示启用 PARSER_OCR_ENABLED；"
        "识别失败时提示检查扫描清晰度。",
        style="List Bullet",
    )
    add_table(
        doc,
        ["配置项", "默认值", "说明"],
        [
            ["PARSER_OCR_ENABLED", "true", "是否启用本地 OCR"],
            ["PARSER_OCR_DPI", "200", "页面渲染分辨率，越高越准但越慢"],
            ["PARSER_OCR_MIN_PAGE_CHARS", "20", "低于此字数才对该页 OCR"],
            ["PARSER_OCR_MIN_SCORE", "0.5", "OCR 置信度阈值，低于此分数的行丢弃"],
            ["PARSER_MAX_PAGES", "200", "单文件最大解析页数"],
        ],
    )

    add_heading(doc, "3.3 文本分块（Chunking）", 2)
    doc.add_paragraph(
        "优先按「第X条」条款标题切分（正则：第[一二三四五六七八九十百零\\d]+条）；"
        "条款不足时按段落聚合，超长段落采用滑动窗口（chunk_size - overlap 步进）。"
        "用于：合同索引、RAG 召回、长合同分块审核。"
    )

    add_heading(doc, "3.4 多模态合同检索（Hybrid Search）", 2)
    add_table(
        doc,
        ["模式", "算法说明"],
        [
            ["keyword", "SQL ILIKE 多字段匹配 + 正文关键词检索"],
            ["semantic", "Query Embedding + Qdrant 余弦近邻，按 contract 聚合最高分"],
            ["field", "结构化字段过滤（金额、状态、类型、甲乙方等）"],
            ["regex", "正则匹配编号/名称/正文"],
            ["natural", "LLM 将自然语言解析为 filters + 关键词，再转 hybrid"],
            ["hybrid", "关键词 + 语义 + 字段三路召回，Reciprocal Rank 风格加权融合（权重 1.0 / 1.2 / 1.1）"],
        ],
    )

    add_heading(doc, "3.5 合同版本 / 文件对比（Diff）", 2)
    doc.add_paragraph("基于 Python difflib.SequenceMatcher 的差异检测。", style="List Bullet")
    doc.add_paragraph("策略一（条款级）：按「第X条」标题对齐，比较 add / remove / modified。", style="List Bullet")
    doc.add_paragraph("策略二（行级）：get_opcodes 逐行 diff，适用于结构不一致的全文对比。", style="List Bullet")
    doc.add_paragraph("条款标题重叠率 < 25% 时自动切换行级 diff，避免误报。", style="List Bullet")
    doc.add_paragraph("变更明细：逐行提取「旧→新」描述；长文本仅展示差异行（focused diff snippets）。", style="List Bullet")
    doc.add_paragraph("LLM interpret_diff：对每条变更生成语义说明与总体风险摘要（无 LLM 时用规则 mock）。", style="List Bullet")

    add_heading(doc, "3.6 合同字段抽取", 2)
    doc.add_paragraph("LLM JSON 抽取：name、contract_type、party_a/b、amount、日期、key_clauses 等。", style="List Bullet")
    doc.add_paragraph("规则引擎兜底：正则匹配甲乙方、金额、日期、合同类型关键词、关键条款探测。", style="List Bullet")
    doc.add_paragraph("应用于：合同导入、台账字段预填。", style="List Bullet")

    add_heading(doc, "3.7 合同审核与起草", 2)
    doc.add_paragraph("审核：checklist / reference 两种 Prompt 模式；超长合同按 review_chunk_size=12000 分块审核后合并。", style="List Bullet")
    doc.add_paragraph("起草：按 purpose、position、style 等参数生成合同/条款 Markdown。", style="List Bullet")

    add_heading(doc, "3.8 AI 摘要生成", 2)
    doc.add_paragraph("详细摘要：优先 LLM 生成 8~12 条要点；无 LLM 时从正文正则抽取（金额、服务范围、付款、违约、争议等）。", style="List Bullet")
    doc.add_paragraph("风险摘要 / 时间线：基于 risk_level 与正文规则抽取。", style="List Bullet")

    add_heading(doc, "3.9 导入合同关联匹配", 2)
    doc.add_paragraph("名称相似度：difflib.SequenceMatcher ratio，含子串加权。", style="List Bullet")
    doc.add_paragraph("主体匹配：甲乙方字段归一化后双向比对（支持甲乙互换）。", style="List Bullet")
    doc.add_paragraph("综合打分：名称相似度 × 70 + 主体一致 × 30，用于推荐关联已有合同。", style="List Bullet")

    add_heading(doc, "3.10 规则问答引擎（非 LLM）", 2)
    doc.add_paragraph(
        "针对「合同金额、付款、违约金、到期、续签、保密、争议、甲乙方」等主题，"
        "通过同义词扩展 + 正文片段定位 + _parse_amount_from_text 解析金额，"
        "在 RAG/LLM 不可用时仍可从正文回答结构化问题。"
    )

    add_heading(doc, "四、按功能模块映射", 1)
    add_table(
        doc,
        ["功能模块", "主要模型", "主要算法"],
        [
            ["法律 AI 检索", "LLM", "Prompt 模板（综合/法规/类案/处罚/解读）+ Mock 降级"],
            ["劳动法 / 合规问答", "LLM", "模块化 System Prompt + Mock"],
            ["合同 CMS 问答", "Embedding + LLM + 规则引擎", "RAG Top-K + 同义词召回 + 结构化问答"],
            ["合同语义搜索", "Embedding", "Qdrant 余弦检索 + Hybrid 融合"],
            ["合同导入 / 文档解析", "RapidOCR + LLM + 规则", "pypdf 文字层 + 扫描页本地 OCR + 字段 JSON 抽取 + 正则兜底"],
            ["版本对比 / 文件比对", "LLM（可选）", "SequenceMatcher 条款/行 diff + 变更明细"],
            ["合同审核", "LLM", "分块审核 + 报告合并"],
            ["合同起草", "LLM", "条件生成 Prompt"],
            ["登录鉴权", "—", "bcrypt + JWT HS256"],
        ],
    )

    add_heading(doc, "五、配置与降级说明", 1)
    doc.add_paragraph("所有 LLM/Embedding 能力均依赖 backend/.env 中的 OPENAI_API_KEY 与 OPENAI_BASE_URL。", style="List Bullet")
    doc.add_paragraph("Embedding API 失败时：分块仍写入 SQLite（index_status=no_embedding），RAG 改关键词召回。", style="List Bullet")
    doc.add_paragraph("Qdrant 不可用时：语义检索与向量 RAG 降级为 SQL/关键词方案。", style="List Bullet")
    doc.add_paragraph("本地 OCR（RapidOCR + PyMuPDF）不依赖 API Key，默认开启（PARSER_OCR_ENABLED=true）；依赖缺失或识别失败时在解析 warnings 中提示。", style="List Bullet")
    doc.add_paragraph("扫描件识别效果受 DPI、清晰度影响，可通过 PARSER_OCR_DPI（建议 200~300）调节精度与速度。", style="List Bullet")

    add_heading(doc, "六、主要源码位置", 1)
    add_table(
        doc,
        ["文件", "职责"],
        [
            ["backend/app/services/llm_service.py", "LLM 统一调用与各业务 Prompt"],
            ["backend/app/services/embedding_service.py", "Embedding API"],
            ["backend/app/services/vector_store.py", "Qdrant 封装"],
            ["backend/app/services/text_chunker.py", "合同分块"],
            ["backend/app/services/index_service.py", "索引流水线"],
            ["backend/app/services/retrieval_service.py", "RAG/语义召回"],
            ["backend/app/services/rag_service.py", "RAG 问答编排"],
            ["backend/app/services/search_service.py", "多模态检索与融合"],
            ["backend/app/services/diff_service.py", "版本 diff"],
            ["backend/app/services/compare_service.py", "对比 + LLM 解读"],
            ["backend/app/services/document_parser.py", "PDF/DOCX 统一解析，扫描页触发 OCR"],
            ["backend/app/services/document_ocr.py", "RapidOCR 引擎、PDF 渲染与按页识别"],
            ["backend/app/services/field_extractor.py", "字段抽取规则"],
            ["backend/app/services/cms_service.py", "摘要/问答规则/导入匹配"],
            ["backend/app/core/config.py", "模型与算法参数配置"],
        ],
    )

    doc.add_paragraph()
    p = doc.add_paragraph("—— 文档结束 ——")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    return doc


def main() -> None:
    doc = build_document()
    doc.save(OUTPUT)
    print(f"已生成: {OUTPUT}")


if __name__ == "__main__":
    main()
