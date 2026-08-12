const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  Table,
  TableRow,
  TableCell,
  WidthType,
  BorderStyle,
  AlignmentType,
  LevelFormat,
} = require('docx');
const fs = require('fs');
const path = require('path');

const border = { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC' };
const borders = { top: border, bottom: border, left: border, right: border };

function cell(text, opts = {}) {
  return new TableCell({
    borders,
    width: { size: opts.width || 2400, type: WidthType.DXA },
    margins: { top: 60, bottom: 60, left: 80, right: 80 },
    shading: opts.header ? { fill: '1F6B4A' } : undefined,
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
              new TextRun({ text: 'RecruitOS · HR Agent', bold: true, font: '微软雅黑', size: 44, color: '1F6B4A' }),
            ],
          }),
          new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { after: 320 },
            children: [new TextRun({ text: '说明文档', bold: true, font: '微软雅黑', size: 36 })],
          }),
          makeTable(
            ['项目', '内容'],
            [
              ['文档版本', 'V1.0'],
              ['编制日期', '2026-08-06'],
              ['服务版本', 'hr-agent 1.0.0'],
              ['默认端口', '3002'],
              ['代码目录', 'hr-agent/'],
              ['适用范围', '能力说明、接口约定、联调运维、与 RecruitOS 边界'],
            ],
            [2400, 6600]
          ),

          h1('1. 文档说明'),
          h2('1.1 编写目的'),
          p('本文档基于当前仓库 hr-agent/ 实现，说明 HR Agent 的定位、架构、技能清单、接口、鉴权、LLM 降级策略以及与 RecruitOS 的协作方式。'),
          h2('1.2 系统定位'),
          p('HR Agent 是 RecruitOS 的 AI 能力侧车服务：负责理解、生成、推荐与草稿；RecruitOS 负责数据、规则、权限、执行与人工确认。'),
          makeTable(
            ['组件', '负责', '不负责'],
            [
              ['HR Agent', '模型调用、提示、草稿/建议、工具回调编排', '无确认的高风险终态执行'],
              ['RecruitOS', '数据、权限、审计、闸门与业务写库', '模型选型与提示词工程'],
            ],
            [2000, 3500, 3500]
          ),
          ...codeBlock([
            '前端 --JWT--> RecruitOS :3001 --代理--> HR Agent :3002',
            '                 ▲                         |',
            '                 └──── 工具回调（同一 JWT）────┘',
            '                               |',
            '                         LLM 网关 / Mock',
          ]),
          h2('1.3 设计原则'),
          bullet('AI 与执行解耦：草稿与建议由 Agent 产出，正式执行在 RecruitOS。'),
          bullet('用户身份透传：全程业务 JWT，权限与审计归属真实操作人。'),
          bullet('可离线演示：无 API Key 时 mock，业务不断流。'),
          bullet('高风险不下放：淘汰、发 Offer、外部触达须闸门/人工确认。'),

          h1('2. 总体架构'),
          h2('2.1 逻辑与代码'),
          p('Express 入口（index.ts）→ skills.ts 技能编排 → llm.ts 模型调用 → recruitos.ts 回调业务 API。'),
          ...codeBlock([
            'hr-agent/src/',
            '├── index.ts      # 路由与 /health /ai/capabilities',
            '├── config.ts     # PORT / RECRUITOS / OPENAI_*',
            '├── llm.ts        # chatCompletion / chatOrMock',
            '├── recruitos.ts  # JWT 回调客户端',
            '└── skills.ts     # 全部 AI 技能',
          ]),
          makeTable(
            ['项', '选型'],
            [
              ['运行时', 'Node.js + TypeScript（tsx / tsc）'],
              ['HTTP', 'Express 5 + CORS'],
              ['LLM', 'OpenAI 兼容 chat/completions'],
            ],
            [2400, 6600]
          ),

          h1('3. 与 RecruitOS 集成'),
          bullet('RecruitOS → HR Agent：HR_AGENT_URL，默认 http://127.0.0.1:3002，代理超时约 120s。'),
          bullet('HR Agent → RecruitOS：RECRUITOS_BASE_URL，默认 http://127.0.0.1:3001，透传 JWT。'),
          bullet('常用回调：/api/agent/query、/api/agent/drafts、/api/agent/actions、报表与渠道 outreach。'),
          p('路径对照：RecruitOS /api/ai/* 对应 HR Agent /ai/*（如 /api/ai/jd/generate ↔ /ai/jd/generate）。'),

          h1('4. LLM 层'),
          bullet('有 OPENAI_API_KEY 则走真实网关；否则全部 mock（provider=mock）。'),
          bullet('超时 LLM_TIMEOUT_MS（默认 90s）；对 429/502/504/超时可重试。'),
          bullet('chatOrMock：LLM 失败降级 mock；safeJsonParse 剥离 markdown 后解析。'),
          bullet('多数响应含 provider 与可选 draft（AgentDraft）。'),

          h1('5. 技能能力清单'),
          makeTable(
            ['key', '名称', '接口'],
            [
              ['jd', 'JD 生成', 'POST /ai/jd/generate'],
              ['publish', '多渠道文案', 'POST /ai/jd/publish-pack'],
              ['sourcing', 'AI 寻聘', 'POST /ai/sourcing/run'],
              ['resume', '解析/初筛', 'POST /ai/resume/parse|/screen'],
              ['talent', '人才库推荐', 'POST /ai/talent/recommend'],
              ['schedule', '面试排期', 'POST /ai/interview/schedule-assist'],
              ['ai_interview', '多模态测评(文本增强)', 'POST /ai/interview/multimodal-assess'],
              ['eval', '评价汇总', 'POST /ai/interview/summary'],
              ['nurture', '候选人沟通', 'POST /ai/nurture/reply'],
              ['offer', 'Offer 草稿', 'POST /ai/offer/draft'],
              ['analytics', '数据分析', 'POST /ai/analytics/ask'],
              ['chat', '通用对话', 'POST /ai/chat'],
            ],
            [1800, 3200, 4000]
          ),

          h2('5.1 技能要点'),
          h3('JD 生成'),
          p('入参 jobId/requestId/brief；输出市场风格 externalJd + 内部版；默认落 AgentDraft type=JD。'),
          h3('多渠道文案'),
          p('jobId 必填；默认渠道 BOSS/LIEPIN/INTERNAL/REFERRAL；输出 packs 数组。'),
          h3('寻聘助手'),
          p('站内挑名单与话术。submitOutreach=true 时提交 /api/channels/outreach/submit，进入 EXTERNAL_OUTREACH 人工闸门，不直连外部爬虫。'),
          h3('简历解析与初筛'),
          p('解析结构化字段并可 apply-parse 回写；初筛输出 score/level/reasons，并结合重复投递风险。'),
          h3('人才推荐 / 排期 / 评价 / 多模态'),
          p('推荐生成激活话术；排期给候选时段与沟通文案；评价与多模态仅辅助决策，decisionBoundary 强调人工终裁。'),
          h3('沟通 / Offer / 分析 / 对话'),
          p('nurture 不编造；Offer 仅草稿且标明发送须确认；analytics 基于报表；chat 含轻量意图路由到上述技能。'),

          h1('6. HTTP 接口'),
          h2('6.1 公共约定'),
          bullet('Base: http://127.0.0.1:3002；JSON；业务接口需 Bearer JWT。'),
          bullet('失败返回 { message } 与 401/400/500。'),
          h2('6.2 运维'),
          p('GET /health：ok、version、llm(openai-compatible|mock)、recruitos。'),
          p('GET /ai/capabilities：能力清单。'),
          h2('6.3 必填字段摘要'),
          makeTable(
            ['接口', '必填'],
            [
              ['/ai/jd/publish-pack', 'jobId'],
              ['/ai/resume/parse', 'candidateId'],
              ['/ai/resume/screen', 'candidateId + jobId'],
              ['/ai/talent/recommend、/ai/sourcing/run', 'jobId'],
              ['/ai/interview/summary、multimodal-assess、offer/draft', 'applicationId'],
              ['/ai/nurture/reply、/ai/analytics/ask', 'question'],
              ['/ai/chat', 'message'],
            ],
            [4800, 4200]
          ),

          h1('7. 配置与启动'),
          makeTable(
            ['变量', '默认', '说明'],
            [
              ['PORT', '3002', '监听端口（127.0.0.1）'],
              ['RECRUITOS_BASE_URL', 'http://127.0.0.1:3001', '回调地址'],
              ['OPENAI_API_KEY', '空', '有值启用 LLM'],
              ['OPENAI_BASE_URL', 'OpenAI v1', '兼容网关根路径'],
              ['OPENAI_MODEL', 'gpt-4o-mini', '模型名'],
              ['LLM_TIMEOUT_MS', '90000', '单次补全超时'],
            ],
            [2800, 2800, 3400]
          ),
          p('请勿将真实 API Key 写入文档或公开仓库。RecruitOS 侧配置 HR_AGENT_URL。'),
          ...codeBlock([
            'npm run setup',
            'npm run dev:backend    # :3001',
            'npm run dev:hr-agent   # :3002',
            'npm run dev:frontend   # :5173',
          ]),

          h1('8. 安全与边界'),
          bullet('必须用户 JWT；无服务账号绕过。'),
          bullet('Offer/淘汰仅建议或草稿；外部触达走渠道人工闸门。'),
          bullet('不实现托管登录爬取；多模态当前为文本增强版。'),
          bullet('默认仅监听本机回环地址。'),

          h1('9. 典型时序（JD）'),
          bullet('前端 → RecruitOS /api/ai/jd/generate → HR Agent /ai/jd/generate。'),
          bullet('Agent 查询岗位上下文 → 调 LLM（失败则 mock）→ 保存 drafts → 返回 provider + 结果。'),

          h1('10. 演进建议'),
          bullet('P0：渠道 live 字段对齐；密钥治理。'),
          bullet('P1：技能模块拆分、契约测试与入参 Zod 校验；简历 OCR 流水线。'),
          bullet('P2：全量多模态特征；限流与可观测性。'),

          h1('11. 附录'),
          h2('11.1 相关文档'),
          bullet('docs/系统架构文档.md（§6.3 / §6.4）'),
          bullet('docs/数据库与数据模型分析.md（AgentDraft / AgentAction）'),
          bullet('docs/HR Agent共性需求汇总（招聘） 0729.xlsx'),
          bullet('Markdown 全文：docs/HR-Agent说明文档.md'),
          h2('11.2 草稿类型'),
          makeTable(
            ['AgentDraft.type', '典型技能'],
            [
              ['JD', 'JD 生成'],
              ['NOTICE', '文案/寻聘/排期/沟通'],
              ['SCREEN', '解析/初筛'],
              ['EVAL_SUMMARY', '评价汇总/多模态'],
              ['OFFER', 'Offer 草稿'],
            ],
            [3000, 6000]
          ),
          h2('11.3 版本记录'),
          p('V1.0（2026-08-06）：基于当前 hr-agent 实现首次成文。'),
          new Paragraph({
            spacing: { before: 400 },
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ text: '— 文档结束 —', font: '微软雅黑', size: 20, color: '666666' })],
          }),
        ],
      },
    ],
  });

  const out = path.join(__dirname, '..', 'docs', 'HR-Agent说明文档.docx');
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(out, buffer);
  console.log('Wrote', out);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
