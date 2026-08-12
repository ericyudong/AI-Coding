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
            size: 21,
            font: '微软雅黑',
            color: opts.header ? 'FFFFFF' : '1A2B22',
          }),
        ],
      }),
    ],
  });
}

function table(headers, rows, widths) {
  const w = widths || headers.map(() => Math.floor(9000 / headers.length));
  return new Table({
    width: { size: 9000, type: WidthType.DXA },
    columnWidths: w,
    rows: [
      new TableRow({ children: headers.map((h, i) => cell(h, { header: true, bold: true, width: w[i] })) }),
      ...rows.map((r) => new TableRow({ children: r.map((c, i) => cell(c, { width: w[i] })) })),
    ],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 320, after: 120 },
    children: [new TextRun({ text, bold: true, size: 30, font: '微软雅黑', color: '1F6B4A' })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 220, after: 90 },
    children: [new TextRun({ text, bold: true, size: 24, font: '微软雅黑' })],
  });
}

function p(text) {
  return new Paragraph({
    spacing: { after: 80 },
    children: [new TextRun({ text, size: 21, font: '微软雅黑' })],
  });
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: 'bullets', level: 0 },
    spacing: { after: 40 },
    children: [new TextRun({ text, size: 21, font: '微软雅黑' })],
  });
}

async function main() {
  const doc = new Document({
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
        properties: { page: { margin: { top: 720, bottom: 720, left: 720, right: 720 } } },
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { after: 160 },
            children: [new TextRun({ text: 'RecruitOS 数据库与数据模型分析', bold: true, size: 42, font: '微软雅黑', color: '1F6B4A' })],
          }),
          table(
            ['项目', '内容'],
            [
              ['文档版本', 'V1.0'],
              ['编制日期', '2026-08-05'],
              ['分析对象', 'backend/prisma/schema.prisma + backend/src/seed.ts'],
              ['数据库引擎', 'SQLite（开发态，Prisma ORM）'],
            ],
            [2400, 6600]
          ),

          h1('1. 分析目标与范围'),
          bullet('评估领域建模完整性（主流程 + 二期能力 + Agent 集成）。'),
          bullet('评估关系约束、可追溯性、可扩展性、性能与治理风险。'),
          bullet('输出分阶段优化建议（P0/P1/P2）。'),

          h1('2. 总体结论'),
          p('当前模型属于“业务优先、快速交付、可运行闭环”的设计，适合中小规模本地/测试场景。'),
          bullet('优势：流程主线清晰，实体边界基本正确，Agent 风险控制模型完整。'),
          bullet('风险：大量 String/JSON 字段导致约束弱、索引不足、统计治理成本高。'),
          bullet('建议：先补索引与状态治理，再推进结构化拆分和 PostgreSQL 迁移。'),

          h1('3. 模型结构分析'),
          h2('3.1 领域分组'),
          table(
            ['领域', '主要模型'],
            [
              ['组织与权限', 'Organization, User, Dictionary, Template'],
              ['招聘主流程', 'RecruitRequest, Job, Candidate, Application, ProcessEvent'],
              ['面试录用入职', 'Interview, InterviewEvaluation, Offer, Onboarding'],
              ['运营协同', 'Todo, Activity, MessageLog, SlaRule, Alert*'],
              ['Agent与二期扩展', 'JobStandard, EvalModel, FlowTemplate, Channel*, Agent*, BusinessEvent'],
            ],
            [2200, 6800]
          ),
          h2('3.2 核心关系'),
          bullet('RecruitRequest -> Job -> Application <- Candidate。'),
          bullet('Application -> Interview -> InterviewEvaluation。'),
          bullet('Application -> Offer -> Onboarding。'),
          bullet('流程状态挂 Application，支持同候选人多岗位并行。'),

          h1('4. 设计亮点'),
          bullet('主档与流程实例分离，符合招聘业务真实流转。'),
          bullet('Offer 版本化（version + isActive）支持重审。'),
          bullet('AgentAction 内置 riskLevel/幂等/人工确认链路。'),
          bullet('FlowTemplate + EvalModel + JobStandard 提供可配置化基础。'),

          h1('5. 关键风险点'),
          table(
            ['风险点', '影响', '建议'],
            [
              ['状态字段大量 String', '脏值风险、统计口径不稳', '逐步枚举化 + 输入校验'],
              ['JSON字段较多', '过滤/索引弱，治理复杂', '高频字段结构化拆分'],
              ['索引不足', '数据增长后慢查询', '补状态/时间/外键/唯一索引'],
              ['dataScope未全面落地', '潜在越权查看', '统一行级过滤器'],
              ['软删策略不统一', '审计留存策略不一致', '制定分层删除与归档规范'],
            ],
            [2200, 3000, 2800]
          ),

          h1('6. HR Agent 集成评估'),
          bullet('优势：查询（/api/agent/query）、草稿（AgentDraft）、动作（AgentAction）、事件（BusinessEvent）链路完整。'),
          bullet('缺口：缺少 traceId / modelName / promptVersion 等跨服务追踪字段。'),
          bullet('建议：为 AgentDraft/AgentAction 增加可观测字段，支持质量回溯。'),

          h1('7. 分阶段优化建议'),
          h2('7.1 P0（1~2周）'),
          bullet('补齐高频索引：Application/Interview/Offer/AgentAction 等状态与时间列。'),
          bullet('统一状态常量与校验规则，收敛非法状态写入。'),
          bullet('落地 dataScope 行级过滤。'),
          h2('7.2 P1（2~4周）'),
          bullet('拆分 parsedResume、scores 等高频 JSON 字段。'),
          bullet('引入 traceId、modelName、promptVersion。'),
          bullet('制定软删、匿名化、归档与保留周期策略。'),
          h2('7.3 P2（1~2月）'),
          bullet('规划 PostgreSQL 迁移（枚举、JSONB、索引、分区、全文检索）。'),
          bullet('建立跨服务数据字典与 schema 版本治理。'),

          h1('8. 结语'),
          p('当前数据模型已具备“可运行、可演示、可扩展”基础。建议按 P0 -> P1 -> P2 推进治理与性能增强，以支撑更高并发和更严格合规要求。'),
        ],
      },
    ],
  });

  const out = path.join(__dirname, '..', 'docs', '数据库与数据模型分析.docx');
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(out, buffer);
  console.log('Wrote', out);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

