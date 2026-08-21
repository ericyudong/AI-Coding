/**
 * Generate DeepSeek Harness intro PPTX using only jszip (already in project deps).
 * PPTX = ZIP of OOXML files. This script builds the minimal valid structure.
 */
import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
// Resolve jszip from the project root's pnpm store
const JSZip = require('/Users/yudong/AI-Coding/deepseek-harness-master/node_modules/.pnpm/jszip@3.10.1/node_modules/jszip');

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT = resolve(__dirname, '..', 'deepseek-harness-intro.pptx');

// --- Slide content (Chinese) ---
const slides = [
  {
    title: 'DeepSeek Harness',
    subtitle: '下一代插件化 AI Agent 基础设施',
    body: '基于 Cordis 框架构建的全栈式 Agent 运行时',
  },
  {
    title: '🎯 核心愿景',
    bullets: [
      '一切皆插件：模型适配器、工具注册、会话日志、Agent 循环均可替换',
      '无特权内核：通过挂载新插件扩展功能，无需修补核心代码',
      '可逆副作用：所有注册都是可撤销的 Effect，卸载时自动清理',
      '多模态运行：Web GUI / Headless CLI / ACP Server / E2B Sandbox',
    ],
  },
  {
    title: '🏗️ 架构基石：Cordis 框架',
    bullets: [
      'Context (ctx)：共享上下文，承载服务与事件总线',
      'Service Definition：声明能力接口（如 ctx.llm, ctx.tools）',
      'Typed Events：强类型事件系统，支持 Waterfall 和 Serial 模式',
      'Effects：可组合、可清理的副作用注册机制',
      'Scopes：每个 Agent 拥有独立的注册作用域',
    ],
    note: '💡 扩展 DSH = 编写 Cordis 插件 + 在 cordis.yml 中挂载',
  },
  {
    title: '📦 Profile 与 Bundle 体系',
    bullets: [
      'Profile：命名的插件组合模板（如 web, headless）',
      'Bundle：可分发的配置+代码单元，支持分层补丁',
      'Patch：针对特定行的配置替换或插入',
      '查看实际启动树：dsh --profile web --dump-config',
      '每一层都可被上层覆盖，实现真正的可组装架构',
    ],
  },
  {
    title: '🔧 核心子系统',
    table: [
      ['包名', '职责', 'Context Key'],
      ['core/session', '追加式 SessionEvent 日志', 'ctx.sessions'],
      ['core/system-prompt', 'Prompt 与 Tool Schema 组装', 'ctx.systemPrompt'],
      ['core/tools', '作用域工具注册与守卫管道', 'ctx.tools'],
      ['core/agent-loop', '默认 Agent 驱动实现', 'ctx.agentLoop'],
      ['llm/llm', 'LLM 消息/流词汇表与适配器', 'ctx.llm'],
      ['subagent', '子代理委派与隔离执行', 'ctx.subagents'],
    ],
  },
  {
    title: '🔄 Turn 与 Step 生命周期',
    bullets: [
      'turn/start → claim input → agent/pre-step (Waterfall)',
      'step/start → derive history → llm/stream → assistant/message',
      'tool/call → tools/execute → tool/result → step/end',
      'agent/turn-stopping → turn/end',
      'Model-visible ⟺ Logged：任何到达模型的输入必须可从日志重建',
      'Waterfall 语义：监听器必须调用 next() 以委托',
    ],
  },
  {
    title: '🛠️ Capability Seams（能力接缝）',
    bullets: [
      'Service Definition：声明接口契约（TypeScript Interface）',
      'Service Provider：具体实现（DeepSeek API / 本地 Shell / E2B）',
      'Consumer：使用方（通常是面向模型的工具）',
      '✅ 完整能力 = Definition + Provider + Consumer',
      '❌ 单一角色不构成 Seam',
    ],
    note: '示例：fs 能力 = 文件系统接口 + 本地/E2B 提供者 + read/write/edit 工具',
  },
  {
    title: '🌐 多运行时支持',
    bullets: [
      'Web App：Vite + Vue 浏览器端 GUI (apps/web)',
      'Headless：无服务器一次性任务执行器',
      'ACP Server：Agent Client Protocol 自动化服务端',
      'E2B Sandbox：云端安全沙箱执行环境',
      'Local Shell：本地 Bash/PowerShell 进程树管理',
      'Python SDK：独立 Python 客户端与运行时绑定',
    ],
  },
  {
    title: '📝 开发规范亮点',
    bullets: [
      'ESM Only：全项目 "type": "module"，Node ^22.19 || >=24',
      'Strict TypeScript：strict: true + noImplicitAny',
      'Effect-Based Registration：所有贡献通过 ctx.effect() / ctx.on()',
      'Session Log as Source of Truth：模型可见内容必须可重放',
      'Branded IDs：跨边界 ID 使用 Branded<B> 防止混淆',
      'Documentation Tiers：严格的事实归属层级，避免重复叙述',
    ],
  },
  {
    title: '🚀 快速开始',
    code: [
      'pnpm install            # 安装依赖',
      'pnpm run dev:web        # 启动 Web GUI',
      'pnpm dsh --profile headless "分析当前目录"',
      'pnpm run test           # 运行测试',
      'pnpm run build          # 构建所有包',
    ],
    note: '🔑 真实 API 测试需设置 DEEPSEEK_API_KEY',
  },
  {
    title: '📚 相关资源',
    bullets: [
      '架构文档：docs/architecture.md',
      'Cordis 入门：docs/cordis-primer.md',
      '包目录：packages/README.md',
      'Agent Notes：.agents/notes/（决策记录）',
      'Cookbook：docs/cookbook/（操作指南）',
      'GitHub：DeepSeek Harness Repository',
    ],
  },
];

// --- OOXML builders ---
const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
${slides.map((_, i) => `  <Override PartName="/ppt/slides/slide${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>`).join('\n')}
</Types>`;

const RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>`;

const PRESENTATION_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
${slides.map((_, i) => `  <Relationship Id="rId${i + 10}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide${i + 1}.xml"/>`).join('\n')}
</Relationships>`;

const PRESENTATION = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst>
    <p:sldMasterId id="2147483648" r:id="rId1"/>
  </p:sldMasterIdLst>
  <p:sldIdLst>
${slides.map((_, i) => `    <p:sldId id="${256 + i}" r:id="rId${i + 10}"/>`).join('\n')}
  </p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>`;

const SLIDE_MASTER = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="F8FAFC"/></a:solidFill><a:effectLst/></p:bgPr></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>`;

const SLIDE_MASTER_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>`;

const SLIDE_LAYOUT = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
             type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>
</p:sldLayout>`;

const SLIDE_LAYOUT_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>`;

const THEME = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="DSH Theme">
  <a:themeElements>
    <a:clrScheme name="DSH">
      <a:dk1><a:srgbClr val="1E293B"/></a:dk1>
      <a:lt1><a:srgbClr val="F8FAFC"/></a:lt1>
      <a:dk2><a:srgbClr val="0F172A"/></a:dk2>
      <a:lt2><a:srgbClr val="E2E8F0"/></a:lt2>
      <a:accent1><a:srgbClr val="3B82F6"/></a:accent1>
      <a:accent2><a:srgbClr val="1E40AF"/></a:accent2>
      <a:accent3><a:srgbClr val="10B981"/></a:accent3>
      <a:accent4><a:srgbClr val="F59E0B"/></a:accent4>
      <a:accent5><a:srgbClr val="EF4444"/></a:accent5>
      <a:accent6><a:srgbClr val="8B5CF6"/></a:accent6>
      <a:hlink><a:srgbClr val="2563EB"/></a:hlink>
      <a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="DSH">
      <a:majorFont><a:latin typeface="PingFang SC"/><a:ea typeface="PingFang SC"/><a:cs typeface=""/></a:majorFont>
      <a:minorFont><a:latin typeface="PingFang SC"/><a:ea typeface="PingFang SC"/><a:cs typeface=""/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
  </a:themeElements>
</a:theme>`;

function escapeXml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function buildSlideXml(slide, index) {
  const shapes = [];
  let shapeId = 2;

  // Title
  shapes.push(`
    <p:sp>
      <p:nvSpPr><p:cNvPr id="${shapeId++}" name="Title"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="457200" y="274638"/><a:ext cx="11277600" cy="1143000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
      <p:txBody><a:bodyPr anchor="b"/><a:lstStyle/><a:p>
        <a:pPr algn="l"/><a:r><a:rPr lang="zh-CN" sz="3600" b="1" dirty="0"><a:solidFill><a:srgbClr val="0F172A"/></a:solidFill><a:latin typeface="PingFang SC"/><a:ea typeface="PingFang SC"/></a:rPr><a:t>${escapeXml(slide.title)}</a:t></a:r>
      </a:p></p:txBody>
    </p:sp>`);

  // Subtitle (only for first slide)
  if (slide.subtitle) {
    shapes.push(`
    <p:sp>
      <p:nvSpPr><p:cNvPr id="${shapeId++}" name="Subtitle"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="457200" y="1600200"/><a:ext cx="11277600" cy="800000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
      <p:txBody><a:bodyPr anchor="t"/><a:lstStyle/><a:p>
        <a:pPr algn="l"/><a:r><a:rPr lang="zh-CN" sz="2400" dirty="0"><a:solidFill><a:srgbClr val="1E40AF"/></a:solidFill><a:latin typeface="PingFang SC"/><a:ea typeface="PingFang SC"/></a:rPr><a:t>${escapeXml(slide.subtitle)}</a:t></a:r>
      </a:p></p:txBody>
    </p:sp>`);
  }

  // Body text or bullets
  const bodyY = slide.subtitle ? 2600000 : 1600000;
  const bodyH = slide.subtitle ? 3800000 : 4800000;

  if (slide.bullets) {
    const paragraphs = slide.bullets.map(b => `
        <a:p><a:pPr marL="342900" indent="-342900"/><a:buChar char="•"/><a:r><a:rPr lang="zh-CN" sz="1800" dirty="0"><a:solidFill><a:srgbClr val="334155"/></a:solidFill><a:latin typeface="PingFang SC"/><a:ea typeface="PingFang SC"/></a:rPr><a:t>${escapeXml(b)}</a:t></a:r></a:p>`).join('');
    shapes.push(`
    <p:sp>
      <p:nvSpPr><p:cNvPr id="${shapeId++}" name="Body"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="457200" y="${bodyY}"/><a:ext cx="11277600" cy="${bodyH}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
      <p:txBody><a:bodyPr anchor="t"/><a:lstStyle/>${paragraphs}</p:txBody>
    </p:sp>`);
  }

  // Table
  if (slide.table) {
    const rows = slide.table.length;
    const cols = slide.table[0].length;
    const colW = Math.floor(11277600 / cols);
    const rowH = 400000;
    const tblRows = slide.table.map((row, ri) => {
      const cells = row.map(cell => `
            <a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="zh-CN" sz="1400" b="${ri === 0 ? '1' : '0'}" dirty="0"><a:solidFill><a:srgbClr val="${ri === 0 ? 'FFFFFF' : '334155'}"/></a:solidFill><a:latin typeface="PingFang SC"/><a:ea typeface="PingFang SC"/></a:rPr><a:t>${escapeXml(cell)}</a:t></a:r></a:p></a:txBody><a:tcPr><a:solidFill><a:srgbClr val="${ri === 0 ? '1E40AF' : (ri % 2 === 0 ? 'F1F5F9' : 'FFFFFF')}"/></a:solidFill></a:tcPr></a:tc>`).join('');
      return `<a:tr h="${rowH}">${cells}</a:tr>`;
    }).join('');

    shapes.push(`
    <p:graphicFrame>
      <p:nvGraphicFramePr><p:cNvPr id="${shapeId++}" name="Table"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>
      <p:xfrm><a:off x="457200" y="${bodyY}"/><a:ext cx="11277600" cy="${rows * rowH}"/></p:xfrm>
      <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">
        <a:tbl><a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>${Array(cols).fill(`<a:gridCol w="${colW}"/>`).join('')}</a:tblGrid>${tblRows}</a:tbl>
      </a:graphicData></a:graphic>
    </p:graphicFrame>`);
  }

  // Code block
  if (slide.code) {
    const codeText = slide.code.join('\n');
    shapes.push(`
    <p:sp>
      <p:nvSpPr><p:cNvPr id="${shapeId++}" name="Code"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="457200" y="${bodyY}"/><a:ext cx="11277600" cy="${bodyH}"/></a:xfrm><a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val 3000"/></a:avLst></a:prstGeom><a:solidFill><a:srgbClr val="1E293B"/></a:solidFill></p:spPr>
      <p:txBody><a:bodyPr anchor="t" lIns="180000" tIns="120000" rIns="180000" bIns="120000"/><a:lstStyle/><a:p>
        <a:r><a:rPr lang="en-US" sz="1400" dirty="0"><a:solidFill><a:srgbClr val="A5F3FC"/></a:solidFill><a:latin typeface="Menlo"/><a:ea typeface="Menlo"/></a:rPr><a:t>${escapeXml(codeText)}</a:t></a:r>
      </a:p></p:txBody>
    </p:sp>`);
  }

  // Note at bottom
  if (slide.note) {
    shapes.push(`
    <p:sp>
      <p:nvSpPr><p:cNvPr id="${shapeId++}" name="Note"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="457200" y="6200000"/><a:ext cx="11277600" cy="400000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
      <p:txBody><a:bodyPr anchor="t"/><a:lstStyle/><a:p>
        <a:pPr algn="l"/><a:r><a:rPr lang="zh-CN" sz="1200" i="1" dirty="0"><a:solidFill><a:srgbClr val="64748B"/></a:solidFill><a:latin typeface="PingFang SC"/><a:ea typeface="PingFang SC"/></a:rPr><a:t>${escapeXml(slide.note)}</a:t></a:r>
      </a:p></p:txBody>
    </p:sp>`);
  }

  // Blue accent line under title
  shapes.push(`
    <p:cxnSp>
      <p:nvCxnSpPr><p:cNvPr id="${shapeId++}" name="Line"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
      <p:spPr><a:xfrm><a:off x="457200" y="1420000"/><a:ext cx="11277600" cy="0"/></a:xfrm><a:prstGeom prst="line"><a:avLst/></a:prstGeom><a:ln w="28575"><a:solidFill><a:srgbClr val="3B82F6"/></a:solidFill></a:ln></p:spPr>
    </p:cxnSp>`);

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>${shapes.join('\n')}</p:spTree></p:cSld>
</p:sld>`;
}

function slideRels(index) {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>`;
}

// --- Build ZIP ---
async function main() {
  const zip = new JSZip();

  zip.file('[Content_Types].xml', CONTENT_TYPES);
  zip.folder('_rels').file('.rels', RELS);

  const ppt = zip.folder('ppt');
  ppt.file('presentation.xml', PRESENTATION);
  ppt.folder('_rels').file('presentation.xml.rels', PRESENTATION_RELS);

  const sm = ppt.folder('slideMasters');
  sm.file('slideMaster1.xml', SLIDE_MASTER);
  sm.folder('_rels').file('slideMaster1.xml.rels', SLIDE_MASTER_RELS);

  const sl = ppt.folder('slideLayouts');
  sl.file('slideLayout1.xml', SLIDE_LAYOUT);
  sl.folder('_rels').file('slideLayout1.xml.rels', SLIDE_LAYOUT_RELS);

  ppt.folder('theme').file('theme1.xml', THEME);

  const slidesFolder = ppt.folder('slides');
  const slidesRels = slidesFolder.folder('_rels');
  slides.forEach((slide, i) => {
    slidesFolder.file(`slide${i + 1}.xml`, buildSlideXml(slide, i));
    slidesRels.file(`slide${i + 1}.xml.rels`, slideRels(i));
  });

  const buf = await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });
  writeFileSync(OUTPUT, buf);
  console.log(`✅ Generated: ${OUTPUT} (${(buf.length / 1024).toFixed(1)} KB)`);
}

main().catch(err => { console.error(err); process.exit(1); });
