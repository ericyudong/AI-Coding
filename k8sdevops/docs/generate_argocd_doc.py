# -*- coding: utf-8 -*-
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn

doc = Document()

style = doc.styles["Normal"]
style.font.name = "微软雅黑"
style.font.size = Pt(11)
style._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")

for i in range(1, 4):
    hs = doc.styles[f"Heading {i}"]
    hs.font.name = "微软雅黑"
    hs.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    hs._element.rPr.rFonts.set(qn("w:eastAsia"), "微软雅黑")


def add_table(headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            table.rows[ri + 1].cells[ci].text = val
    doc.add_paragraph()


doc.add_heading("Argo CD 目录文件说明", level=0)
doc.add_paragraph(
    "本文档说明 argocd/ 目录下各配置文件的作用，以及它们在 GitOps CD 流程中的协作关系。"
)

doc.add_heading("目录结构", level=1)
doc.add_paragraph(
    "argocd/\n"
    "├── application.yaml   # Argo CD Application：声明要部署的应用\n"
    "└── project.yaml       # Argo CD AppProject：项目级隔离与权限边界"
)

doc.add_heading("文件一览表", level=1)
add_table(
    ["文件路径", "资源类型", "作用摘要"],
    [
        [
            "application.yaml",
            "Application",
            "定义 Git 源、目标集群/命名空间，以及自动同步策略",
        ],
        [
            "project.yaml",
            "AppProject",
            "限制可访问的 Git 仓库与部署目标，做多租户隔离",
        ],
    ],
)

doc.add_heading("1. application.yaml", level=1)
doc.add_paragraph(
    "作用：定义名为 demo-app 的 Argo CD Application，是 GitOps 持续交付的核心配置。"
)
doc.add_paragraph(
    "部署位置：资源创建在 argocd 命名空间（Argo CD 控制面所在命名空间）。"
)

doc.add_heading("关键字段说明", level=2)
add_table(
    ["字段", "当前值", "含义"],
    [
        ["metadata.name", "demo-app", "Application 名称，Argo CD UI/CLI 中的应用标识"],
        ["metadata.namespace", "argocd", "必须部署在 Argo CD 所在命名空间"],
        [
            "finalizers",
            "resources-finalizer.argocd.argoproj.io",
            "删除 Application 时级联清理其管理的 K8s 资源",
        ],
        [
            "spec.project",
            "default",
            "所属 AppProject（也可改为 demo 以匹配 project.yaml）",
        ],
        ["spec.source.repoURL", "Git 仓库地址", "监控的 GitOps 仓库"],
        ["spec.source.targetRevision", "main", "跟踪的分支/Tag/Commit"],
        ["spec.source.path", "manifests", "仓库内清单目录（Deployment、Service 等）"],
        [
            "spec.destination.server",
            "https://kubernetes.default.svc",
            "目标集群（本集群 API Server）",
        ],
        ["spec.destination.namespace", "demo-app", "工作负载部署到的命名空间"],
        [
            "syncPolicy.automated.prune",
            "true",
            "Git 中删除的资源会从集群同步删除",
        ],
        [
            "syncPolicy.automated.selfHeal",
            "true",
            "集群被手动篡改时自动纠正回 Git 状态",
        ],
        [
            "syncOptions",
            "CreateNamespace=true",
            "目标命名空间不存在时自动创建",
        ],
        ["revisionHistoryLimit", "5", "保留的同步历史条数"],
    ],
)

doc.add_heading("工作方式", level=2)
doc.add_paragraph(
    "Git 仓库 manifests/ 目录发生变更 → Argo CD 检测到差异（OutOfSync）→ "
    "按 syncPolicy 自动同步到 demo-app 命名空间 → Deployment / Service 等资源更新完成。"
)
doc.add_paragraph(
    "与 Tekton 的衔接：Tekton 的 update-manifest Task 会改写 manifests/deployment.yaml "
    "并 push 回 Git；Argo CD 监听到该变更后自动完成部署。"
)
doc.add_paragraph("使用方式：")
doc.add_paragraph("先把 repoURL 改成真实仓库地址", style="List Bullet")
doc.add_paragraph("kubectl apply -f argocd/application.yaml", style="List Bullet")
doc.add_paragraph(
    "查看同步状态：argocd app get demo-app 或 kubectl get application -n argocd",
    style="List Bullet",
)

doc.add_heading("2. project.yaml", level=1)
doc.add_paragraph(
    "作用：定义名为 demo 的 Argo CD AppProject，用于项目级隔离与安全边界。"
)
doc.add_paragraph(
    "说明：AppProject 不是业务应用本身，而是一组 Application 可共享的“租户/项目”策略。"
)

doc.add_heading("关键字段说明", level=2)
add_table(
    ["字段", "当前值", "含义"],
    [
        ["metadata.name", "demo", "项目名称"],
        ["spec.description", "Demo project...", "项目描述"],
        [
            "spec.sourceRepos",
            "指定 Git 仓库",
            "仅允许从此仓库拉取清单（白名单）",
        ],
        [
            "spec.destinations",
            "demo-app + 本集群",
            "仅允许部署到该命名空间与集群",
        ],
        [
            "spec.clusterResourceWhitelist",
            "Namespace",
            "允许创建/管理的集群级资源类型",
        ],
    ],
)

doc.add_heading("安全意义", level=2)
add_table(
    ["能力", "作用"],
    [
        ["sourceRepos", "防止 Application 误用未授权的 Git 仓库"],
        [
            "destinations",
            "防止部署到未授权的集群或命名空间（如 kube-system）",
        ],
        [
            "clusterResourceWhitelist",
            "限制可创建的集群级资源，降低权限面",
        ],
    ],
)

doc.add_paragraph(
    "与 application.yaml 的关系：当前 application.yaml 中 spec.project 为 default。"
    "若要启用本项目的隔离策略，将 Application 的 project 改为 demo。"
)
doc.add_paragraph("使用方式：kubectl apply -f argocd/project.yaml（建议先于 Application 创建）")

doc.add_heading("协作关系示意", level=1)
doc.add_paragraph(
    "project.yaml (AppProject: demo)\n"
    "    │  约束：允许哪些仓库、部署到哪里\n"
    "    ▼\n"
    "application.yaml (Application: demo-app)\n"
    "    │  从 Git manifests/ 拉取期望状态\n"
    "    ▼\n"
    "Kubernetes 命名空间 demo-app（Deployment、Service、Namespace 等）"
)
doc.add_paragraph(
    "与整体流水线：Tekton CI 构建镜像并更新 manifests/ → Git 仓库变更 → "
    "Argo CD Application 自动同步 → 集群中应用更新。"
)

doc.add_heading("部署建议顺序", level=1)
for i, step in enumerate(
    [
        "确保集群已安装 Argo CD，且存在 argocd 命名空间",
        "kubectl apply -f argocd/project.yaml",
        "修改 application.yaml 中的 repoURL（及可选的 project: demo）",
        "kubectl apply -f argocd/application.yaml",
        "用 argocd app get demo-app 或 UI 确认同步状态为 Healthy / Synced",
    ],
    1,
):
    doc.add_paragraph(f"{i}. {step}")

doc.add_heading("使用前需替换的占位符", level=1)
add_table(
    ["占位符", "所在文件", "说明"],
    [
        [
            "https://github.com/your-org/tekton-argocd-demo.git",
            "两个文件均有",
            "替换为真实 Git 仓库地址",
        ],
        [
            "spec.project: default",
            "application.yaml",
            "若启用 project.yaml，改为 demo",
        ],
    ],
)

out = r"c:\AI-Coding\k8sdevops\docs\argocd-files-guide.docx"
doc.save(out)
print("saved:", out)
