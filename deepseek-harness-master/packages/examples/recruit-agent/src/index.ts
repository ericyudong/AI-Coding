/**
 * RecruitOS / HR Agent plugin: model tools and bundled recruitment skills.
 * @module @deepseek-ai/dsh-recruit-agent
 */

import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import type { Context } from '@deepseek-ai/cordis'
import z from '@deepseek-ai/schemastery'
import {
  BUNDLED_SKILL_RANK,
  type SkillCandidate,
  type SkillDefinition,
  type SkillProvider,
} from '@deepseek-ai/dsh-skill'
import { defineTool, type JsonValue } from '@deepseek-ai/dsh-tools'
import { HR_AGENT_PATHS, RecruitOsClient, type RecruitAgentEndpoints } from './recruitos-client.ts'

export const name = 'recruit-agent'
export const inject = ['tools', 'skills']

const PROVIDER_NAME = 'recruit-agent'
const RESOURCE_BASE = {
  kind: 'directory',
  path: fileURLToPath(new URL('../assets/skills/', import.meta.url)),
} as const

const BUNDLED_SKILLS: readonly { name: string, file: string, description: string }[] = [
  {
    name: 'hr-recruitment',
    file: 'hr-recruitment.md',
    description:
      'RecruitOS 招聘全流程助手：JD 撰写、简历初筛、面试协调、Offer 草稿与招聘数据分析。在招聘业务上下文中优先加载。',
  },
  {
    name: 'hr-jd',
    file: 'hr-jd.md',
    description: '职位需求诊断与 JD 生成、多渠道发布文案。需要 jobId 或 brief 时使用。',
  },
  {
    name: 'hr-resume',
    file: 'hr-resume.md',
    description: '简历解析与岗位初筛。需要 candidateId 与 jobId 时使用。',
  },
  {
    name: 'hr-interview',
    file: 'hr-interview.md',
    description: '面试日程协调与多面试官评价汇总。需要 applicationId 时使用。',
  },
  {
    name: 'hr-offer',
    file: 'hr-offer.md',
    description: 'Offer 与入职衔接草稿。需要 applicationId 时使用。',
  },
  {
    name: 'hr-analytics',
    file: 'hr-analytics.md',
    description: '招聘漏斗与渠道 ROI 等自然语言数据分析。',
  },
]

/** Plugin configuration for RecruitOS and HR Agent endpoints. */
export interface Config {
  /** RecruitOS API base URL. */
  recruitosBaseUrl?: string
  /** HR Agent service base URL. */
  hrAgentBaseUrl?: string
  /**
   * JWT for RecruitOS / HR Agent (Bearer). When omitted, reads
   * `RECRUITOS_JWT` or `RECRUITOS_TOKEN` from the process environment.
   */
  authToken?: string
}

export const Config: z<Pick<Config, 'recruitosBaseUrl' | 'hrAgentBaseUrl'>> = z.object({
  recruitosBaseUrl: z.string().default('http://127.0.0.1:3001'),
  hrAgentBaseUrl: z.string().default('http://127.0.0.1:3002'),
})

function resolveAuthToken(configToken?: string): string {
  const fromConfig = configToken?.trim()
  if (fromConfig) return fromConfig
  const fromEnv = process.env.RECRUITOS_JWT?.trim() || process.env.RECRUITOS_TOKEN?.trim()
  if (fromEnv) return fromEnv
  throw new Error(
    'RecruitOS 认证未配置：在 cordis.yml 设置 authToken，或设置环境变量 RECRUITOS_JWT / RECRUITOS_TOKEN',
  )
}

function buildClient(config: Config = {}): RecruitOsClient {
  const endpoints: RecruitAgentEndpoints = {
    recruitosBaseUrl: config.recruitosBaseUrl ?? 'http://127.0.0.1:3001',
    hrAgentBaseUrl: config.hrAgentBaseUrl ?? 'http://127.0.0.1:3002',
    authToken: resolveAuthToken(config.authToken),
  }
  return new RecruitOsClient(endpoints)
}

function jsonOutput() {
  return {
    schema: { type: 'object' as const, additionalProperties: true as const },
    render: (_args: unknown, value: Record<string, JsonValue>) => [{
      type: 'text' as const,
      text: JSON.stringify(value),
    }],
  }
}

function skillCandidate(entry: typeof BUNDLED_SKILLS[number]): SkillCandidate {
  return {
    name: entry.name,
    description: entry.description,
    invocation: { modelInvocable: true, userInvocable: true },
    provider: PROVIDER_NAME,
    source: 'bundled',
    resourceBase: RESOURCE_BASE,
    rank: BUNDLED_SKILL_RANK,
    locator: new URL(`../assets/skills/${entry.file}`, import.meta.url),
  }
}

function registerSkillProvider(ctx: Context): void {
  const candidates = BUNDLED_SKILLS.map(skillCandidate)
  const provider: SkillProvider = {
    name: PROVIDER_NAME,
    list: () => Promise.resolve(candidates),
    async get(candidate): Promise<SkillDefinition> {
      const entry = BUNDLED_SKILLS.find(s => s.name === candidate.name)
      if (!entry) throw new Error(`skill not found: ${candidate.name}`)
      const content = await readFile(new URL(`../assets/skills/${entry.file}`, import.meta.url), 'utf8')
      return {
        name: entry.name,
        description: entry.description,
        invocation: { modelInvocable: true, userInvocable: true },
        provider: PROVIDER_NAME,
        source: 'bundled',
        resourceBase: RESOURCE_BASE,
        content,
      }
    },
  }
  ctx.skills.registerProvider(() => provider)
}

function registerTools(ctx: Context, getClient: () => RecruitOsClient): void {
  ctx.tools.register(defineTool({
    name: 'recruitos_query',
    description:
      '从 RecruitOS 查询结构化对象。objectType: job | candidate | application | offer。',
    parameters: {
      objectType: {
        type: 'string',
        required: true,
        enum: ['job', 'candidate', 'application', 'offer'],
        description: '对象类型',
      },
      id: { type: 'string', required: true, description: '对象 ID' },
    },
    output: jsonOutput(),
    async execute(args) {
      return await getClient().query(args.objectType, args.id) as Record<string, JsonValue>
    },
    presentCall: args => ({
      card: 'generic',
      title: 'RecruitOS 查询',
      kind: 'search',
      rawInput: args,
    }),
  }))

  ctx.tools.register(defineTool({
    name: 'recruitos_search',
    description: '在 RecruitOS 中按关键词搜索岗位、候选人或投递记录。',
    parameters: {
      q: { type: 'string', required: true, description: '搜索关键词' },
      type: {
        type: 'string',
        enum: ['job', 'candidate', 'application'],
        description: '限定对象类型（可选）',
      },
    },
    output: jsonOutput(),
    async execute(args) {
      return await getClient().search(args.q, args.type) as Record<string, JsonValue>
    },
    presentCall: args => ({
      card: 'generic',
      title: 'RecruitOS 搜索',
      kind: 'search',
      rawInput: args,
    }),
  }))

  ctx.tools.register(defineTool({
    name: 'recruitos_save_draft',
    description: '将 AI 生成内容保存为 RecruitOS 草稿，供 HR 审核后采纳。',
    parameters: {
      type: { type: 'string', required: true, description: '草稿类型，如 JD / OFFER / MESSAGE' },
      content: { type: 'string', required: true, description: '草稿正文' },
      refType: { type: 'string', description: '关联对象类型' },
      refId: { type: 'string', description: '关联对象 ID' },
    },
    output: jsonOutput(),
    async execute(args) {
      return await getClient().saveDraft({
        type: args.type,
        content: args.content,
        ...(args.refType !== undefined ? { refType: args.refType } : {}),
        ...(args.refId !== undefined ? { refId: args.refId } : {}),
      }) as Record<string, JsonValue>
    },
    presentCall: args => ({
      card: 'generic',
      title: '保存 RecruitOS 草稿',
      kind: 'edit',
      rawInput: args,
    }),
  }))

  ctx.tools.register(defineTool({
    name: 'recruitos_propose_action',
    description:
      '向 RecruitOS 提议受控业务动作（如发 Offer、拒候选人）。高风险动作需用户在系统中确认。',
    parameters: {
      actionKey: { type: 'string', required: true, description: '动作键，如 SEND_OFFER / REJECT_CANDIDATE' },
      payload: {
        type: 'object',
        required: true,
        additionalProperties: true,
        description: '动作参数 JSON',
      },
      autoConfirm: {
        type: 'boolean',
        description: '是否尝试自动确认（仅低风险动作）',
      },
    },
    output: jsonOutput(),
    async execute(args) {
      return await getClient().proposeAction({
        actionKey: args.actionKey,
        payload: args.payload,
        ...(args.autoConfirm !== undefined ? { autoConfirm: args.autoConfirm } : {}),
      }) as Record<string, JsonValue>
    },
    presentCall: args => ({
      card: 'generic',
      title: 'RecruitOS 动作提议',
      kind: 'other',
      rawInput: args,
    }),
  }))

  const capabilityEnum = Object.keys(HR_AGENT_PATHS)
  ctx.tools.register(defineTool({
    name: 'hr_agent_invoke',
    description:
      '调用 HR Agent AI 能力（JD 生成、初筛、排期、评价汇总、Offer 草稿、数据分析、对话等）。'
      + ` capability 可选: ${capabilityEnum.join(', ')}。body 为各能力所需 JSON 参数。`,
    parameters: {
      capability: {
        type: 'string',
        required: true,
        enum: capabilityEnum,
        description: 'HR Agent 能力键',
      },
      body: {
        type: 'object',
        required: true,
        additionalProperties: true,
        description: '请求体 JSON',
      },
    },
    output: jsonOutput(),
    async execute(args) {
      return await getClient().invokeHrAgent(args.capability, args.body as Record<string, unknown>) as Record<string, JsonValue>
    },
    presentCall: args => ({
      card: 'generic',
      title: `HR Agent: ${args.capability}`,
      kind: 'other',
      rawInput: args,
    }),
  }))
}

/**
 * Register RecruitOS tools and bundled recruitment skills.
 * @param ctx - Cordis context with tools and skills services.
 * @param config - endpoint URLs and optional auth token.
 */
export function apply(ctx: Context, config: Config = {}): void {
  const getClient = () => buildClient(config)
  registerSkillProvider(ctx)
  registerTools(ctx, getClient)
}

export { HR_AGENT_PATHS, RecruitOsClient } from './recruitos-client.ts'
