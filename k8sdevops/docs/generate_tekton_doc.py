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


doc.add_heading("Tekton 目录文件说明", level=0)
doc.add_paragraph(
    "本文档说明 tekton/ 目录下各配置文件的作用，以及它们在 CI 流水线中的协作关系。"
)

doc.add_heading("目录结构", level=1)
doc.add_paragraph(
    "tekton/\n"
    "├── namespace.yaml\n"
    "├── rbac.yaml\n"
    "├── pipeline.yaml\n"
    "├── pipelinerun-example.yaml\n"
    "├── triggers.yaml\n"
    "├── secrets.example.yaml\n"
    "└── tasks/\n"
    "    ├── git-clone.yaml\n"
    "    ├── build-push-image.yaml\n"
    "    └── update-manifest.yaml"
)

doc.add_heading("文件一览表", level=1)
add_table(
    ["文件路径", "资源类型", "作用摘要"],
    [
        ["namespace.yaml", "Namespace", "创建 Tekton 流水线专用命名空间"],
        ["rbac.yaml", "ServiceAccount / Role / RoleBinding", "为 Pipeline 运行提供身份与权限"],
        ["pipeline.yaml", "Pipeline", "定义完整 CI 流水线编排"],
        ["pipelinerun-example.yaml", "PipelineRun", "手动触发流水线的示例"],
        [
            "triggers.yaml",
            "EventListener / TriggerBinding / TriggerTemplate",
            "Webhook 自动触发 CI",
        ],
        ["secrets.example.yaml", "Secret（示例）", "Git 与镜像仓库凭据模板"],
        ["tasks/git-clone.yaml", "Task", "克隆代码仓库"],
        ["tasks/build-push-image.yaml", "Task", "构建并推送容器镜像"],
        ["tasks/update-manifest.yaml", "Task", "更新 GitOps 清单并回写 Git"],
    ],
)

doc.add_heading("1. namespace.yaml", level=1)
doc.add_paragraph("作用：创建名为 tekton-pipelines 的 Kubernetes 命名空间。")
doc.add_paragraph(
    "所有 Tekton Pipeline、Task、PipelineRun、Secret 等资源都部署在此命名空间中。",
    style="List Bullet",
)
doc.add_paragraph(
    "将 CI 相关资源与业务应用命名空间（如 demo-app）隔离，便于权限管理与资源清理。",
    style="List Bullet",
)
doc.add_paragraph("关键资源：Namespace / tekton-pipelines")

doc.add_heading("2. rbac.yaml", level=1)
doc.add_paragraph("作用：配置流水线运行所需的身份与 RBAC 权限。")
doc.add_paragraph("包含资源：")
add_table(
    ["资源", "名称", "说明"],
    [
        ["ServiceAccount", "pipeline-sa", "Pipeline 各 Task Pod 使用的服务账号"],
        [
            "Role",
            "pipeline-role",
            "命名空间内权限：访问 Pods、Secrets、ConfigMaps、PVC，以及 Tekton 资源",
        ],
        ["RoleBinding", "pipeline-rolebinding", "将 pipeline-role 绑定到 pipeline-sa"],
    ],
)
doc.add_paragraph(
    "说明：没有正确的 ServiceAccount 与权限，PipelineRun 创建的 Pod 将无法读写工作区、"
    "读取密钥或创建 TaskRun。pipelinerun-example.yaml 与 triggers.yaml 中均指定 "
    "serviceAccountName: pipeline-sa。"
)

doc.add_heading("3. pipeline.yaml", level=1)
doc.add_paragraph("作用：定义名为 demo-app-ci 的完整 CI 流水线编排。")
doc.add_paragraph("输入参数：")
doc.add_paragraph("git-url：源码仓库地址", style="List Bullet")
doc.add_paragraph("git-revision：分支或 commit（默认 main）", style="List Bullet")
doc.add_paragraph("image：目标镜像完整地址（含 tag）", style="List Bullet")
doc.add_paragraph(
    "工作区：shared-workspace — 各 Task 共享的 PVC，用于传递源码与构建产物路径。"
)
doc.add_paragraph(
    "任务顺序：fetch-source (git-clone) → build-image (build-push-image) → "
    "gitops-update (update-manifest)"
)
add_table(
    ["阶段名", "引用 Task", "职责"],
    [
        ["fetch-source", "git-clone", "拉取代码到工作区"],
        ["build-image", "build-push-image", "用 Kaniko 构建并推送镜像"],
        ["gitops-update", "update-manifest", "更新 manifests/deployment.yaml 并 push"],
    ],
)
doc.add_paragraph(
    "说明：Pipeline 本身只是“模板”，不会自动执行；需要通过 PipelineRun 或 Triggers 触发。"
)

doc.add_heading("4. pipelinerun-example.yaml", level=1)
doc.add_paragraph("作用：手动触发 demo-app-ci 流水线的示例配置。")
doc.add_paragraph(
    "使用 generateName: demo-app-ci-run-，每次 kubectl create 会生成唯一名称的 PipelineRun",
    style="List Bullet",
)
doc.add_paragraph("需替换其中的 git-url、image 等占位符为实际值", style="List Bullet")
doc.add_paragraph(
    "通过 volumeClaimTemplate 为共享工作区申请 1Gi PVC", style="List Bullet"
)
doc.add_paragraph("指定 serviceAccountName: pipeline-sa", style="List Bullet")
doc.add_paragraph("使用方式：kubectl create -f tekton/pipelinerun-example.yaml")

doc.add_heading("5. triggers.yaml", level=1)
doc.add_paragraph(
    "作用：配置 Tekton Triggers，使 Git Push（如 GitHub Webhook）自动启动 CI。"
)
doc.add_paragraph("前置条件：需先安装 Tekton Triggers 组件。")
doc.add_paragraph("包含资源：")
add_table(
    ["资源", "名称", "说明"],
    [
        [
            "EventListener",
            "demo-app-listener",
            "接收 HTTP Webhook，匹配 Trigger 并创建 PipelineRun",
        ],
        [
            "TriggerBinding",
            "github-push-binding",
            "从 Webhook JSON 提取 clone_url、after（commit）等字段",
        ],
        [
            "TriggerTemplate",
            "demo-app-trigger-template",
            "根据绑定参数生成 PipelineRun（镜像 tag 使用 commit SHA）",
        ],
    ],
)
doc.add_paragraph(
    "说明：EventListener 会暴露 Service，可将 GitHub Webhook URL 指向该服务，"
    "实现“推送即构建”的自动化 CI。"
)

doc.add_heading("6. secrets.example.yaml", level=1)
doc.add_paragraph(
    "作用：Git 与容器镜像仓库凭据的示例模板（不可直接用于生产）。"
)
add_table(
    ["Secret 名称", "类型", "用途"],
    [
        [
            "git-credentials",
            "kubernetes.io/basic-auth",
            "update-manifest Task push 代码回仓库时认证",
        ],
        [
            "registry-credentials",
            "kubernetes.io/dockerconfigjson",
            "Kaniko 向镜像仓库推送镜像时认证",
        ],
    ],
)
doc.add_paragraph(
    "说明：文件中为占位用户名/密码，需复制为 secrets.yaml，填入真实凭据后再 "
    "kubectl apply。真实凭据文件不应提交到 Git。"
)

doc.add_heading("7. tasks/git-clone.yaml", level=1)
doc.add_paragraph(
    "作用：定义 git-clone Task，从 Git 仓库克隆指定 revision 的源码。"
)
doc.add_paragraph("url：仓库地址", style="List Bullet")
doc.add_paragraph("revision：分支或 commit（默认 main）", style="List Bullet")
doc.add_paragraph(
    "工作区：output — 将代码克隆到 $(workspaces.output.path)/src"
)
doc.add_paragraph("实现：使用 alpine/git 镜像执行 git clone 与 git checkout")
doc.add_paragraph("在流水线中的位置：第一个阶段 fetch-source")

doc.add_heading("8. tasks/build-push-image.yaml", level=1)
doc.add_paragraph(
    "作用：定义 build-push-image Task，使用 Kaniko 构建 Docker 镜像并推送到仓库。"
)
doc.add_paragraph("image：完整目标镜像地址（含 tag）", style="List Bullet")
doc.add_paragraph(
    "dockerfile：Dockerfile 路径（默认 ./Dockerfile）", style="List Bullet"
)
doc.add_paragraph("context：构建上下文路径（默认 .）", style="List Bullet")
doc.add_paragraph("工作区：source — 指向已克隆的源码目录")
doc.add_paragraph(
    "实现：使用 gcr.io/kaniko-project/executor，无需 Docker Daemon，适合在 Kubernetes 中构建"
)
doc.add_paragraph("在流水线中的位置：第二个阶段 build-image（依赖 fetch-source）")

doc.add_heading("9. tasks/update-manifest.yaml", level=1)
doc.add_paragraph(
    "作用：定义 update-manifest Task，更新 GitOps 部署清单并提交推送回 Git。"
)
doc.add_paragraph("主要行为：")
doc.add_paragraph(
    "用 sed 将 manifests/deployment.yaml 中的 image: 更新为新镜像地址",
    style="List Number",
)
doc.add_paragraph("同步更新 APP_VERSION 环境变量为镜像 tag", style="List Number")
doc.add_paragraph(
    "git commit + git push，触发 Argo CD 检测到变更并自动同步部署",
    style="List Number",
)
doc.add_paragraph("参数：image、deployment-file、git-user-email / git-user-name")
doc.add_paragraph(
    "在流水线中的位置：第三个阶段 gitops-update（依赖 build-image）"
)
doc.add_paragraph("说明：这是连接 Tekton CI 与 Argo CD CD 的关键步骤。")

doc.add_heading("协作关系示意", level=1)
doc.add_paragraph(
    "namespace.yaml → 提供命名空间\n"
    "rbac.yaml → 提供 pipeline-sa 权限\n"
    "secrets.example.yaml →（复制后）提供 Git / Registry 凭据\n"
    "tasks/*.yaml → 可复用的原子能力\n"
    "pipeline.yaml → 编排三个 Task 的执行顺序\n"
    "pipelinerun-example.yaml → 手动创建一次运行\n"
    "triggers.yaml → Webhook 自动创建运行"
)
doc.add_paragraph("部署建议顺序：")
for i, step in enumerate(
    [
        "namespace.yaml",
        "rbac.yaml",
        "tasks/ 下全部 Task",
        "pipeline.yaml",
        "（可选）secrets.yaml、triggers.yaml",
        "需要跑 CI 时：kubectl create -f pipelinerun-example.yaml",
    ],
    1,
):
    doc.add_paragraph(f"{i}. {step}")

out = r"c:\AI-Coding\k8sdevops\docs\tekton-files-说明.docx"
doc.save(out)
print("saved:", out)
