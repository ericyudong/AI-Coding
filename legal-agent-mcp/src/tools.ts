import { z } from 'zod'

import type { LegalAgentClient } from './legal-client.js'
import { formatJson } from './legal-client.js'

export const TOOL_DEFINITIONS = [
  {
    name: 'legal_search',
    description:
      '法律检索：对法律问题进行综合分析、法规查询、类案检索、行政处罚或专业解读。返回 AI 分析结论与参考依据。',
    inputSchema: {
      type: 'object' as const,
      properties: {
        query: { type: 'string', description: '法律问题或检索关键词' },
        search_type: {
          type: 'string',
          enum: ['comprehensive', 'regulation', 'case', 'penalty', 'interpretation'],
          description: '检索类型，默认 comprehensive（综合分析）',
        },
        optimize: { type: 'boolean', description: '是否优化检索 query（默认 false）' },
      },
      required: ['query'],
    },
  },
  {
    name: 'legal_chat',
    description:
      '法律智能问答：支持劳动法、通用法律问答、金融合规、企业出海等模块。可传入 session_id 继续多轮对话。',
    inputSchema: {
      type: 'object' as const,
      properties: {
        message: { type: 'string', description: '用户问题' },
        module: {
          type: 'string',
          enum: ['labor_law', 'qa', 'financial', 'overseas'],
          description: '问答模块，默认 labor_law',
        },
        session_id: { type: 'number', description: '可选，继续已有会话 ID' },
      },
      required: ['message'],
    },
  },
  {
    name: 'contract_draft',
    description: '合同起草：根据用途、立场与风格生成合同草案文本。',
    inputSchema: {
      type: 'object' as const,
      properties: {
        purpose: { type: 'string', description: '合同用途/背景描述' },
        position: { type: 'string', description: '起草立场，如「甲方」「乙方」' },
        extra_info: { type: 'string', description: '补充信息' },
        style: {
          type: 'string',
          description: '起草风格：简明居中、详细严谨、偏向甲方、偏向乙方',
        },
        draft_type: { type: 'string', description: '草案类型，默认 contract' },
      },
      required: ['purpose'],
    },
  },
  {
    name: 'contract_review_file',
    description:
      '合同审核：上传本地 doc/docx/pdf 文件并执行 AI 审核。review_mode 可选 checklist（清单审核）或 reference（参照惯例）。',
    inputSchema: {
      type: 'object' as const,
      properties: {
        file_path: { type: 'string', description: '本地合同文件绝对或相对路径' },
        review_mode: {
          type: 'string',
          enum: ['checklist', 'reference'],
          description: '审核模式，默认 checklist',
        },
      },
      required: ['file_path'],
    },
  },
  {
    name: 'contract_compare_files',
    description: '合同比对：对比两份本地 doc/docx/pdf 合同，返回差异摘要与风险说明。',
    inputSchema: {
      type: 'object' as const,
      properties: {
        left_file_path: { type: 'string', description: '左侧/基准合同文件路径' },
        right_file_path: { type: 'string', description: '右侧/对比合同文件路径' },
      },
      required: ['left_file_path', 'right_file_path'],
    },
  },
  {
    name: 'legal_capabilities',
    description: '获取 Legal Agent 支持的检索类型、聊天模块与合同起草风格等元数据。',
    inputSchema: {
      type: 'object' as const,
      properties: {},
    },
  },
] as const

const searchArgs = z.object({
  query: z.string().min(1),
  search_type: z.enum(['comprehensive', 'regulation', 'case', 'penalty', 'interpretation']).optional(),
  optimize: z.boolean().optional(),
})

const chatArgs = z.object({
  message: z.string().min(1),
  module: z.enum(['labor_law', 'qa', 'financial', 'overseas']).optional(),
  session_id: z.number().optional(),
})

const draftArgs = z.object({
  purpose: z.string().min(1),
  position: z.string().optional(),
  extra_info: z.string().optional(),
  style: z.string().optional(),
  draft_type: z.string().optional(),
})

const reviewArgs = z.object({
  file_path: z.string().min(1),
  review_mode: z.enum(['checklist', 'reference']).optional(),
})

const compareArgs = z.object({
  left_file_path: z.string().min(1),
  right_file_path: z.string().min(1),
})

export async function handleToolCall(
  client: LegalAgentClient,
  name: string,
  args: unknown,
): Promise<{ content: Array<{ type: 'text'; text: string }>; isError?: boolean }> {
  try {
    switch (name) {
      case 'legal_search': {
        const { query, search_type, optimize } = searchArgs.parse(args)
        const result = await client.search(query, search_type ?? 'comprehensive', optimize ?? false)
        return {
          content: [{
            type: 'text',
            text: `# 法律检索结果\n\n**类型**: ${result.search_type}\n\n${result.answer}\n\n${
              result.references.length ? `**参考**: ${result.references.join('；')}` : ''
            }`.trim(),
          }],
        }
      }
      case 'legal_chat': {
        const { message, module, session_id } = chatArgs.parse(args)
        const result = await client.chat(message, module ?? 'labor_law', session_id)
        return {
          content: [{
            type: 'text',
            text: `# 法律问答\n\n**会话 ID**: ${result.session_id}\n\n${result.reply.content}`,
          }],
        }
      }
      case 'contract_draft': {
        const params = draftArgs.parse(args)
        const result = await client.draftContract(params)
        return {
          content: [{
            type: 'text',
            text: `# 合同草案 (ID: ${result.id})\n\n**风格**: ${result.style}\n\n${result.content}`,
          }],
        }
      }
      case 'contract_review_file': {
        const { file_path, review_mode } = reviewArgs.parse(args)
        const result = await client.reviewContractFile(file_path, review_mode ?? 'checklist')
        const warnings = result.parse_warnings?.length
          ? `\n\n**解析警告**: ${result.parse_warnings.join('；')}`
          : ''
        return {
          content: [{
            type: 'text',
            text: `# 合同审核报告\n\n**文件**: ${result.filename}\n**模式**: ${result.review_mode}\n**状态**: ${result.status}\n\n${result.result}${warnings}`,
          }],
        }
      }
      case 'contract_compare_files': {
        const { left_file_path, right_file_path } = compareArgs.parse(args)
        const result = await client.compareContractFiles(left_file_path, right_file_path)
        return {
          content: [{
            type: 'text',
            text: `# 合同比对\n\n**左**: ${result.left_filename}\n**右**: ${result.right_filename}\n**耗时**: ${result.elapsed_ms}ms\n\n## 摘要\n${formatJson(result.summary)}\n\n## 风险说明\n${result.risk_note}\n\n## 变更明细\n${formatJson(result.changes)}`,
          }],
        }
      }
      case 'legal_capabilities': {
        const meta = await client.getMetadata()
        return { content: [{ type: 'text', text: formatJson(meta) }] }
      }
      default:
        return {
          content: [{ type: 'text', text: `未知工具: ${name}` }],
          isError: true,
        }
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return {
      content: [{ type: 'text', text: `Legal Agent 调用失败: ${message}` }],
      isError: true,
    }
  }
}
