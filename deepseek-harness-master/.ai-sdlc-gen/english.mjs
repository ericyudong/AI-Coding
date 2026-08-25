/**
 * Generate English + Chinese Word docs about Anthropic's AI-Native SDLC Playbook.
 * Reuses jszip from harness's pnpm store; no external install needed.
 */
import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const JSZip = require('/Users/yudong/AI-Coding/deepseek-harness-master/node_modules/.pnpm/jszip@3.10.1/node_modules/jszip');

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_EN = resolve(__dirname, '..', 'ai-native-sdlc-playbook-en.docx');
const OUT_ZH = resolve(__dirname, '..', 'ai-native-sdlc-playbook-zh.docx');

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
const PAGE_W = 11906, PAGE_H = 16838, MARGIN = 1440;

const STYLES_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="Calibri" w:eastAsia="PingFang SC" w:hAnsi="Calibri"/>
      <w:sz w:val="22"/><w:szCs w:val="22"/>
      <w:lang w:val="en-US" w:eastAsia="zh-CN"/>
    </w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="288" w:lineRule="auto"/></w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:styleId="DocTitle"><w:name w:val="DocTitle"/>
    <w:pPr><w:spacing w:before="0" w:after="160"/><w:jc w:val="left"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="44"/><w:szCs w:val="44"/><w:color w:val="0F172A"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/>
    <w:pPr><w:spacing w:before="0" w:after="280"/></w:pPr>
    <w:rPr><w:i/><w:sz w:val="22"/><w:szCs w:val="22"/><w:color w:val="475569"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>
    <w:pPr><w:spacing w:before="320" w:after="140"/><w:pBdr><w:bottom w:val="single" w:sz="8" w:space="4" w:color="3B82F6"/></w:pBdr></w:pPr>
    <w:rPr><w:b/><w:sz w:val="30"/><w:szCs w:val="30"/><w:color w:val="0F172A"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>
    <w:pPr><w:spacing w:before="200" w:after="100"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/><w:color w:val="1E40AF"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="BodyText"><w:name w:val="Body Text"/>
    <w:rPr><w:sz w:val="22"/><w:szCs w:val="22"/><w:color w:val="334155"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Bullet"><w:name w:val="Bullet"/>
    <w:pPr><w:numPr><w:numId w:val="1"/></w:numPr><w:spacing w:after="80" w:line="288" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:sz w:val="22"/><w:szCs w:val="22"/><w:color w:val="334155"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Callout"><w:name w:val="Callout"/>
    <w:pPr><w:shd w:val="clear" w:color="auto" w:fill="EFF6FF"/><w:spacing w:before="120" w:after="160"/><w:ind w:left="360" w:right="360"/></w:pPr>
    <w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/><w:color w:val="1E40AF"/></w:rPr>
  </w:style>
</w:styles>`;

const NUMBERING_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/>
      <w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr></w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>`;

function pStyle(id, text) {
  return `<w:p><w:pPr><w:pStyle w:val="${id}"/></w:pPr><w:r><w:t xml:space="preserve">${esc(text)}</w:t></w:r></w:p>`;
}
function pBullet(text) { return pStyle('Bullet', text); }
function pCallout(text) { return pStyle('Callout', text); }
function pBody(text) { return pStyle('BodyText', text); }

function pTable(headers, rows, colW) {
  const headers_xml = headers.map((c, i) =>
    `<w:tc><w:tcPr><w:tcW w:w="${colW[i]}" w:type="dxa"/>
      <w:shd w:val="clear" w:color="auto" w:fill="1E40AF"/>
      <w:tcBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
      <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
      <w:left w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
      <w:right w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/></w:tcBorders></w:tcPr>
      <w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr>
      <w:r><w:rPr><w:b/><w:sz w:val="20"/><w:color w:val="FFFFFF"/>
      <w:rFonts w:ascii="Calibri" w:eastAsia="PingFang SC" w:hAnsi="Calibri"/></w:rPr>
      <w:t xml:space="preserve">${esc(c)}</w:t></w:r></w:p></w:tc>`).join('');
  const rows_xml = rows.map((row, ri) => row.map((c, i) =>
    `<w:tc><w:tcPr><w:tcW w:w="${colW[i]}" w:type="dxa"/>
      <w:shd w:val="clear" w:color="auto" w:fill="${ri % 2 === 0 ? 'F1F5F9' : 'FFFFFF'}"/>
      <w:tcBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
      <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
      <w:left w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
      <w:right w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/></w:tcBorders></w:tcPr>
      <w:p><w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr>
      <w:r><w:rPr><w:sz w:val="20"/><w:color w:val="334155"/>
      <w:rFonts w:ascii="Calibri" w:eastAsia="PingFang SC" w:hAnsi="Calibri"/></w:rPr>
      <w:t xml:space="preserve">${esc(c)}</w:t></w:r></w:p></w:tc>`).join('')).map(tcs => `<w:tr>${tcs}</w:tr>`).join('');

  const totalW = colW.reduce((a,b)=>a+b,0);
  return `<w:tbl><w:tblPr><w:tblW w:w="${totalW}" w:type="dxa"/><w:tblLayout w:type="fixed"/>
    <w:tblCellMar><w:top w:w="60" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>
    <w:bottom w:w="60" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tblCellMar></w:tblPr>
    <w:tblGrid>${colW.map(w => `<w:gridCol w:w="${w}"/>`).join('')}</w:tblGrid>
    <w:tr>${headers_xml}</w:tr>${rows_xml}</w:tbl>`;
}

// === ENGLISH SECTIONS ===
const enSections = [
  { t: 'DocTitle', v: 'The AI-Native SDLC Playbook' },
  { t: 'Subtitle', v: 'Summary of Anthropic\'s internal playbook for reimagining the SDLC around agentic AI' },
  { t: 'Callout', v: 'Source: Claude by Anthropic — Anthropic\'s Applied AI team published a practical playbook for reshaping every stage from Plan to Maintain around Claude Code.' },

  { t: 'H1', v: 'Executive Summary' },
  { t: 'Body', v: 'Anthropic assumes that code generation is no longer the bottleneck. With Claude authoring roughly 80% of code changes inside the company, the friction has moved upstream (intent, design) and downstream (review, verification, governance). The playbook reorganizes the lifecycle around six stages, connected by a chain of markdown artifacts rather than meetings, governed by four durable control mechanisms.' },
  { t: 'Body', v: 'Target audience: not individual developers, but engineering organizations that must answer to audit, compliance, and operations. The model is heavy: skills and hooks require dedicated owners, eval suites cost ongoing inference, and the payoff usually takes several quarters to materialize.' },

  { t: 'H1', v: 'Core Thesis: Artifact Chain, Not Meetings' },
  { t: 'Body', v: 'The lifecycle is a chain of single artifacts. Each stage commits one file that the next stage reads:' },
  { t: 'Bullet', v: 'Plan → intent.md (problem, users, constraints)' },
  { t: 'Bullet', v: 'Design → spec.md (UX, security, policy checks)' },
  { t: 'Bullet', v: 'Build → plan.md (implementation plan, then code)' },
  { t: 'Bullet', v: 'Test → continuous evaluation, not a stage gate' },
  { t: 'Bullet', v: 'Deploy → layered automated review + hooks' },
  { t: 'Bullet', v: 'Maintain → anomaly detection writes a new intent.md, closing the loop' },
  { t: 'Callout', v: 'Single commitment per stage: each handoff produces one file that the next stage consumes.' },

  { t: 'H1', v: 'The Six Stages' },
  { t: 'H2', v: '1. Plan — intent.md' },
  { t: 'Body', v: 'Replace requirement meetings and hand-written docs with a structured conversation with Claude. Output: intent.md that captures problem, users, and constraints. The playbook claims cycle time compresses from weeks to hours. The artifact must be reviewed and approved by the product owner before it moves downstream.' },
  { t: 'H2', v: '2. Design — spec.md' },
  { t: 'Body', v: 'Apply UX and security skills (e.g., secure-api-review) in a single Claude session to produce spec.md. Run policy checks before leaving the stage. Constraints (rate limits, PII handling, auth scheme) are written into the spec so the implementation stage cannot accidentally violate them.' },
  { t: 'H2', v: '3. Build — plan.md then code' },
  { t: 'Body', v: 'Enter plan mode, generate plan.md, then exit and let Claude Code implement. Review hooks gate the PR merge. Teams encode hard constraints in their plan.md: e.g., a payments team pins Java 21, Spring Boot 3, forbids Lombok, requires BigDecimal for money, and freezes dependency versions managed by the platform team.' },
  { t: 'H2', v: '4. Test — continuous, not a gate' },
  { t: 'Body', v: 'Evaluation lives inside the build process, not at a stage boundary. An eval suite of 20–50 real tasks runs on every config change plus a nightly job. Every production incident gets distilled into a permanent eval; pass rate is a merge condition.' },
  { t: 'H2', v: '5. Deploy — layered review + hooks' },
  { t: 'Body', v: 'Replace manual sign-off with deterministic hooks. Examples: block edits to frozen dependencies and force formatting in build; require release-manager authorization in production deploys (exit 2 blocks unauthorized pushes). Hooks are non-bypassable control points.' },
  { t: 'H2', v: '6. Maintain — anomaly detection → new intent' },
  { t: 'Body', v: 'Maintenance is not reactive paging. Anomaly detection is deterministic (Western Electric rules, not the model). Escalation thresholds: 1σ just logs; 2σ grants Claude read-only diagnostic access; 3σ allows it to open a PR or trigger a pre-approved runbook. The detected anomaly itself becomes a new intent.md, closing the loop.' },

  { t: 'H1', v: 'The Four Governance Mechanisms' },
  { t: 'Table', headers: ['Mechanism', 'Role', 'Example'],
    rows: [
      ['Skills', 'Encode institutional knowledge under .claude/skills/. Change centrally once; every session picks it up.', 'secure-api-review checks auth, input validation, audit logging.'],
      ['Hooks', 'Deterministic, non-bypassable controls.', 'Block edits to frozen deps, force format; require release-manager auth for prod deploys.'],
      ['CLAUDE.md', 'One-page team memory: build commands, conventions, architecture, recurring mistakes.', 'Rule: when the same mistake recurs a second time, write it in.'],
      ['Evals', '20–50 real tasks as regression suite; run on config change + nightly.', 'Each prod incident becomes a permanent eval; pass rate is a merge gate.'],
    ], colW: [1700, 4400, 3000] },

  { t: 'H1', v: 'Case: Self-Service Claims Status' },
  { t: 'Body', v: 'Operations writes intent.md describing the problem, users, and constraints. The product owner approves. Claude applies UX and security skills to produce spec.md. An engineer enters plan mode, receives plan.md (with explicit constraints: claims-core is capped at 50 rps so caching is required; no PII may be added in conversation; auth reuses the existing scheme). Claude Code implements, the PR passes review hooks, and the change ships.' },
  { t: 'Body', v: 'A payments team\'s CLAUDE.md pins Java 21, Spring Boot 3, forbids Lombok, requires BigDecimal for money, and freezes platform-managed dependency versions. The constraints surface in code review automatically, not in memory.' },

  { t: 'H1', v: 'Metrics: Leading and Lagging' },
  { t: 'Table', headers: ['Type', 'Metric'],
    rows: [
      ['Leading', 'First chat → intent.md submitted'],
      ['Leading', 'intent.md submitted → first review'],
      ['Leading', 'Concurrent agent sessions'],
      ['Leading', 'CI pass rate'],
      ['Lagging', 'intent.md approval rate'],
      ['Lagging', 'First-implementation pass rate'],
      ['Lagging', 'Trend in PR review findings'],
      ['Lagging', 'Recurrence rate of production incidents'],
      ['Lagging', 'PRs merged per engineer per week'],
    ], colW: [1800, 7300] },

  { t: 'H1', v: 'Compliance Paths' },
  { t: 'Body', v: 'Path A treats Jira or ServiceNow as the authoritative record with markdown as a working copy, synced back via MCP connectors. Path B makes the repository the single source of truth and lets legacy systems reference commit SHAs. Audit trails stitch together Git history, PR threads, OpenTelemetry-exported agent behavior, and hook allow/deny logs.' },

  { t: 'H1', v: 'Key Takeaways' },
  { t: 'Bullet', v: 'Shift the bottleneck from code generation to intent, design, and governance.' },
  { t: 'Bullet', v: 'Replace meetings with an artifact chain: intent.md → spec.md → plan.md → PR → telemetry → new intent.' },
  { t: 'Bullet', v: 'Make evaluation continuous and tied to merge gates, not a final phase.' },
  { t: 'Bullet', v: 'Treat governance (skills, hooks, CLAUDE.md, evals) as durable code with dedicated owners.' },
  { t: 'Bullet', v: 'Use deterministic thresholds for escalation; let the model advise but not decide.' },
  { t: 'Bullet', v: 'This is a multi-quarter investment. The playbooks fits organizations willing to fund audit-grade traceability, not casual teams.' },
];

// === CHINESE SECTIONS ===
const zhSections = [
  { t: 'DocTitle', v: 'AI 原生 SDLC 实战手册（中文摘要）' },
  { t: 'Subtitle', v: '基于 Anthropic 公开的内部开发流程手册整理' },
  { t: 'Callout', v: '原文：Claude by Anthropic — The AI-Native SDLC Playbook，Anthropic Applied AI 团队发布的工程实践手册。' },

  { t: 'H1', v: '一句话核心观点' },
  { t: 'Body', v: 'Anthropic 内部 Claude 已编写约 80% 的代码改动，传统按"人手写代码"速度设计的 SDLC 卡点位置已经变了——瓶颈从代码生成上移到了需求与设计，下移到了评审、验证与治理。手册把整条生命周期拆成六个阶段，用四件治理件串起来，运行基础是一连串 markdown 工件而非会议。' },
  { t: 'Body', v: '读者画像：不是个人开发者，而是必须向审计、合规、运营交代的工程组织。模型很重——skills 与 hooks 需要专人维护，评估集有常年推理开销，收益往往要几个季度才显形。中型公司通常推不动这类改造；愿意为审计线索付费的组织，才是真正瞄准的客户。' },

  { t: 'H1', v: '核心论点：工件链而非会议' },
  { t: 'Body', v: '生命周期是一条"单工件"的链条，每个阶段提交一个文件，供下一阶段读取：' },
  { t: 'Bullet', v: '规划 → intent.md（问题、用户、约束）' },
  { t: 'Bullet', v: '设计 → spec.md（UX、安全、策略检查）' },
  { t: 'Bullet', v: '构建 → plan.md（先出计划再实现）' },
  { t: 'Bullet', v: '测试 → 持续评估，不是阶段关卡' },
  { t: 'Bullet', v: '部署 → 分层自动评审 + Hook 把关' },
  { t: 'Bullet', v: '维护 → 异常检测后写新的 intent.md，回到起点' },
  { t: 'Callout', v: '每阶段提交一件工件，供下一阶段读取。' },

  { t: 'H1', v: '六个阶段详解' },
  { t: 'H2', v: '1. 规划 — intent.md' },
  { t: 'Body', v: '用一次结构化的 Claude 对话取代需求评审会和手写文档，产出 intent.md：问题、用户、约束。手册声称周期从"数周"压到"数小时"。产物必须由产品负责人审查批准后才能进入下一阶段。' },
  { t: 'H2', v: '2. 设计 — spec.md' },
  { t: 'Body', v: '在一次 Claude 会话中应用 UX 与安全 skills（如 secure-api-review），产出 spec.md。离场前跑策略检查。约束（限流、PII 处理、认证方案）显式写入 spec，实现阶段无法无意识地违反。' },
  { t: 'H2', v: '3. 构建 — plan.md → 代码' },
  { t: 'Body', v: '进入 plan mode 拿到 plan.md，再退出让 Claude Code 实现。Review hook 守住 PR 合并关。团队把硬约束写进 plan.md：例如某支付团队锁死 Java 21、Spring Boot 3、禁用 Lombok、金额必须 BigDecimal，依赖版本由平台团队统一管理不得擅改。' },
  { t: 'H2', v: '4. 测试 — 持续评估，非阶段关卡' },
  { t: 'Body', v: '评估嵌入实现过程，不是阶段边界。20–50 个真实任务组成评估集，配置变更触发 + 每晚一轮。每次生产事故固化为一条永久 eval，通过率直接作为合并条件。' },
  { t: 'H2', v: '5. 部署 — 分层评审 + Hook' },
  { t: 'Body', v: '用确定性 Hook 取代人工审批。示例：构建阶段拦住对冻结依赖包的编辑、强制跑格式化；生产发布需要 release manager 授权，未授权直接 exit 2 阻断。Hook 是不可绕过的控制点。' },
  { t: 'H2', v: '6. 维护 — 异常检测 → 新 intent' },
  { t: 'Body', v: '维护不是被动响应告警。异常检测是确定性的（Western Electric 规则，不交给模型）。三档阈值：1σ 只记录，2σ 授予 Claude 只读诊断权限，3σ 才允许它开 PR 或触发预先批准的 runbook。异常本身成为新的 intent.md，闭环回到规划阶段。' },

  { t: 'H1', v: '四件治理件' },
  { t: 'Table', headers: ['治理件', '作用', '示例'],
    rows: [
      ['Skills', '把制度化知识写进 .claude/skills/，中央改一次，所有会话自动拿到新版。', 'secure-api-review：盯认证、入参校验、审计日志。'],
      ['Hooks', '确定性控制，没有人工绕行路径。', '构建阶段拦截冻结依赖编辑、强制格式化；部署阶段要求 release manager 授权。'],
      ['CLAUDE.md', '一页团队记忆：构建命令、约定、架构、常犯的错。', '维护规则：同一个错犯到第二次就写进去。'],
      ['Evals', '20–50 个真实任务当回归集；配置变更加每晚定时跑。', '每次生产事故固化为永久 eval，通过率是合并条件。'],
    ], colW: [1700, 4400, 3000] },

  { t: 'H1', v: '案例：理赔状态自助查询' },
  { t: 'Body', v: '运营先写 intent.md 说清问题、用户、约束，产品负责人审查批准后进入设计阶段；Claude 应用 UX 与安全 skills 生成 spec.md；工程师进入 plan mode 拿到 plan.md，约束已显式写入（claims-core 接口限 50 rps 所以需要缓存；会话中不得新增 PII；认证走既有方案）；Claude Code 实现，PR 过 review hook 后合并。' },
  { t: 'Body', v: '某支付团队的 CLAUDE.md 写着 Java 21、Spring Boot 3、禁用 Lombok、金额必须 BigDecimal、依赖版本由平台团队管不许动——这些约束自动出现在 code review 里，而不是靠人记。' },

  { t: 'H1', v: '指标清单：前置 vs 滞后' },
  { t: 'Table', headers: ['类型', '指标'],
    rows: [
      ['前置', '首次对话 → 提交 intent.md 的时长'],
      ['前置', '提交 → 首次审查的时长'],
      ['前置', '并发 agent 会话数'],
      ['前置', 'CI 通过率'],
      ['滞后', 'intent.md 通过率'],
      ['滞后', '首次实现通过率'],
      ['滞后', 'PR 审查发现数趋势'],
      ['滞后', '生产事件重复率'],
      ['滞后', '每工程师每周合并 PR 数'],
    ], colW: [1800, 7300] },

  { t: 'H1', v: '合规路径' },
  { t: 'Body', v: '路径 A：把 Jira 或 ServiceNow 当权威记录，markdown 当工作副本，通过 MCP 连接器同步回旧系统。路径 B：以仓库为唯一事实源，旧系统只引用 commit SHA。审计线索靠 Git 历史、PR 线程、OpenTelemetry 导出的 agent 行为记录、Hook 的放行/阻断日志四路拼齐。' },

  { t: 'H1', v: '关键启示' },
  { t: 'Bullet', v: '瓶颈从"写代码"上移到需求与设计、下移到评审与治理。' },
  { t: 'Bullet', v: '用工件链（intent.md → spec.md → plan.md → PR → 事件 → 新 intent）取代会议驱动。' },
  { t: 'Bullet', v: '把评估做成持续的、绑定到合并门的工序，不是末端关卡。' },
  { t: 'Bullet', v: '把治理件（skills / hooks / CLAUDE.md / evals）当作长期维护的代码，配专人。' },
  { t: 'Bullet', v: '升级阈值用确定性规则，模型只做建议不替决策。' },
  { t: 'Bullet', v: '这是一项多季度投入，适合愿意为审计级可追溯性付费的组织，而非个人或小团队。' },
];

function buildBody(sections) {
  return sections.map(s => {
    if (s.t === 'DocTitle' || s.t === 'Subtitle' || s.t === 'Callout' ||
        s.t === 'H1' || s.t === 'H2' || s.t === 'Body' || s.t === 'Bullet') {
      return pStyle(s.t, s.v);
    }
    if (s.t === 'Table') {
      return pTable(s.headers, s.rows, s.colW);
    }
    return '';
  }).join('\n');
}

const DOCUMENT_TEMPLATE = (body) => `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>${body}
    <w:sectPr>
      <w:pgSz w:w="${PAGE_W}" w:h="${PAGE_H}"/>
      <w:pgMar w:top="${MARGIN}" w:right="${MARGIN}" w:bottom="${MARGIN}" w:left="${MARGIN}" w:header="720" w:footer="720"/>
    </w:sectPr>
  </w:body>
</w:document>`;

const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>`;

const RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`;

const DOC_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>`;

const SETTINGS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:defaultTabStop w:val="720"/>
  <w:compat><w:useFELayout/></w:compat>
</w:settings>`;

async function buildDocx(outPath, sections) {
  const zip = new JSZip();
  zip.file('[Content_Types].xml', CONTENT_TYPES);
  zip.folder('_rels').file('.rels', RELS);
  const word = zip.folder('word');
  word.file('document.xml', DOCUMENT_TEMPLATE(buildBody(sections)));
  word.file('styles.xml', STYLES_XML);
  word.file('numbering.xml', NUMBERING_XML);
  word.file('settings.xml', SETTINGS);
  word.folder('_rels').file('document.xml.rels', DOC_RELS);
  const buf = await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });
  writeFileSync(outPath, buf);
  console.log(`✅ ${outPath} (${(buf.length / 1024).toFixed(1)} KB)`);
}

async function main() {
  await buildDocx(OUT_EN, enSections);
  await buildDocx(OUT_ZH, zhSections);
}

main().catch(err => { console.error(err); process.exit(1); });