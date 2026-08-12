"""Generate legal-agent architecture design Word document."""
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

OUTPUT = Path(__file__).resolve().parents[1] / "doc" / "legal-agent架构设计.docx"


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


def add_flow(doc: Document, lines: list[str]) -> None:
    for line in lines:
        doc.add_paragraph(line, style="List Bullet")


def build_document() -> Document:
    doc = Document()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("益慧科技 Legal-Agent\n系统架构设计文档")
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = RGBColor(0x1E, 0x1B, 0x4B)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run(f"文档版本：1.0　　更新日期：{date.today().isoformat()}").font.size = Pt(10)

    doc.add_paragraph(
        "本文档描述 Legal-Agent 智能法务平台的系统架构、技术选型、模块划分、"
        "核心数据流、部署方式与安全机制，供开发、运维与架构评审使用。"
    )

    # ── 一、架构概览 ──
    add_heading(doc, "一、系统架构概览", 1)
    doc.add_paragraph(
        "Legal-Agent 采用前后端分离的单体后端架构。"
        "前端为 Vue 3 单页应用（SPA），后端为 FastAPI 应用；"
        "生产环境可将前端构建产物挂载至 FastAPI，由同一端口统一对外服务。"
    )
    doc.add_paragraph("系统分层结构如下：")
    add_table(
        doc,
        ["层次", "组件", "说明"],
        [
            ["表现层", "Vue 3 SPA", "法务门户 + 合同管理系统（CMS）两套界面"],
            ["接入层", "FastAPI + Uvicorn", "REST API，统一前缀 /api/v1，JWT 鉴权"],
            ["业务层", "services/", "20+ 业务服务模块，编排 AI、检索、解析等逻辑"],
            ["持久层", "SQLAlchemy ORM", "异步 SQLite，用户/合同/会话等关系数据"],
            ["向量层", "Qdrant 本地嵌入", "合同分块向量索引，余弦相似度检索"],
            ["文件层", "backend/data/", "导入文件、审核上传、向量库目录"],
            ["外部 AI", "OpenAI 兼容 API", "LLM 对话与 Embedding 向量化（可选）"],
            ["本地 OCR", "RapidOCR + PyMuPDF", "扫描件 PDF 本地文字识别"],
        ],
    )
    doc.add_paragraph("逻辑架构示意：")
    add_flow(
        doc,
        [
            "浏览器（Vue SPA）──HTTP/JSON──▶ FastAPI（8010）",
            "FastAPI ──▶ SQLite（legal_agent.db）── 关系型业务数据",
            "FastAPI ──▶ Qdrant（data/qdrant）── 向量检索",
            "FastAPI ──▶ OpenAI 兼容 API ── LLM / Embedding",
            "FastAPI ──▶ RapidOCR（本地）── 扫描件 OCR",
            "FastAPI ──▶ 本地文件系统（data/cms_imports、data/contracts）",
        ],
    )
    doc.add_paragraph("功能域划分：")
    add_table(
        doc,
        ["功能域", "主要页面/模块", "核心能力"],
        [
            ["法务门户", "首页、法律检索、问答 AI", "法律问题分析、专题多轮对话"],
            ["合同工具", "合同审核、起草、文件比对", "上传解析、AI 审核/生成/双文件 diff"],
            ["合同 CMS", "台账、导入、检索、版本对比、详情", "全生命周期管理、RAG 问答、向量检索"],
        ],
    )

    # ── 二、技术栈 ──
    add_heading(doc, "二、技术栈", 1)

    add_heading(doc, "2.1 前端", 2)
    add_table(
        doc,
        ["技术", "版本/说明", "用途"],
        [
            ["Vue 3", "^3.4", "响应式 UI 框架"],
            ["TypeScript", "^5.3", "类型安全"],
            ["Vite", "^5.0", "构建与开发服务器（5173）"],
            ["Vue Router", "^4.2", "路由与鉴权守卫"],
            ["Pinia", "^2.1", "状态管理（auth store）"],
            ["Element Plus", "^2.5", "UI 组件库"],
            ["Axios", "^1.6", "HTTP 客户端，Bearer Token 注入"],
        ],
    )

    add_heading(doc, "2.2 后端", 2)
    add_table(
        doc,
        ["技术", "说明", "用途"],
        [
            ["FastAPI", ">=0.109", "Web 框架、OpenAPI 文档"],
            ["Uvicorn", ">=0.27", "ASGI 服务器"],
            ["SQLAlchemy 2.x", "asyncio + aiosqlite", "异步 ORM"],
            ["Pydantic v2", "—", "请求/响应 Schema 校验"],
            ["python-jose", "—", "JWT 签发与验证"],
            ["bcrypt", "—", "密码哈希"],
            ["httpx", "—", "异步调用 LLM/Embedding API"],
            ["aiofiles", "—", "异步文件读写"],
        ],
    )

    add_heading(doc, "2.3 AI 与文档处理", 2)
    add_table(
        doc,
        ["组件", "类型", "用途"],
        [
            ["OpenAI 兼容 Chat API", "外部/可选", "检索、问答、审核、起草、字段抽取、Diff 解读"],
            ["OpenAI 兼容 Embeddings API", "外部/可选", "合同分块向量化（默认 bge-m3, 1024 维）"],
            ["qdrant-client", "本地嵌入式", "向量存储与余弦近邻检索"],
            ["pypdf / python-docx", "本地", "PDF/DOCX 文字层提取"],
            ["PyMuPDF (fitz)", "本地", "PDF 页面渲染为 PNG"],
            ["rapidocr-onnxruntime", "本地 ONNX", "扫描件 OCR 识别"],
        ],
    )

    add_heading(doc, "2.4 数据存储", 2)
    add_table(
        doc,
        ["存储", "路径/连接", "内容"],
        [
            ["SQLite", "sqlite+aiosqlite:///./legal_agent.db", "用户、合同、版本、分块、会话等"],
            ["Qdrant", "data/qdrant/", "contract_chunks 集合，向量 + payload"],
            ["文件系统", "data/cms_imports/{user_id}/", "CMS 导入原始文件"],
            ["文件系统", "data/contracts/{user_id}/", "审核/比对上传文件"],
        ],
    )

    # ── 三、目录结构 ──
    add_heading(doc, "三、项目目录结构", 1)
    doc.add_paragraph(
        "legal-agent/\n"
        "├── backend/                  # 后端服务\n"
        "│   ├── app/\n"
        "│   │   ├── main.py           # FastAPI 应用工厂、CORS、SPA 挂载\n"
        "│   │   ├── api/              # 路由层（v1/auth、legal、contract、cms、content）\n"
        "│   │   ├── core/             # config、database、security、migrations\n"
        "│   │   ├── models/           # SQLAlchemy ORM 模型\n"
        "│   │   ├── schemas/          # Pydantic DTO\n"
        "│   │   └── services/         # 业务服务层\n"
        "│   ├── data/                 # 运行时数据（qdrant、导入、合同文件）\n"
        "│   ├── static/               # 生产前端构建产物（可选）\n"
        "│   ├── run.py                # Uvicorn 启动入口\n"
        "│   └── requirements.txt\n"
        "├── frontend/                 # 前端 SPA\n"
        "│   └── src/\n"
        "│       ├── router/           # 路由与鉴权守卫\n"
        "│       ├── stores/           # Pinia 状态（auth）\n"
        "│       ├── api/              # http.ts、legal.ts、cms.ts\n"
        "│       ├── views/            # 页面组件\n"
        "│       ├── layouts/          # AppLayout、CmsLayout\n"
        "│       └── components/       # 公共组件\n"
        "├── doc/                      # 项目文档（用户手册、架构、算法总结）\n"
        "└── scripts/                  # 文档生成脚本"
    )

    # ── 四、后端分层 ──
    add_heading(doc, "四、后端分层架构", 1)
    doc.add_paragraph("请求处理链路：HTTP Request → api/v1 → schemas → services → models/core")
    add_table(
        doc,
        ["层级", "目录", "职责"],
        [
            ["路由层", "app/api/v1/*.py", "HTTP 端点、参数校验、Depends(get_current_user) 鉴权"],
            ["依赖注入", "app/api/deps.py", "HTTPBearer + JWT 解码，获取当前用户"],
            ["DTO 层", "app/schemas/", "Pydantic Request/Response 模型"],
            ["业务层", "app/services/", "核心业务逻辑编排"],
            ["持久层", "app/models/", "SQLAlchemy ORM 实体"],
            ["基础设施", "app/core/", "配置、数据库、安全、迁移"],
        ],
    )

    add_heading(doc, "4.1 核心服务模块", 2)
    add_table(
        doc,
        ["服务文件", "职责"],
        [
            ["auth_service.py / bootstrap.py", "用户认证、首次启动创建管理员"],
            ["llm_service.py", "LLM 统一调用，各业务 Prompt 封装"],
            ["embedding_service.py", "Embedding API 批量向量化"],
            ["vector_store.py", "Qdrant 本地集合封装（upsert/search/delete）"],
            ["text_chunker.py", "合同正文按条款/滑窗分块"],
            ["index_service.py", "分块 → 嵌入 → SQLite + Qdrant 索引流水线"],
            ["retrieval_service.py", "向量检索 + 关键词降级召回"],
            ["rag_service.py", "RAG 问答编排（检索 → LLM → 规则降级）"],
            ["document_parser.py", "PDF/DOCX 统一解析，触发 OCR"],
            ["document_ocr.py", "RapidOCR + PyMuPDF 扫描页识别"],
            ["field_extractor.py", "LLM JSON 字段抽取 + 正则兜底"],
            ["cms_service.py", "CMS 台账、导入、摘要、规则问答、种子数据"],
            ["search_service.py", "多模态检索（keyword/semantic/field/hybrid）"],
            ["diff_service.py", "条款级/行级 SequenceMatcher diff"],
            ["compare_service.py", "版本对比 + LLM 差异解读"],
            ["content_service.py", "首页静态内容（快捷链接、资讯等）"],
        ],
    )

    add_heading(doc, "4.2 启动初始化（lifespan）", 2)
    add_flow(
        doc,
        [
            "create_all：创建 SQLite 表结构",
            "run_migrations：增量列迁移（ALTER TABLE）",
            "ensure_admin_user：首次启动创建 bootstrap 管理员",
            "seed_cms_data：写入演示合同与版本数据",
            "refresh_legacy_version_snapshots：刷新旧版本快照",
            "reindex_all：尝试对种子合同建立向量索引",
        ],
    )

    # ── 五、前端架构 ──
    add_heading(doc, "五、前端架构", 1)

    add_heading(doc, "5.1 路由与布局", 2)
    add_table(
        doc,
        ["路径", "布局", "页面"],
        [
            ["/login", "无", "LoginView（公开）"],
            ["/", "HomeView", "首页门户"],
            ["/search、/contract/*、/qa/*", "AppLayout", "法律检索、合同工具、问答 AI"],
            ["/cms/*", "CmsLayout", "合同管理系统"],
        ],
    )
    doc.add_paragraph(
        "路由守卫：非 public 路由检查 auth.token；无 token 跳转 /login?redirect=...；"
        "有 token 时自动调用 /auth/me 加载用户信息。"
    )

    add_heading(doc, "5.2 状态与 API 客户端", 2)
    add_table(
        doc,
        ["模块", "文件", "说明"],
        [
            ["认证状态", "stores/auth.ts", "token 存 localStorage，login/logout/loadUser"],
            ["HTTP 基础", "api/http.ts", "Axios 实例，baseURL=/api/v1，401 自动跳登录"],
            ["法务 API", "api/legal.ts", "认证、内容、检索、聊天、合同审核/起草/比对"],
            ["CMS API", "api/cms.ts", "台账、导入、搜索、QA、版本对比、导出"],
        ],
    )

    add_heading(doc, "5.3 开发代理", 2)
    doc.add_paragraph(
        "开发模式下 Vite 运行于 5173，将 /api 与 /health 代理至 http://127.0.0.1:8010。"
        "生产模式下前端 build 产物复制至 backend/static，由 FastAPI SPAStaticFiles 托管。"
    )

    # ── 六、核心数据流 ──
    add_heading(doc, "六、核心数据流", 1)

    add_heading(doc, "6.1 用户登录", 2)
    add_flow(
        doc,
        [
            "LoginView 提交 username/password",
            "POST /api/v1/auth/login → auth_service.authenticate_user()",
            "bcrypt 校验密码 → security.create_access_token(user.id)",
            "返回 access_token → 前端存 localStorage",
            "GET /api/v1/auth/me（Bearer JWT）→ deps.get_current_user() 解码并查库",
            "路由守卫放行，进入业务页面",
        ],
    )

    add_heading(doc, "6.2 合同导入 + OCR + 索引", 2)
    add_flow(
        doc,
        [
            "POST /api/v1/cms/import/upload → 文件保存至 data/cms_imports/{user_id}/",
            "document_parser.parse_file()：pypdf 提取文字层",
            "文字不足页 → document_ocr（PyMuPDF 渲染 + RapidOCR 识别）",
            "field_extractor：LLM JSON 抽取字段，失败则规则引擎兜底",
            "写入 contract_import_tasks 表，返回抽取结果与 warnings",
            "用户确认 POST /cms/import/{id}/confirm → 新建合同或追加版本",
            "index_service.index_contract()：text_chunker 分块",
            "embedding_service 向量化 → contract_chunks 表 + vector_store.upsert",
            "managed_contracts.index_status = indexed",
        ],
    )

    add_heading(doc, "6.3 RAG 合同问答", 2)
    add_flow(
        doc,
        [
            "POST /api/v1/cms/contracts/{id}/qa → 校验 contract.user_id",
            "index_service.ensure_indexed() 确保已索引",
            "retrieval_service：优先 embed_query + Qdrant 向量检索（filter user_id + contract_id）",
            "向量不可用 → 关键词扩展 + contract_chunks 表内匹配",
            "llm_service.rag_answer() 基于检索片段生成回答",
            "LLM 不可用 → cms_service.answer_from_contract_knowledge() 规则回答",
            "返回 answer + citations + confidence",
        ],
    )

    add_heading(doc, "6.4 版本对比", 2)
    add_flow(
        doc,
        [
            "POST /api/v1/cms/contracts/{id}/compare（left_version_id, right_version_id）",
            "compare_service 从 contract_versions 加载左右版本正文",
            "diff_service：按「第X条」条款拆分 → SequenceMatcher 逐条对比",
            "条款标题重叠率 < 25% 时切换行级 diff",
            "summarize_diff_stats() 统计变更摘要",
            "llm_service.interpret_diff() AI 解读每条变更（无 Key 时 mock）",
            "返回 summary + changes[] + risk_note",
        ],
    )
    doc.add_paragraph(
        "补充：POST /api/v1/contract/compare 支持直接上传两个文件实时解析对比，"
        "不依赖 CMS 版本库，流程类似但输入为临时文件。"
    )

    # ── 七、外部依赖与降级 ──
    add_heading(doc, "七、外部依赖与降级策略", 1)
    add_table(
        doc,
        ["依赖", "集成方式", "不可用时的降级"],
        [
            ["OpenAI 兼容 Chat API", "llm_service._call_llm()", "返回 mock 演示文本"],
            ["OpenAI 兼容 Embeddings", "embedding_service.embed_texts()", "chunks 仅存 SQLite，index_status=no_embedding，改关键词检索"],
            ["Qdrant 本地", "QdrantClient(path=data/qdrant)", "跳过向量检索，纯 SQL/关键词 fallback"],
            ["RapidOCR", "本地 ONNX 推理", "写入 parse_warnings，不影响文字层 PDF"],
        ],
    )

    # ── 八、数据库模型 ──
    add_heading(doc, "八、数据库模型", 1)

    add_heading(doc, "8.1 通用模块（models.py）", 2)
    add_table(
        doc,
        ["表名", "主要字段", "说明"],
        [
            ["users", "username, email, hashed_password, display_name", "用户账户"],
            ["chat_sessions", "user_id, module, title", "问答会话"],
            ["chat_messages", "session_id, role, content", "会话消息"],
            ["contract_reviews", "user_id, filename, review_mode, content_text, result", "合同审核记录"],
            ["contract_drafts", "user_id, draft_type, purpose, style, content", "合同起草记录"],
        ],
    )

    add_heading(doc, "8.2 CMS 模块（cms_models.py）", 2)
    add_table(
        doc,
        ["表名", "主要字段", "说明"],
        [
            ["managed_contracts", "user_id, code, name, party_a/b, amount, status, content_text, index_status", "托管合同主表"],
            ["contract_versions", "contract_id, version, label, content, is_current", "版本快照"],
            ["contract_chunks", "contract_id, chunk_index, section_title, content, vector_id", "RAG 分块"],
            ["contract_import_tasks", "user_id, filename, extracted_json, content_text, status", "导入任务"],
        ],
    )
    doc.add_paragraph(
        "实体关系：User 1:N ManagedContract / ChatSession / ContractReview；"
        "ManagedContract 1:N ContractVersion / ContractChunk。"
    )

    # ── 九、API 结构 ──
    add_heading(doc, "九、API 模块结构", 1)
    add_table(
        doc,
        ["路由前缀", "文件", "鉴权", "主要端点"],
        [
            ["/api/v1/auth", "auth.py", "login 公开；me 需登录", "POST /login, GET /me"],
            ["/api/v1/content", "content.py", "无需登录", "首页快捷链接、AI 模块、资讯"],
            ["/api/v1", "legal.py", "需登录", "POST /search, POST /chat, GET /chat/sessions*"],
            ["/api/v1/contract", "contract.py", "需登录", "upload/review/draft/compare"],
            ["/api/v1/cms", "cms.py", "需登录", "台账 CRUD、导入、搜索、QA、版本对比、CSV 导出"],
            ["/health", "main.py", "公开", "健康检查"],
        ],
    )

    add_heading(doc, "9.1 CMS 主要端点", 2)
    add_table(
        doc,
        ["方法", "路径", "功能"],
        [
            ["GET", "/cms/stats", "台账统计"],
            ["GET/POST/PUT/DELETE", "/cms/contracts*", "合同 CRUD、批量更新、CSV 导出"],
            ["POST", "/cms/import/upload", "上传并解析（OCR + 字段抽取）"],
            ["POST", "/cms/import/{id}/confirm", "确认导入入库"],
            ["GET/POST", "/cms/search", "多模态合同搜索"],
            ["GET", "/cms/contracts/{id}/summary", "AI 摘要"],
            ["POST", "/cms/contracts/{id}/qa", "RAG 问答"],
            ["GET", "/cms/contracts/{id}/versions", "版本列表"],
            ["POST", "/cms/contracts/{id}/compare", "版本对比"],
        ],
    )

    # ── 十、部署与配置 ──
    add_heading(doc, "十、部署与运行时配置", 1)

    add_heading(doc, "10.1 端口与启动", 2)
    add_table(
        doc,
        ["环境", "端口", "启动方式"],
        [
            ["开发-后端", "8010", "backend/run.py 或 start.bat"],
            ["开发-前端", "5173", "frontend: npm run dev"],
            ["生产合一", "8010", "npm run build → backend/static → python run.py"],
        ],
    )

    add_heading(doc, "10.2 关键环境变量", 2)
    add_table(
        doc,
        ["变量", "默认值", "说明"],
        [
            ["PORT", "8010", "后端监听端口"],
            ["DATABASE_URL", "sqlite+aiosqlite:///./legal_agent.db", "数据库连接"],
            ["SECRET_KEY", "your-secret-key-change-in-production", "JWT 签名密钥"],
            ["ACCESS_TOKEN_EXPIRE_MINUTES", "480", "Token 有效期（分钟）"],
            ["OPENAI_API_KEY / BASE_URL / MODEL", "—", "LLM 配置"],
            ["EMBEDDING_MODEL / DIMENSIONS", "text-embedding-3-small / 1024", "向量模型"],
            ["QDRANT_PATH", "data/qdrant", "向量库目录"],
            ["PARSER_OCR_ENABLED / DPI", "true / 200", "本地 OCR 开关与渲染分辨率"],
            ["CHUNK_SIZE / CHUNK_OVERLAP", "800 / 100", "分块参数"],
            ["RAG_TOP_K", "5", "RAG 检索 Top-K"],
            ["BOOTSTRAP_ADMIN_USERNAME/PASSWORD", "admin / admin123", "首次启动管理员"],
            ["CORS_ALLOW_ORIGINS", "localhost:5173", "CORS 白名单"],
        ],
    )

    # ── 十一、安全机制 ──
    add_heading(doc, "十一、安全机制", 1)

    add_heading(doc, "11.1 认证与密码", 2)
    add_flow(
        doc,
        [
            "JWT Bearer Token（HS256），payload 含 sub=user.id 与 exp",
            "前端 Axios 拦截器自动附加 Authorization: Bearer {token}",
            "bcrypt 哈希存储密码，verify_password 校验",
            "401 响应时前端清除 token 并重定向登录页",
        ],
    )

    add_heading(doc, "11.2 用户数据隔离", 2)
    add_table(
        doc,
        ["层级", "隔离方式"],
        [
            ["API 层", "Depends(get_current_user) 获取当前用户 ID"],
            ["CMS", "_get_user_contract() 校验 contract.user_id == user.id"],
            ["合同工具", "ContractReview/Draft 查询带 user_id 过滤"],
            ["聊天", "ChatSession.user_id 校验"],
            ["向量库", "Qdrant payload 含 user_id，检索时 Filter 过滤"],
            ["文件存储", "data/{cms_imports,contracts}/{user_id}/ 分子目录"],
        ],
    )
    doc.add_paragraph(
        "其他：/content/* 端点无需认证（静态展示数据）；"
        "上传文件限制 contract_max_upload_bytes = 50MB；"
        "生产环境须修改 SECRET_KEY 并关闭 debug。"
    )

    # ── 十二、架构特点与扩展建议 ──
    add_heading(doc, "十二、架构特点与扩展建议", 1)
    doc.add_paragraph("当前架构特点：", style="List Bullet")
    doc.add_paragraph("单体 FastAPI 便于部署与调试，前后端分离支持独立开发。", style="List Bullet")
    doc.add_paragraph("AI 能力统一走 OpenAI 兼容接口，LLM 与 Embedding 可独立配置。", style="List Bullet")
    doc.add_paragraph("多层降级设计：向量 → 关键词 → 规则引擎 → Mock，保障无 Key 环境可用。", style="List Bullet")
    doc.add_paragraph("OCR 本地推理，扫描件处理不依赖云端。", style="List Bullet")
    doc.add_paragraph("扩展建议：", style="List Bullet")
    doc.add_paragraph("数据库：SQLite 可迁移至 PostgreSQL 以支持并发与生产规模。", style="List Bullet")
    doc.add_paragraph("向量库：本地 Qdrant 可切换为远程 Qdrant/Milvus 集群。", style="List Bullet")
    doc.add_paragraph("任务队列：大文件 OCR/索引可异步化（Celery/RQ + 进度通知）。", style="List Bullet")
    doc.add_paragraph("权限：可增加 RBAC 角色（管理员/法务/业务）与组织级数据隔离。", style="List Bullet")

    doc.add_paragraph()
    footer = doc.add_paragraph("—— 文档结束 ——")
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    copy = doc.add_paragraph("© 益慧科技有限公司 · Legal-Agent 架构设计文档")
    copy.alignment = WD_ALIGN_PARAGRAPH.CENTER

    return doc


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = build_document()
    doc.save(OUTPUT)
    print(f"已生成: {OUTPUT}")


if __name__ == "__main__":
    main()
