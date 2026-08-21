/**
 * Generate DeepSeek Harness intro DOCX using only jszip (already in project deps).
 * DOCX = ZIP of WordprocessingML files. This script builds a valid .docx with
 * styled headings, bullet lists, tables, and code blocks — all in Chinese.
 */
import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const JSZip = require('/Users/yudong/AI-Coding/deepseek-harness-master/node_modules/.pnpm/jszip@3.10.1/node_modules/jszip');

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT = resolve(__dirname, '..', 'deepseek-harness-intro.docx');

// ─── Document Content ────────────────────────────────────────────────
const sections = [
  { type: 'title', text: 'DeepSeek Harness' },
  { type: 'subtitle', text: '下一代插件化 AI Agent 基础设施' },
  { type: 'body', text: '基于 Cordis 框架构建的全栈式 Agent 运行时，支持 Web GUI、Headless CLI、ACP 自动化服务器等多种运行模式。' },

  { type: 'h1', text: '1. 核心愿景' },
  { type: 'bullet', text: '一切皆插件：模型适配器、工具注册、会话日志、Agent 循环本身均可通过配置替换' },
  { type: 'bullet', text: '无特权内核：没有需要修补的核心代码；通过挂载新插件来扩展功能' },
  { type: 'bullet', text: '可逆副作用：所有注册都是可撤销的 Effect，插件卸载时自动清理资源' },
  { type: 'bullet', text: '多模态运行：Web GUI / Headless CLI / ACP Server / E2B Sandbox' },

  { type: 'h1', text: '2. 架构基石：Cordis 框架' },
  { type: 'body', text: 'DSH 构建在 vendored Cordis 之上，提供以下核心能力：' },
  { type: 'table', headers: ['概念', '描述'], rows: [
    ['Context (ctx)', '共享上下文，承载所有服务和事件总线'],
    ['Service Definition', '声明能力接口（如 ctx.llm, ctx.tools）'],
    ['Typed Events', '强类型事件系统，支持 Waterfall 和 Serial 模式'],
    ['Effects', '可组合、可清理的副作用注册机制'],
    ['Scopes', '每个 Agent 拥有独立的注册作用域'],
  ]},
  { type: 'note', text: '💡 扩展 DSH = 编写一个 Cordis 插件 + 在 cordis.yml 中挂载' },

  { type: 'h1', text: '3. Profile 与 Bundle 体系' },
  { type: 'body', text: '运行时由多层配置组合而成，支持灵活的定制与覆盖：' },
  { type: 'code', text: '[Base Layer] → [Bundle A] → [Bundle B] → [Profile Patch] → [User Patch]' },
  { type: 'bullet', text: 'Profile：命名的插件组合模板（如 web, headless）' },
  { type: 'bullet', text: 'Bundle：可分发的配置+代码单元，支持分层补丁' },
  { type: 'bullet', text: 'Patch：针对特定行的配置替换或插入' },
  { type: 'bullet', text: '查看实际启动树：dsh --profile web --dump-config' },
  { type: 'body', text: '每一层都可以被上层覆盖，实现真正的"可组装架构"。' },

  { type: 'h1', text: '4. 核心子系统' },
  { type: 'table', headers: ['包名', '职责', 'Context Key'], rows: [
    ['core/session', '追加式 SessionEvent 日志与内存存储', 'ctx.sessions'],
    ['core/system-prompt', 'Prompt 片段与 Tool Schema 组装', 'ctx.systemPrompt'],
    ['core/tools', '作用域工具注册与守卫执行管道', 'ctx.tools'],
    ['core/agent-loop', '默认 Agent 驱动实现', 'ctx.agentLoop'],
    ['llm/llm', 'LLM 消息/流词汇表与适配器接缝', 'ctx.llm'],
    ['subagent', '子代理委派与隔离执行', 'ctx.subagents'],
  ]},

  { type: 'h1', text: '5. Turn 与 Step 生命周期' },
  { type: 'body', text: 'Agent 的执行流被精确建模为可观测的事件序列：' },
  { type: 'code', text: `turn/start
  ├─ claim input + queued message
  ├─ agent/pre-step (Waterfall: 可重写/拒绝)
  │   └─ step/start
  │       ├─ derive model history from log
  │       ├─ agent/request → llm/stream → assistant/message
  │       ├─ tool/call → tools/execute → tool/result
  │       └─ step/end
  └─ agent/turn-stopping
turn/end` },
  { type: 'bullet', text: 'Model-visible ⟺ Logged：任何到达模型的输入都必须可从日志重建' },
  { type: 'bullet', text: 'Waterfall 语义：监听器必须调用 next() 以委托给下一环节' },

  { type: 'h1', text: '6. Capability Seams（能力接缝）' },
  { type: 'body', text: '每个可替换能力都包含三个角色：' },
  { type: 'bullet', text: 'Service Definition：声明接口契约（TypeScript Interface）' },
  { type: 'bullet', text: 'Service Provider：具体实现（如 DeepSeek API、本地 Shell、E2B）' },
  { type: 'bullet', text: 'Consumer：使用方（通常是面向模型的工具）' },
  { type: 'note', text: '✅ 完整的能力 = Definition + Provider + Consumer；❌ 单一角色不构成 Seam' },
  { type: 'body', text: '示例：fs 能力包含文件系统接口定义、本地/E2B 提供者、以及 read/write/edit 工具消费者。' },

  { type: 'h1', text: '7. 多运行时支持' },
  { type: 'bullet', text: 'Web App：基于 Vite + Vue 的浏览器端 GUI (apps/web)' },
  { type: 'bullet', text: 'Headless：无服务器的一次性任务执行器' },
  { type: 'bullet', text: 'ACP Server：Agent Client Protocol 自动化服务端' },
  { type: 'bullet', text: 'E2B Sandbox：云端安全沙箱执行环境' },
  { type: 'bullet', text: 'Local Shell：本地 Bash/PowerShell 进程树管理' },
  { type: 'bullet', text: 'Python SDK：独立的 Python 客户端与运行时绑定' },

  { type: 'h1', text: '8. 开发规范亮点' },
  { type: 'bullet', text: 'ESM Only：全项目 "type": "module"，Node ^22.19 || >=24' },
  { type: 'bullet', text: 'Strict TypeScript：strict: true + noImplicitAny，禁止隐式 any' },
  { type: 'bullet', text: 'Effect-Based Registration：所有贡献通过 ctx.effect() / ctx.on()' },
  { type: 'bullet', text: 'Session Log as Source of Truth：模型可见内容必须可重放' },
  { type: 'bullet', text: 'Branded IDs：跨边界 ID 使用 Branded<B> 防止混淆' },
  { type: 'bullet', text: 'Documentation Tiers：严格的事实归属层级，避免重复叙述' },

  { type: 'h1', text: '9. 快速开始' },
  { type: 'code', text: `pnpm install                          # 安装依赖
pnpm run dev:web                      # 启动 Web GUI
pnpm dsh --profile headless "分析目录"  # 运行 Headless 任务
pnpm run test                         # 运行测试
pnpm run build                        # 构建所有包` },
  { type: 'note', text: '🔑 真实 API 测试需要设置 DEEPSEEK_API_KEY 环境变量' },

  { type: 'h1', text: '10. 相关资源' },
  { type: 'bullet', text: '架构文档：docs/architecture.md' },
  { type: 'bullet', text: 'Cordis 入门：docs/cordis-primer.md' },
  { type: 'bullet', text: '包目录：packages/README.md' },
  { type: 'bullet', text: 'Agent Notes：.agents/notes/（决策记录）' },
  { type: 'bullet', text: 'Cookbook：docs/cookbook/（操作指南）' },
  { type: 'bullet', text: 'GitHub：DeepSeek Harness Repository' },
];

// ─── XML Helpers ─────────────────────────────────────────────────────
function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// EMU conversions: 1cm = 360000 EMU, 1pt = 12700 EMU
const PAGE_W = 11906; // A4 width in twips (210mm)
const PAGE_H = 16838; // A4 height in twips (297mm)
const MARGIN = 1440;  // 1 inch in twips

// ─── Style Definitions ───────────────────────────────────────────────
const STYLES_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="PingFang SC" w:eastAsia="PingFang SC" w:hAnsi="PingFang SC"/>
      <w:sz w:val="21"/><w:szCs w:val="21"/>
      <w:lang w:val="zh-CN" w:eastAsia="zh-CN"/>
    </w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>
    <w:pPr><w:spacing w:before="0" w:after="200"/><w:jc w:val="left"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="52"/><w:szCs w:val="52"/><w:color w:val="0F172A"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/>
    <w:pPr><w:spacing w:before="0" w:after="300"/></w:pPr>
    <w:rPr><w:sz w:val="28"/><w:szCs w:val="28"/><w:color w:val="1E40AF"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>
    <w:pPr><w:spacing w:before="360" w:after="160"/><w:pBdr><w:bottom w:val="single" w:sz="8" w:space="4" w:color="3B82F6"/></w:pBdr></w:pPr>
    <w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/><w:color w:val="0F172A"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="BodyText"><w:name w:val="Body Text"/>
    <w:rPr><w:sz w:val="21"/><w:szCs w:val="21"/><w:color w:val="334155"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/>
    <w:pPr><w:numPr><w:numId w:val="1"/></w:numPr><w:spacing w:after="60" w:line="276" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:sz w:val="21"/><w:szCs w:val="21"/><w:color w:val="334155"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="CodeBlock"><w:name w:val="Code Block"/>
    <w:pPr><w:shd w:val="clear" w:color="auto" w:fill="1E293B"/><w:spacing w:before="120" w:after="120" w:line="240" w:lineRule="auto"/><w:ind w:left="360" w:right="360"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Menlo" w:eastAsia="Menlo" w:hAnsi="Menlo"/><w:sz w:val="18"/><w:szCs w:val="18"/><w:color w:val="A5F3FC"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Note"><w:name w:val="Note"/>
    <w:pPr><w:spacing w:before="80" w:after="160"/><w:ind w:left="360"/></w:pPr>
    <w:rPr><w:i/><w:sz w:val="18"/><w:szCs w:val="18"/><w:color w:val="64748B"/></w:rPr>
  </w:style>
</w:styles>`;

const NUMBERING_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="•"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>`;

// ─── Paragraph Builders ──────────────────────────────────────────────
function pStyle(styleId, text) {
  return `<w:p><w:pPr><w:pStyle w:val="${styleId}"/></w:pPr><w:r><w:t xml:space="preserve">${esc(text)}</w:t></w:r></w:p>`;
}

function pCode(text) {
  // Each line of code is a separate paragraph with CodeBlock style
  return text.split('\n').map(line =>
    `<w:p><w:pPr><w:pStyle w:val="CodeBlock"/></w:pPr><w:r><w:t xml:space="preserve">${esc(line || ' ')}</w:t></w:r></w:p>`
  ).join('\n');
}

function pTable(headers, rows) {
  const colCount = headers.length;
  const colW = Math.floor((PAGE_W - 2 * MARGIN) / colCount);
  const gridCols = Array(colCount).fill(`<w:gridCol w:w="${colW}"/>`).join('');

  function cellRow(cells, isHeader) {
    const tcs = cells.map(c => {
      const shading = isHeader
        ? '<w:shd w:val="clear" w:color="auto" w:fill="1E40AF"/>'
        : '';
      const color = isHeader ? 'FFFFFF' : '334155';
      const bold = isHeader ? '<w:b/>' : '';
      return `<w:tc><w:tcPr><w:tcW w:w="${colW}" w:type="dxa"/>${shading}<w:tcBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/><w:left w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/><w:right w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/></w:tcBorders></w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/><w:jc w:val="left"/></w:pPr><w:r><w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/><w:color w:val="${color}"/>${bold}<w:rFonts w:ascii="PingFang SC" w:eastAsia="PingFang SC" w:hAnsi="PingFang SC"/></w:rPr><w:t xml:space="preserve">${esc(c)}</w:t></w:r></w:p></w:tc>`;
    }).join('');
    return `<w:tr>${tcs}</w:tr>`;
  }

  const headerRow = cellRow(headers, true);
  const dataRows = rows.map(r => cellRow(r, false)).join('\n');

  return `<w:tbl>
    <w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="60" w:type="dxa"/><w:left w:w="120" w:type="dxa"/><w:bottom w:w="60" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tblCellMar></w:tblPr>
    <w:tblGrid>${gridCols}</w:tblGrid>
    ${headerRow}
    ${dataRows}
  </w:tbl>`;
}

// ─── Build document.xml body ─────────────────────────────────────────
function buildBody() {
  const parts = [];
  for (const s of sections) {
    switch (s.type) {
      case 'title':    parts.push(pStyle('Title', s.text)); break;
      case 'subtitle': parts.push(pStyle('Subtitle', s.text)); break;
      case 'h1':       parts.push(pStyle('Heading1', s.text)); break;
      case 'body':     parts.push(pStyle('BodyText', s.text)); break;
      case 'bullet':   parts.push(pStyle('ListBullet', s.text)); break;
      case 'code':     parts.push(pCode(s.text)); break;
      case 'note':     parts.push(pStyle('Note', s.text)); break;
      case 'table':    parts.push(pTable(s.headers, s.rows)); break;
    }
  }
  return parts.join('\n');
}

const DOCUMENT_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    ${buildBody()}
    <w:sectPr>
      <w:pgSz w:w="${PAGE_W}" w:h="${PAGE_H}"/>
      <w:pgMar w:top="${MARGIN}" w:right="${MARGIN}" w:bottom="${MARGIN}" w:left="${MARGIN}" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>`;

// ─── Package Files ───────────────────────────────────────────────────
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

const DOCUMENT_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>`;

const SETTINGS_XML = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:defaultTabStop w:val="720"/>
  <w:compat><w:useFELayout/></w:compat>
</w:settings>`;

// ─── Assemble & Write ────────────────────────────────────────────────
async function main() {
  const zip = new JSZip();

  zip.file('[Content_Types].xml', CONTENT_TYPES);
  zip.folder('_rels').file('.rels', RELS);

  const word = zip.folder('word');
  word.file('document.xml', DOCUMENT_XML);
  word.file('styles.xml', STYLES_XML);
  word.file('numbering.xml', NUMBERING_XML);
  word.file('settings.xml', SETTINGS_XML);
  word.folder('_rels').file('document.xml.rels', DOCUMENT_RELS);

  const buf = await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });
  writeFileSync(OUTPUT, buf);
  console.log(`✅ Generated: ${OUTPUT} (${(buf.length / 1024).toFixed(1)} KB)`);
}

main().catch(err => { console.error(err); process.exit(1); });
