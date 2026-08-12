const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, BorderStyle, AlignmentType, LevelFormat } = require('docx');
const fs = require('fs');
const path = require('path');

const border = { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC' };
const borders = { top: border, bottom: border, left: border, right: border };

function cell(text, opts = {}) {
  return new TableCell({
    borders,
    width: { size: opts.width || 2400, type: WidthType.DXA },
    margins: { top: 60, bottom: 60, left: 80, right: 80 },
    children: [
      new Paragraph({
        children: [
          new TextRun({
            text: String(text ?? ''),
            bold: !!opts.bold,
            size: opts.size || 20,
            font: '微软雅黑',
            color: opts.header ? 'FFFFFF' : '1A2B22',
          }),
        ],
      }),
    ],
    shading: opts.header ? { fill: '1F6B4A' } : undefined,
  });
}

function makeTable(headers, rows, widths) {
  const w = widths || headers.map(() => Math.floor(9000 / headers.length));
  return new Table({
    width: { size: 9000, type: WidthType.DXA },
    columnWidths: w,
    rows: [
      new TableRow({
        children: headers.map((h, i) => cell(h, { bold: true, header: true, width: w[i] })),
      }),
      ...rows.map(
        (r) =>
          new TableRow({
            children: r.map((c, i) => cell(c, { width: w[i] })),
          })
      ),
    ],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 160 },
    children: [new TextRun({ text, bold: true, font: '微软雅黑', size: 32, color: '1F6B4A' })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 120 },
    children: [new TextRun({ text, bold: true, font: '微软雅黑', size: 26, color: '1A2B22' })],
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 200, after: 100 },
    children: [new TextRun({ text, bold: true, font: '微软雅黑', size: 22 })],
  });
}
function p(text) {
  return new Paragraph({
    spacing: { after: 100 },
    children: [new TextRun({ text, font: '微软雅黑', size: 21 })],
  });
}
function bullet(text) {
  return new Paragraph({
    numbering: { reference: 'bullets', level: 0 },
    spacing: { after: 60 },
    children: [new TextRun({ text, font: '微软雅黑', size: 21 })],
  });
}
function codeBlock(lines) {
  return lines.map(
    (line) =>
      new Paragraph({
        spacing: { after: 0 },
        children: [new TextRun({ text: line || ' ', font: 'Consolas', size: 16, color: '333333' })],
      })
  );
}

async function main() {
  const doc = new Document({
    styles: {
      default: { document: { styles: [{ id: 'Normal', run: { font: '微软雅黑', size: 21 } }] } },
    },
    numbering: {
      config: [
        {
          reference: 'bullets',
          levels: [
            {
              level: 0,
              format: LevelFormat.BULLET,
              text: '•',
              alignment: AlignmentType.LEFT,
              style: { paragraph: { indent: { left: 420, hanging: 210 } } },
            },
          ],
        },
      ],
    },
    sections: [
      {
        properties: {
          page: { margin: { top: 720, bottom: 720, left: 720, right: 720 } },
        },
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { after: 120 },
            children: [
              new TextRun({ text: 'RecruitOS 招聘管理系统', bold: true, font: '微软雅黑', size: 44, color: '1F6B4A' }),
            ],
          }),
          new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { after: 320 },
            children: [new TextRun({ text: '系统架构文档', bold: true, font: '微软雅黑', size: 36 })],
          }),
          makeTable(
            ['项目', '内容'],
            [
              ['文档版本', 'V2.2'],
              ['编制日期', '2026-08-05'],
              ['系统版本', '2.2.0（一期 + 二期 + HR Agent + 渠道适配/合规闸门）'],
              ['适用范围', '架构设计、开发交接、评审与运维参考'],
            ],
            [2400, 6600]
          ),

          h1('1. 文档说明'),
          h2('1.1 编写目的'),
          p('本文档描述 RecruitOS（recruit-agent）招聘管理系统的总体架构、分层设计、核心数据模型、模块划分、接口边界、安全权限与部署结构，作为研发、测试与后续 HR Agent 集成的共同依据。'),
          h2('1.2 系统定位'),
          p('建设一套 RecruitOS（业务系统）+ HR Agent（AI 能力）协同架构：'),
          bullet('第一阶段：跑通招聘全流程闭环（需求→入职），数据留痕、责任清楚。'),
          bullet('第二阶段：标准化、可配置、可集成；开放受控接口供 HR Agent 读写。'),
          bullet('渠道合规：适配层对接 Boss/猎聘中台；默认 sandbox + 人工确认闸门。'),
          p('HR Agent 负责模型与草稿生成；RecruitOS 负责数据、规则、权限、执行与审计。'),
          h2('1.3 设计原则'),
          makeTable(
            ['原则', '说明'],
            [
              ['流程先完整', '优先保证需求到入职可闭环'],
              ['对象要分清', '候选人主档与应聘记录分离'],
              ['结果有留痕', '推进、淘汰、审批、状态变更均记录操作人/时间/原因'],
              ['AI 与系统解耦', '基础系统执行；Agent 理解、生成、推荐'],
              ['高风险人工确认', '淘汰、发/撤 Offer、渠道发布、外部打招呼等须人工确认'],
            ],
            [2800, 6200]
          ),

          h1('2. 总体架构'),
          h2('2.1 逻辑架构'),
          p('系统自上而下分为：接入层（管理后台、候选人门户、HR Agent、渠道中台）→ API 网关层（JWT/RBAC/CORS）→ 业务服务层（主流程 + 渠道适配/合规闸门 + Agent）→ 领域支撑（待办/审计/事件）→ 数据层（SQLite + 附件）。'),
          ...codeBlock([
            '┌─────────────────────────────────────────────────────┐',
            '│ 接入层：PC后台 / 门户 / HR Agent / Boss·猎聘中台      │',
            '└──────────────────────┬──────────────────────────────┘',
            '                       │ HTTPS / JSON',
            '┌──────────────────────▼──────────────────────────────┐',
            '│ API 网关层：Express + JWT + RBAC + 附件静态服务       │',
            '└──────────────────────┬──────────────────────────────┘',
            '                       │',
            '┌──────────────────────▼──────────────────────────────┐',
            '│ 业务：主流程 │ Agent │ 渠道适配层+合规开关+人工闸门   │',
            '└──────────────────────┬──────────────────────────────┘',
            '                       │ Prisma ORM',
            '┌──────────────────────▼──────────────────────────────┐',
            '│ 数据层：SQLite（可切换 PG） + uploads/ 附件目录        │',
            '└─────────────────────────────────────────────────────┘',
          ]),
          h2('2.2 API 网关层实现说明'),
          p('文档中的「API 网关层」不是独立的 Kong / Nginx Gateway 等产品，而是 Express 应用入口 + 中间件在模块化单体内承担的统一接入职责，与业务路由运行在同一后端进程（backend/src/index.ts + middleware/auth.ts）。'),
          makeTable(
            ['能力', '实现方式'],
            [
              ['统一入口', '业务 API 挂在 /api/*，附件在 /uploads'],
              ['跨域', 'app.use(cors())'],
              ['请求体解析', 'express.json({ limit: 10mb })'],
              ['路由分发', "app.use('/api/xxx', xxxRoutes) 按业务域转发"],
              ['JWT 鉴权', 'authRequired：校验 Bearer Token，查库确认未停用，写入 req.user'],
              ['RBAC', "requireRoles(...); ADMIN 默认放行"],
              ['健康检查', 'GET /api/health'],
              ['统一错误', '末尾 error middleware 返回 { message }'],
              ['静态附件', '/uploads 直接提供文件'],
            ],
            [2400, 6600]
          ),
          p('候选人外链接口（/api/links/portal/:token）不走登录 JWT，靠限时 token 鉴权，仍由同一 Express 应用对外提供。'),
          p('开发态由 Vite 代理将 :5173/api、/uploads 转发到后端 :3001，用于同域开发，不是独立网关服务。'),
          p('小结：当前为 Express 中间件式网关。生产可前置 Nginx/Ingress 做 TLS、限流、负载均衡；Express 继续负责业务鉴权与路由分发。'),
          h2('2.3 技术架构'),
          makeTable(
            ['层次', '技术选型', '说明'],
            [
              ['前端', 'React 18 + TS + Vite + Ant Design 5', 'SPA 管理后台 + 候选人门户'],
              ['后端', 'Node.js + Express 5 + TypeScript', 'REST API（含网关层职责）'],
              ['ORM', 'Prisma 5', '模型驱动、种子数据'],
              ['数据库', 'SQLite（默认）', '本地零配置；生产可换 PostgreSQL'],
              ['认证', 'JWT + bcrypt', 'Bearer Token，默认 7 天'],
              ['图表', 'Recharts', '漏斗与统计可视化'],
            ],
            [1800, 3600, 3600]
          ),
          h2('2.4 部署视图（开发态）'),
          bullet('前端 Vite :5173，通过代理转发 /api、/uploads 至后端 :3001。'),
          bullet('后端 Express 同进程提供网关层职责与业务 API。'),
          bullet('生产建议：Nginx 终止 TLS，同域转发；独立数据库与对象存储。'),

          h1('3. 分层与目录结构'),
          h2('3.1 仓库结构'),
          ...codeBlock([
            'recruit-agent/',
            '├── backend/prisma/schema.prisma',
            '├── backend/src/config/compliance.ts',
            '├── backend/src/channels/{types,adapters,registry,service}.ts',
            '├── backend/src/routes | middleware | utils | seed.ts',
            '├── hr-agent/（AI；寻聘可提交 EXTERNAL_OUTREACH）',
            '├── frontend/src/pages（Channels / Agent 闸门 UI）',
            '├── docs/',
            '└── README.md',
          ]),
          h2('3.2 后端分层职责'),
          makeTable(
            ['层', '职责', '典型文件'],
            [
              ['路由层', '入参校验、编排闸门/适配、返回 JSON', 'routes/*.ts'],
              ['中间件', '鉴权、角色校验', 'middleware/auth.ts'],
              ['合规配置', '渠道模式、开关、凭证校验', 'config/compliance.ts'],
              ['渠道适配', 'Boss/猎聘 sandbox 与 live', 'channels/*'],
              ['支撑工具', '审计、待办、事件、脱敏', 'utils/helpers.ts'],
              ['数据访问', 'Prisma Client', 'prisma.ts + schema'],
            ],
            [2000, 3600, 3400]
          ),
          p('架构形态为模块化单体（Modular Monolith）：单进程按业务域拆分路由，便于后续服务化。'),

          h1('4. 核心业务域与模块'),
          h2('4.1 招聘主流程（一期）'),
          p('招聘需求 → 职位发布 → 简历/候选人 → 筛选 → 面试/评价 → Offer → 待入职 → 入职归档。未录用须以淘汰、放弃或人才库等明确终态结束。'),
          makeTable(
            ['模块', 'API 前缀', '前端路由'],
            [
              ['工作台', '/api/workbench', '/'],
              ['招聘需求', '/api/requests', '/requests'],
              ['职位', '/api/jobs', '/jobs'],
              ['候选人', '/api/candidates', '/candidates'],
              ['应聘/筛选', '/api/applications', '/pipeline'],
              ['面试评价', '/api/interviews', '/interviews'],
              ['Offer', '/api/offers', '/offers'],
              ['待入职', '/api/onboarding', '/onboarding'],
              ['人才库', '/api/talent-pool', '/talent-pool'],
              ['报表', '/api/reports', '/reports'],
              ['配置权限', '/api/config', '/settings'],
              ['认证', '/api/auth', '/login'],
            ],
            [2400, 3300, 3300]
          ),
          h2('4.2 进阶与 Agent 基础（二期）'),
          makeTable(
            ['模块', 'API 前缀', '前端路由'],
            [
              ['岗位标准', '/api/standards', '/standards'],
              ['流程 SLA', '/api/flows', '/flows'],
              ['渠道', '/api/channels', '/channels'],
              ['消息', '/api/messages', '/messages'],
              ['安全链接', '/api/links', '/portal/:token'],
              ['Agent', '/api/agent', '/agent'],
              ['二期综合', '/api/p2', '嵌入各页'],
            ],
            [2400, 3300, 3300]
          ),
          h2('4.3 候选人外链门户'),
          bullet('无内部账号，凭限时 token 访问。'),
          bullet('类型：INTERVIEW_CONFIRM / SLOT_PICK / OFFER_CONFIRM / SUPPLEMENT。'),
          bullet('过期或禁用返回错误；Offer 确认记录设备与 IP，接受后自动创建待入职与协同任务。'),

          h1('5. 数据架构'),
          h2('5.1 核心对象关系'),
          bullet('Organization 1—* User；RecruitRequest 1—* Job 1—* Application *—1 Candidate。'),
          bullet('Application 1—* Interview 1—* InterviewEvaluation；Application 1—* Offer（版本）0..1—Onboarding。'),
          bullet('FlowTemplate 1—* FlowNode；JobStandard / EvalModel 应用到 Job。'),
          bullet('SecureLink 关联候选人/应聘/面试/Offer；AgentDraft / AgentAction / BusinessEvent / SemanticDict。'),
          h2('5.2 关键业务规则'),
          makeTable(
            ['规则', '实现要点'],
            [
              ['BR-001', '流程状态挂在 Application，不挂候选人主档'],
              ['多岗位应聘', '同一候选人多条 Application，状态互不覆盖'],
              ['Offer 版本', '同一时间仅一份 isActive；关键字段变更升版重审'],
              ['评价锁定', '提交后默认不可由他人修改'],
              ['入职回写', '确认入职时更新 Job/Request 已入职人数'],
              ['Agent 高风险', '含 PUBLISH_CHANNEL / EXTERNAL_OUTREACH；PENDING → 确认后执行'],
              ['渠道发布留痕', '确认后写 JobChannelPublish（含 externalRef）'],
              ['外部触达留痕', '确认后写 MessageLog（templateKey=EXTERNAL_OUTREACH）'],
              ['幂等', 'idempotencyKey 唯一，重复请求复用结果'],
            ],
            [2400, 6600]
          ),
          h2('5.3 一期核心实体（节选）'),
          p('User、Organization、RecruitRequest、Job、Candidate、Application、ProcessEvent、Interview、InterviewEvaluation、Offer、Onboarding、Todo、AuditLog、Activity。'),
          h2('5.4 二期扩展实体（节选）'),
          p('JobStandard、EvalModel、FlowTemplate、FlowNode、SlaRule、Channel、JobChannelPublish、SecureLink、MessageLog、WarmTask、OnboardCollabTask、TalentActivation、AgentDraft、AgentAction、BusinessEvent、SemanticDict、HireQualityRecord 等。'),

          h1('6. 接口与集成架构'),
          h2('6.1 内部 API 风格'),
          bullet('HTTP JSON；管理端需 Authorization: Bearer <JWT>。'),
          bullet('成功直接返回业务对象；失败返回 { message } 与相应 HTTP 状态码。'),
          h2('6.2 Agent 接口分级'),
          makeTable(
            ['等级', '示例', '控制'],
            [
              ['读取', '/api/agent/query/*', '继承发起人权限，敏感字段脱敏'],
              ['生成草稿', '/api/agent/drafts', '标记 AI_GENERATED，不直接覆盖正式数据'],
              ['低风险执行', '加标签、建待办', '可自动执行'],
              ['高风险执行', '淘汰、Offer、渠道发布、外部打招呼', '必须人工确认'],
              ['禁止', '绕过审批/合规开关直连外网', '系统层不提供接口'],
            ],
            [2200, 3000, 3800]
          ),
          h2('6.3 外部集成现状'),
          makeTable(
            ['集成对象', '现状', '说明'],
            [
              ['招聘渠道', '适配层+合规+闸门', '默认 sandbox；PUBLISH_CHANNEL / EXTERNAL_OUTREACH'],
              ['消息中心', '模拟 + 外部落库', '外部打招呼写入 MessageLog'],
              ['电子签', '接口预留', '/api/p2/offers/:id/esign'],
              ['日历', '本地忙闲表', '面试同步写入 CalendarBusy'],
              ['基础人事', '入职导出 JSON', '非实时主数据同步'],
            ],
            [2200, 2400, 4400]
          ),
          h2('6.4 渠道适配层与合规闸门'),
          p('设计目标：不直连第三方爬虫；默认 sandbox 安全联调；渠道发布与外部打招呼默认人工确认后执行。'),
          bullet('代码：config/compliance.ts + channels/{types,adapters,registry,service}.ts + routes/channels.ts + agent 确认执行。'),
          bullet('流水线：请求 → 合规校验 → AgentAction PENDING → confirm → Adapter（sandbox/live）→ JobChannelPublish / MessageLog + 审计。'),
          makeTable(
            ['环境变量', '默认', '说明'],
            [
              ['CHANNEL_MODE', 'sandbox', 'sandbox 模拟；live 调外部 API'],
              ['CHANNEL_REQUIRE_HUMAN_CONFIRM', 'true', '发布/触达先进闸门'],
              ['EXTERNAL_OUTREACH_ENABLED', 'false', 'live 外部打招呼总开关'],
              ['CHANNEL_BOSS_ENABLED', 'false', 'live 启用 Boss'],
              ['CHANNEL_LIEPIN_ENABLED', 'false', 'live 启用猎聘'],
              ['CHANNEL_BOSS_API_*', '空', 'Boss 中台 Base/Key'],
              ['CHANNEL_LIEPIN_API_*', '空', '猎聘中台 Base/Key'],
            ],
            [3200, 1600, 4200]
          ),
          makeTable(
            ['接口', '说明'],
            [
              ['GET /api/channels/compliance', '合规快照'],
              ['GET /api/channels/adapters', '适配器健康'],
              ['POST /api/channels/publish', '发布提交，默认 202 进闸门'],
              ['POST /api/channels/outreach/submit', '外部打招呼提交，默认 202'],
              ['POST /api/agent/actions/:id/confirm', '确认并执行适配器'],
            ],
            [4200, 4800]
          ),
          p('Live 约定：Boss POST {BASE}/jobs/publish 与 /messages/greeting；猎聘 POST {BASE}/v1/jobs 与 /v1/chat/greeting；Bearer API Key。'),
          p('前端 /channels、/agent 寻聘；HR Agent POST /ai/sourcing/run 在 submitOutreach=true 时提交 EXTERNAL_OUTREACH，仍须人工确认。'),

          h1('7. 安全与权限架构'),
          h2('7.1 用户分类方式'),
          p('系统内部用户按三维属性管理，以业务角色（role）为主分类：'),
          makeTable(
            ['维度', '字段', '说明'],
            [
              ['业务角色', 'User.role', '决定可操作的功能与接口（主分类）'],
              ['数据范围', 'User.dataScope', '全公司 / 本部门 / 本人负责'],
              ['组织归属', 'User.orgId', '挂在组织树下，用于部门维度与后续隔离'],
            ],
            [2200, 2800, 4000]
          ),
          p('权限控制：后端 requireRoles(...) + 前端 canRole()；ADMIN 默认拥有全部操作权限。'),
          p('候选人不是系统内部用户。二期通过外链 /portal/:token 操作，不占用下述角色，也无内部登录账号。'),
          h2('7.2 业务角色（主分类）'),
          makeTable(
            ['角色代码', '中文名', '演示账号', '主要职责（概要）'],
            [
              ['ADMIN', '系统管理员', 'admin', '组织/账号/角色/模板/字典；全量审计'],
              ['RECRUIT_LEAD', '招聘负责人', 'lead', '审批/关闭需求；分配HR；看数据'],
              ['HR', '招聘HR', 'hr', '维护职位/候选人/面试/Offer；推进流程'],
              ['DEPT_HEAD', '用人部门负责人', 'dept', '发起需求；参与筛选；指定面试官'],
              ['INTERVIEWER', '面试官', 'interviewer', '查看本人面试；提交评价'],
              ['OFFER_APPROVER', 'Offer审批人', 'approver', '审批/驳回Offer'],
              ['HR_OPS', '人事运营', 'ops', '待入职跟进；确认入职与转档'],
              ['DATA_VIEWER', '数据查看人', 'viewer', '看统计；不可看敏感薪酬与联系方式'],
            ],
            [2200, 2200, 1600, 3000]
          ),
          p('种子数据中默认密码均为 123456。'),
          h2('7.3 数据范围（dataScope）'),
          makeTable(
            ['值', '含义', '种子示例'],
            [
              ['ALL', '全公司', 'admin、lead、approver、ops、viewer'],
              ['DEPT', '本部门', 'dept'],
              ['SELF', '本人负责', 'hr、interviewer'],
            ],
            [1800, 2400, 4800]
          ),
          p('字段已建模并随 JWT 下发。当前实现以角色控按钮与接口为主；按 dataScope 的行级数据过滤尚未全面落地，可在后续强化。'),
          h2('7.4 组织归属（orgId）'),
          bullet('用户关联 Organization（如示例科技 → 人力资源部 / 研发中心）。'),
          bullet('用于展示所属部门、需求/职位的组织维度，以及后续「组织范围 + 角色 + 本人负责」数据权限。'),
          h2('7.5 控制点'),
          bullet('认证：登录签发 JWT（默认 7 天）；停用账号拒绝访问。'),
          bullet('授权：requireRoles；ADMIN 默认放行。'),
          bullet('字段脱敏：数据查看人/面试官等对手机、邮箱、薪酬脱敏。'),
          bullet('审计：敏感操作写入 AuditLog；渠道外部动作另写发布记录/消息日志。'),
          bullet('渠道合规：sandbox/live、渠道启用、外部触达总开关；默认人工确认。'),
          bullet('外链：限时 token、类型校验、可作废。'),

          h1('8. 前端架构'),
          bullet('路由：React Router；PrivateRoute 保护管理端；公开 /portal/:token 与 /login。'),
          bullet('状态：LocalStorage 保存 token/user；axios 注入 Header，401 跳转登录。'),
          bullet('UI：Ant Design，主题色 #1F6B4A；侧栏业务菜单。'),
          bullet('权限展示：canRole() 控制按钮；后端仍强制校验。'),
          bullet('渠道页 /channels：合规状态、适配器健康、待确认闸门。'),
          bullet('Agent 寻聘：可选渠道并提交外部打招呼进入闸门。'),

          h1('9. 横切能力'),
          makeTable(
            ['能力', '机制'],
            [
              ['待办', 'Todo + 业务节点创建/完成'],
              ['操作审计', 'writeAudit → AuditLog'],
              ['最近动态', 'Activity'],
              ['流程时间轴', 'ProcessEvent（统计不覆盖历史）'],
              ['业务事件', 'emitBusinessEvent'],
              ['附件', 'multer → uploads/'],
              ['SLA 预警', '巡检写 AlertEvent 并可催办'],
            ],
            [2400, 6600]
          ),

          h1('10. 非功能需求对照'),
          makeTable(
            ['类别', '目标/现状'],
            [
              ['性能', '列表/详情常规 2s 内（本地开发态）'],
              ['容量参考', '≥10 万候选人、30 万应聘、约 50 并发'],
              ['安全', '部署侧 TLS；密码哈希；审计'],
              ['兼容性', 'Chromium 近两主版本；1440×900+'],
              ['备份', '业务库与附件关联恢复（上线前确认流程）'],
            ],
            [2400, 6600]
          ),

          h1('11. 演进路线'),
          bullet('已完成一期：全流程闭环、角色权限、基础报表、审计。'),
          bullet('已完成二期（可运行）：标准/流程/外链/消息/Agent 受控面/进阶分析。'),
          bullet('已完成渠道合规链路：适配层（Boss/猎聘 sandbox+live 骨架）+ 合规开关 + 人工闸门 + 寻聘提交触达。'),
          bullet('后续建议：按真实渠道中台字段对齐 live 映射、人事主数据、PostgreSQL 与对象存储、dataScope 行级加固、事件 Webhook。'),

          h1('12. 附录'),
          h2('12.1 演示账号'),
          p('密码均为 123456。'),
          makeTable(
            ['用户名', '角色', '数据范围', '组织（种子）'],
            [
              ['admin', '系统管理员', 'ALL', '人力资源部'],
              ['lead', '招聘负责人', 'ALL', '人力资源部'],
              ['hr', '招聘HR', 'SELF', '人力资源部'],
              ['dept', '用人部门负责人', 'DEPT', '研发中心'],
              ['interviewer', '面试官', 'SELF', '研发中心'],
              ['approver', 'Offer审批人', 'ALL', '人力资源部'],
              ['ops', '人事运营', 'ALL', '人力资源部'],
              ['viewer', '数据查看人', 'ALL', '示例科技有限公司（根）'],
            ],
            [1800, 2600, 1600, 3000]
          ),
          h2('12.2 本地启动'),
          ...codeBlock([
            'npm run setup',
            'npm run dev:backend   # :3001',
            'npm run dev:hr-agent  # :3002',
            'npm run dev:frontend  # :5173',
          ]),
          h2('12.3 相关文档'),
          bullet('《招聘管理系统需求说明书 V1.0》'),
          bullet('仓库 README.md'),
          bullet('Markdown 版：docs/系统架构文档.md'),
          new Paragraph({
            spacing: { before: 400 },
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ text: '— 文档结束 —', font: '微软雅黑', size: 20, color: '666666' })],
          }),
        ],
      },
    ],
  });

  const out = path.join(__dirname, '..', 'docs', '系统架构文档.docx');
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(out, buffer);
  console.log('Wrote', out);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
