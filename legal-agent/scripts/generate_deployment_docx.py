"""Generate legal-agent deployment manual Word document."""
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

OUTPUT = Path(__file__).resolve().parents[1] / "doc" / "legal-agent部署手册.docx"


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


def add_code(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(9)


def build_document() -> Document:
    doc = Document()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("益慧科技 Legal-Agent\n部署手册")
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = RGBColor(0x00, 0x63, 0x64)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run(f"文档版本：1.0　　更新日期：{date.today().isoformat()}").font.size = Pt(10)

    doc.add_paragraph(
        "本文档说明 Legal-Agent 从 Windows 开发环境，经 Ubuntu Staging（可联网）验证，"
        "最终部署至隔离 Ubuntu 生产环境的完整流程，涵盖环境准备、构建打包、配置差异、"
        "服务化运行、验证与回滚。"
    )

    # ── 一、三环境概览 ──
    add_heading(doc, "一、三环境概览", 1)
    add_table(
        doc,
        ["维度", "开发环境（Dev）", "Staging 环境", "生产环境（Prod）"],
        [
            ["操作系统", "Windows 10/11", "Ubuntu Linux（可联网）", "Ubuntu Linux（网络隔离）"],
            ["用途", "功能开发、联调、本地演示", "预发布验证、集成测试、打离线包", "正式对外服务"],
            ["前端运行", "Vite Dev Server（5173）", "构建后由 FastAPI 托管或 Nginx", "构建后由 FastAPI 托管或 Nginx"],
            ["后端运行", "Uvicorn（8010）", "Uvicorn / systemd 服务", "systemd 常驻服务"],
            ["联网", "可访问外网/内网 MaaS", "可访问外网/内网 MaaS", "仅内网（不可访问公网）"],
            ["依赖安装", "pip / npm 在线安装", "pip / npm 在线安装", "离线 wheel + 预构建前端"],
            ["数据持久化", "本地 SQLite + data/", "独立 SQLite + data/", "独立 SQLite + data/（需备份）"],
            ["AI 能力", "可配置 MaaS API Key", "与生产相同配置做联调", "内网 MaaS 端点或演示模式"],
        ],
    )
    doc.add_paragraph("部署路径总览：")
    add_steps(
        doc,
        [
            "开发环境（Windows）：日常开发与功能验证。",
            "Staging（Ubuntu）：拉取代码 → 安装依赖 → 构建前端 → 配置 .env → 启动验证 → 制作离线发布包。",
            "生产环境（隔离 Ubuntu）：通过安全通道传输发布包 → 离线安装 → 配置生产 .env → systemd 启动 → 健康检查。",
        ],
    )

    # ── 二、通用要求 ──
    add_heading(doc, "二、通用环境与版本要求", 1)
    add_table(
        doc,
        ["组件", "最低版本", "说明"],
        [
            ["Python", "3.10+", "后端运行时，Dev/Staging/Prod 大版本需一致"],
            ["Node.js", "18 LTS+", "仅 Dev/Staging 构建前端时需要"],
            ["npm", "9+", "与 Node.js 配套"],
            ["磁盘空间", "≥ 2 GB", "含 Python 依赖、OCR 模型、向量库与上传文件"],
            ["内存", "≥ 4 GB", "OCR 与向量检索会占用额外内存"],
        ],
    )
    doc.add_paragraph(
        "重要：Windows 下创建的 Python 虚拟环境（.venv）不可直接复制到 Linux 使用。"
        "必须在 Staging 或 Linux 上重新创建 venv，或使用 Linux 平台 wheel 离线安装。"
    )

    # ── 三、开发环境 ──
    add_heading(doc, "三、开发环境部署（Windows）", 1)

    add_heading(doc, "3.1 获取代码", 2)
    add_code(
        doc,
        "git clone <仓库地址> legal-agent\ncd legal-agent",
    )

    add_heading(doc, "3.2 后端启动", 2)
    add_steps(
        doc,
        [
            "进入 backend 目录，创建虚拟环境：python -m venv .venv",
            "激活虚拟环境：.venv\\Scripts\\activate",
            "安装依赖：pip install -r requirements.txt",
            "复制配置：copy .env.example .env，按需填写 OPENAI_API_KEY 等",
            "启动后端：python run.py",
        ],
    )
    doc.add_paragraph("后端默认监听 http://127.0.0.1:8010。也可使用项目根目录 start.bat 一键启动前后端。")

    add_heading(doc, "3.3 前端启动", 2)
    add_steps(
        doc,
        [
            "进入 frontend 目录：npm install",
            "启动开发服务器：npm run dev",
            "浏览器访问 http://localhost:5173/login",
        ],
    )
    doc.add_paragraph(
        "开发模式下 Vite 将 /api 与 /health 代理至 8010，前后端分离运行。"
        "默认账号 admin / admin123（首次启动自动创建）。"
    )

    add_heading(doc, "3.4 开发环境 .env 参考", 2)
    add_code(
        doc,
        "DEBUG=true\n"
        "HOST=0.0.0.0\n"
        "PORT=8010\n"
        "SECRET_KEY=dev-only-secret\n"
        "OPENAI_API_KEY=<开发用 Key>\n"
        "OPENAI_BASE_URL=https://maas.ehuidata.com/openai/v1\n"
        "OPENAI_MODEL=deepseek-v4-flash-04275\n"
        "EMBEDDING_MODEL=bge-m3\n"
        "EMBEDDING_DIMENSIONS=1024\n"
        "QDRANT_PATH=data/qdrant\n"
        "PARSER_OCR_ENABLED=true\n"
        "BOOTSTRAP_ADMIN_USERNAME=admin\n"
        "BOOTSTRAP_ADMIN_PASSWORD=admin123",
    )

    add_heading(doc, "3.5 开发环境验证清单", 2)
    add_table(
        doc,
        ["检查项", "预期结果"],
        [
            ["GET /health", "返回 status=healthy"],
            ["登录 admin/admin123", "成功进入首页"],
            ["法律检索", "返回 AI 分析或演示模式回答"],
            ["CMS 合同导入 PDF", "正文提取成功，扫描件触发 OCR warnings"],
            ["合同 RAG 问答", "返回答案与引用片段"],
        ],
    )

    # ── 四、Staging ──
    add_heading(doc, "四、Staging 环境部署（Ubuntu，可联网）", 1)
    doc.add_paragraph(
        "Staging 用于在类生产环境下验证功能、性能与配置，并在此阶段制作供隔离生产环境使用的离线发布包。"
    )

    add_heading(doc, "4.1 系统依赖", 2)
    add_code(
        doc,
        "sudo apt update\n"
        "sudo apt install -y python3 python3-venv python3-pip \\\n"
        "  nodejs npm git curl",
    )
    doc.add_paragraph("建议确认 python3 --version ≥ 3.10，node --version ≥ 18。")

    add_heading(doc, "4.2 部署步骤", 2)
    add_steps(
        doc,
        [
            "创建部署目录：sudo mkdir -p /opt/legal-agent && sudo chown $USER:$USER /opt/legal-agent",
            "拉取代码：git clone <仓库地址> /opt/legal-agent（或 rsync/scp 从开发机同步）",
            "后端虚拟环境：cd /opt/legal-agent/backend && python3 -m venv .venv",
            "安装 Python 依赖：.venv/bin/pip install -r requirements.txt",
            "配置环境：cp .env.example .env，按 Staging 要求修改（见 4.3）",
            "构建前端：cd /opt/legal-agent/frontend && npm install && npm run build",
            "复制静态资源：cp -r dist/* /opt/legal-agent/backend/static/",
            "启动服务：cd /opt/legal-agent/backend && .venv/bin/python run.py",
        ],
    )

    add_heading(doc, "4.3 Staging 环境 .env 差异", 2)
    add_table(
        doc,
        ["配置项", "Staging 建议值", "说明"],
        [
            ["DEBUG", "false", "关闭调试模式"],
            ["SECRET_KEY", "随机强密钥", "勿与开发环境相同"],
            ["BOOTSTRAP_ADMIN_PASSWORD", "强密码", "首次部署后建议修改管理员密码"],
            ["OPENAI_BASE_URL", "内网 MaaS 地址", "与生产环境保持一致以便验证"],
            ["CORS_ALLOW_ORIGINS", "Staging 前端域名", "若前后端分离部署时需配置"],
            ["DATABASE_URL", "默认 SQLite 即可", "高并发场景可后续迁移 PostgreSQL"],
        ],
    )

    add_heading(doc, "4.4 配置 systemd 服务（推荐）", 2)
    add_code(
        doc,
        "# /etc/systemd/system/legal-agent.service\n"
        "[Unit]\n"
        "Description=Legal-Agent Backend\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        "User=legalagent\n"
        "WorkingDirectory=/opt/legal-agent/backend\n"
        "Environment=PATH=/opt/legal-agent/backend/.venv/bin\n"
        "ExecStart=/opt/legal-agent/backend/.venv/bin/python run.py\n"
        "Restart=on-failure\n"
        "RestartSec=5\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target",
    )
    add_code(
        doc,
        "sudo systemctl daemon-reload\n"
        "sudo systemctl enable legal-agent\n"
        "sudo systemctl start legal-agent\n"
        "sudo systemctl status legal-agent",
    )

    add_heading(doc, "4.5 可选：Nginx 反向代理", 2)
    doc.add_paragraph(
        "若需通过 80/443 端口对外、配置 HTTPS 或限流，可在 FastAPI 前增加 Nginx。"
        "FastAPI 已可托管 backend/static 中的前端，简单场景下可省略 Nginx，直接访问 8010。"
    )
    add_code(
        doc,
        "server {\n"
        "    listen 80;\n"
        "    server_name staging.legal-agent.example.com;\n"
        "    client_max_body_size 50m;\n"
        "    location / {\n"
        "        proxy_pass http://127.0.0.1:8010;\n"
        "        proxy_set_header Host $host;\n"
        "        proxy_set_header X-Real-IP $remote_addr;\n"
        "    }\n"
        "}",
    )

    add_heading(doc, "4.6 Staging 验证清单", 2)
    add_table(
        doc,
        ["检查项", "命令/操作", "预期"],
        [
            ["健康检查", "curl http://127.0.0.1:8010/health", "status=healthy"],
            ["前端页面", "浏览器访问 /login", "页面正常加载"],
            ["AI 接口", "登录后执行法律检索", "返回有效响应"],
            ["OCR", "上传扫描 PDF 导入", "warnings 含 OCR 识别提示"],
            ["向量索引", "导入合同后问答", "RAG 返回引用片段"],
            ["日志", "journalctl -u legal-agent -f", "无持续报错"],
        ],
    )

    # ── 五、离线发布包 ──
    add_heading(doc, "五、在 Staging 制作生产离线发布包", 1)
    doc.add_paragraph(
        "生产环境网络隔离，无法执行 pip install 或 npm install。"
        "须在 Staging（可联网的 Linux）上预先下载 Linux 平台依赖并构建前端，打包后通过安全通道传输至生产。"
    )

    add_heading(doc, "5.1 目录结构", 2)
    add_code(
        doc,
        "legal-agent-release-v1.0.0/\n"
        "├── app/                    # 应用源码（backend/app、run.py 等）\n"
        "├── static/                 # 前端构建产物（frontend/dist）\n"
        "├── wheels/                 # Python 离线 wheel（Linux x86_64）\n"
        "├── requirements.txt\n"
        "├── install.sh              # 生产环境离线安装脚本\n"
        "├── .env.production.example # 生产配置模板（不含密钥）\n"
        "└── VERSION                 # 版本号与构建时间",
    )

    add_heading(doc, "5.2 打包步骤（在 Staging 执行）", 2)
    add_steps(
        doc,
        [
            "确保 Staging 上已完成一次完整部署且验证通过。",
            "下载 Linux wheel：mkdir wheels && .venv/bin/pip download -r requirements.txt -d wheels/",
            "构建前端：cd frontend && npm run build",
            "创建发布目录并复制文件（见下方脚本）。",
            "在 Staging 上执行一次 OCR 冒烟测试，确认 rapidocr-onnxruntime 模型随 wheel 正常加载。",
            "打包压缩：tar czvf legal-agent-release-v1.0.0.tar.gz legal-agent-release-v1.0.0/",
            "校验：sha256sum legal-agent-release-v1.0.0.tar.gz > checksum.sha256",
            "通过内网文件服务器、堡垒机或加密 U 盘传输至生产环境。",
        ],
    )

    add_heading(doc, "5.3 打包脚本示例", 2)
    add_code(
        doc,
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "VERSION=${1:-1.0.0}\n"
        "ROOT=/opt/legal-agent\n"
        "OUT=legal-agent-release-${VERSION}\n"
        "rm -rf \"$OUT\" && mkdir -p \"$OUT\"/wheels\n"
        "cp -r \"$ROOT/backend/app\" \"$ROOT/backend/run.py\" \\\n"
        "   \"$ROOT/backend/requirements.txt\" \"$OUT/\"\n"
        "mv \"$OUT/app\" \"$OUT/app.bak\"  # 保持 backend 结构\n"
        "mkdir -p \"$OUT/backend\" && mv \"$OUT/app.bak\" \"$OUT/backend/app\"\n"
        "mv \"$OUT/run.py\" \"$OUT/backend/\"\n"
        "mv \"$OUT/requirements.txt\" \"$OUT/backend/\"\n"
        "cp -r \"$ROOT/frontend/dist\" \"$OUT/backend/static\"\n"
        "$ROOT/backend/.venv/bin/pip download -r \"$ROOT/backend/requirements.txt\" \\\n"
        "  -d \"$OUT/wheels\"\n"
        "cp \"$ROOT/backend/.env.example\" \"$OUT/.env.production.example\"\n"
        "echo \"$VERSION $(date -Iseconds)\" > \"$OUT/VERSION\"\n"
        "tar czvf \"${OUT}.tar.gz\" \"$OUT\"",
    )

    add_heading(doc, "5.4 install.sh 离线安装脚本示例", 2)
    add_code(
        doc,
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        "INSTALL_DIR=/opt/legal-agent\n"
        "sudo mkdir -p \"$INSTALL_DIR\"\n"
        "sudo cp -r backend \"$INSTALL_DIR/\"\n"
        "cd \"$INSTALL_DIR/backend\"\n"
        "python3 -m venv .venv\n"
        ".venv/bin/pip install --no-index --find-links=../wheels -r requirements.txt\n"
        "mkdir -p data/qdrant data/cms_imports data/contracts\n"
        "echo '请编辑 /opt/legal-agent/backend/.env 后执行 systemctl start legal-agent'",
    )

    # ── 六、生产环境 ──
    add_heading(doc, "六、生产环境部署（Ubuntu，网络隔离）", 1)
    doc.add_paragraph(
        "生产服务器无法访问公网，所有依赖必须来自 Staging 制作的离线发布包。"
        "AI 服务须使用生产内网可访问的 MaaS 端点，或接受演示模式降级。"
    )

    add_heading(doc, "6.1 前置条件", 2)
    add_table(
        doc,
        ["条件", "说明"],
        [
            ["发布包", "legal-agent-release-x.x.x.tar.gz + checksum.sha256"],
            ["操作系统", "Ubuntu 20.04/22.04 LTS（与 Staging 同架构，建议 x86_64）"],
            ["Python", "python3 ≥ 3.10 已预装"],
            ["运行用户", "专用账号 legalagent，禁止 root 直接运行"],
            ["内网 MaaS", "OPENAI_BASE_URL 指向隔离网内 LLM/Embedding 服务"],
            ["防火墙", "仅开放业务所需端口（如 8010 或 Nginx 80/443）"],
            ["备份策略", "定期备份 legal_agent.db 与 data/ 目录"],
        ],
    )

    add_heading(doc, "6.2 部署步骤", 2)
    add_steps(
        doc,
        [
            "校验发布包：sha256sum -c checksum.sha256",
            "解压：tar xzvf legal-agent-release-v1.0.0.tar.gz",
            "创建运行用户：sudo useradd -r -m -s /bin/bash legalagent（若不存在）",
            "安装：sudo bash install.sh 或按 5.4 手动执行",
            "配置生产 .env：sudo cp .env.production.example /opt/legal-agent/backend/.env",
            "编辑 .env：设置 SECRET_KEY、管理员密码、内网 MaaS 地址（见 6.3）",
            "设置权限：sudo chown -R legalagent:legalagent /opt/legal-agent",
            "安装 systemd 服务（见 4.4，User=legalagent）",
            "启动：sudo systemctl start legal-agent",
            "验证：curl http://127.0.0.1:8010/health",
            "业务验收：登录、导入合同、RAG 问答、版本对比",
        ],
    )

    add_heading(doc, "6.3 生产环境 .env 关键配置", 2)
    add_code(
        doc,
        "DEBUG=false\n"
        "HOST=0.0.0.0\n"
        "PORT=8010\n"
        "SECRET_KEY=<生产环境随机强密钥，至少32字符>\n"
        "ACCESS_TOKEN_EXPIRE_MINUTES=480\n"
        "\n"
        "# 内网 MaaS（生产隔离网内可达）\n"
        "OPENAI_API_KEY=<生产 Key>\n"
        "OPENAI_BASE_URL=http://<内网MaaS地址>/openai/v1\n"
        "OPENAI_MODEL=deepseek-v4-flash-04275\n"
        "EMBEDDING_MODEL=bge-m3\n"
        "EMBEDDING_DIMENSIONS=1024\n"
        "\n"
        "QDRANT_PATH=data/qdrant\n"
        "PARSER_OCR_ENABLED=true\n"
        "PARSER_OCR_DPI=200\n"
        "\n"
        "BOOTSTRAP_ADMIN_ENABLED=true\n"
        "BOOTSTRAP_ADMIN_USERNAME=admin\n"
        "BOOTSTRAP_ADMIN_PASSWORD=<强密码，部署后立即修改>\n"
        "\n"
        "# 生产勿开放开发 CORS\n"
        "CORS_ALLOW_ORIGINS=[]",
    )
    doc.add_paragraph(
        "注意：若内网 MaaS 不可达，系统自动降级为演示模式（Mock），"
        "合同 OCR 仍可本地运行（RapidOCR 不依赖外网）。"
        "向量检索依赖 Embedding API；若不可用则降级为关键词检索。"
    )

    add_heading(doc, "6.4 数据目录与备份", 2)
    add_table(
        doc,
        ["路径", "内容", "备份建议"],
        [
            ["backend/legal_agent.db", "SQLite 业务数据库", "每日增量备份"],
            ["backend/data/qdrant/", "向量索引", "随数据库同步备份"],
            ["backend/data/cms_imports/", "导入原始文件", "每日备份"],
            ["backend/data/contracts/", "审核/比对上传", "每日备份"],
            ["backend/.env", "环境配置（含密钥）", "加密离线保管，勿入版本库"],
        ],
    )
    add_code(
        doc,
        "# 备份示例（cron 每日执行）\n"
        "tar czvf /backup/legal-agent-$(date +%Y%m%d).tar.gz \\\n"
        "  /opt/legal-agent/backend/legal_agent.db \\\n"
        "  /opt/legal-agent/backend/data",
    )

    add_heading(doc, "6.5 生产验证清单", 2)
    add_table(
        doc,
        ["检查项", "预期"],
        [
            ["/health 返回 healthy", "通过"],
            ["HTTPS/防火墙仅开放必要端口", "通过"],
            ["管理员可登录且密码非默认值", "通过"],
            ["合同导入 + OCR（扫描 PDF）", "正文提取成功"],
            ["RAG 问答（需内网 Embedding）", "返回引用片段或关键词降级"],
            ["法律检索（需内网 LLM）", "返回 AI 回答或演示模式提示"],
            ["systemctl 重启后服务自启", "通过"],
            ["日志无持续 Traceback", "通过"],
        ],
    )

    # ── 七、三环境配置对比 ──
    add_heading(doc, "七、三环境配置对比速查", 1)
    add_table(
        doc,
        ["配置项", "Dev（Windows）", "Staging", "Prod（隔离）"],
        [
            ["DEBUG", "true", "false", "false"],
            ["前端", "npm run dev（5173）", "build → static", "build → static（离线包）"],
            ["依赖安装", "pip / npm 在线", "pip / npm 在线", "wheel 离线 + 预构建 static"],
            ["SECRET_KEY", "可简单", "随机强密钥", "独立随机强密钥"],
            ["OPENAI_BASE_URL", "开发 MaaS", "与 Prod 一致的内网地址", "隔离网内 MaaS"],
            ["BOOTSTRAP_ADMIN_PASSWORD", "admin123", "强密码", "强密码且首次登录后修改"],
            ["服务管理", "手动 / start.bat", "systemd 推荐", "systemd 必须"],
            ["CORS", "localhost:5173", "按需", "空或生产域名"],
        ],
    )

    # ── 八、升级与回滚 ──
    add_heading(doc, "八、版本升级与回滚", 1)

    add_heading(doc, "8.1 Staging 升级流程", 2)
    add_steps(
        doc,
        [
            "git pull 获取新版本代码。",
            "pip install -r requirements.txt && npm run build。",
            "执行 Staging 验证清单。",
            "重新制作离线发布包并更新 VERSION。",
        ],
    )

    add_heading(doc, "8.2 生产升级流程", 2)
    add_steps(
        doc,
        [
            "升级前备份 legal_agent.db 与 data/ 目录。",
            "停止服务：sudo systemctl stop legal-agent。",
            "解压新版本至临时目录，对比 .env 配置差异。",
            "覆盖 backend/app、backend/static，保留 .env 与 data/。",
            "若有新依赖：.venv/bin/pip install --no-index --find-links=../wheels -r requirements.txt。",
            "启动服务并执行生产验证清单。",
        ],
    )

    add_heading(doc, "8.3 回滚", 2)
    add_steps(
        doc,
        [
            "停止服务：sudo systemctl stop legal-agent。",
            "从备份恢复 legal_agent.db 与 data/（若数据结构有变）。",
            "恢复上一版本发布包的 app/ 与 static/。",
            "启动服务并验证 /health 与核心功能。",
        ],
    )

    # ── 九、故障排查 ──
    add_heading(doc, "九、常见问题排查", 1)
    add_table(
        doc,
        ["现象", "可能原因", "处理建议"],
        [
            ["8010 端口被占用", "旧进程未退出", "Windows: netstat -ano | findstr 8010；Linux: ss -tlnp | grep 8010"],
            ["pip 离线安装失败", "wheel 平台不匹配", "在 Linux Staging 重新 pip download，勿用 Windows wheel"],
            ["OCR 不可用", "rapidocr 依赖缺失", "确认 wheels 含 rapidocr-onnxruntime 及 onnxruntime"],
            ["AI 返回演示内容", "OPENAI_API_KEY 未配置或 MaaS 不可达", "检查 .env 与内网网络连通性"],
            ["RAG 无引用片段", "Embedding 失败或未索引", "检查 index_status，查看日志中 reindex 报错"],
            ["前端 404", "static 未复制", "确认 backend/static/index.html 存在"],
            ["登录 401", "Token 过期或 SECRET_KEY 变更", "清除浏览器 localStorage 重新登录"],
            ["上传失败", "文件超过 50MB", "压缩文件或调整 contract_max_upload_bytes"],
        ],
    )

    # ── 十、安全 checklist ──
    add_heading(doc, "十、生产安全 Checklist", 1)
    add_steps(
        doc,
        [
            "修改默认管理员密码，考虑部署后关闭 BOOTSTRAP_ADMIN_ENABLED。",
            "SECRET_KEY 使用密码学安全随机值，各环境互不相同。",
            ".env 文件权限设为 600，仅 legalagent 用户可读。",
            "生产 DEBUG=false，不对外暴露 /docs OpenAPI（可考虑关闭）。",
            "配置防火墙，仅允许业务网段访问。",
            "启用 HTTPS（Nginx + 内网证书）。",
            "建立数据库与 data/ 定期备份与恢复演练。",
            "API Key 不入版本库，通过安全渠道分发。",
            "隔离环境禁止 outbound 公网，仅允许访问内网 MaaS。",
        ],
    )

    doc.add_paragraph()
    footer = doc.add_paragraph("—— 文档结束 ——")
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    copy = doc.add_paragraph("© 益慧科技有限公司 · Legal-Agent 部署手册")
    copy.alignment = WD_ALIGN_PARAGRAPH.CENTER

    return doc


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = build_document()
    doc.save(OUTPUT)
    print(f"已生成: {OUTPUT}")


if __name__ == "__main__":
    main()
