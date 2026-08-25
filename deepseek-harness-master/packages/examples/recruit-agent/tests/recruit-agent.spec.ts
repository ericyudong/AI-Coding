import { fileURLToPath } from 'node:url'
import { Context } from '@deepseek-ai/cordis'
import { describe, expect, it, vi, afterEach } from 'vitest'
import SkillRegistry from '@deepseek-ai/dsh-skill'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime from '@deepseek-ai/dsh-tools'
import { CallId } from '@deepseek-ai/dsh-llm'
import * as RecruitAgent from '@deepseek-ai/dsh-recruit-agent'

const testToolSignal = AbortSignal.timeout(5000)

async function setup() {
  const ctx = new Context()
  await ctx.plugin(SystemPrompt)
  await ctx.plugin(SkillRegistry)
  await ctx.plugin(ToolRuntime)
  return ctx
}

describe('dsh-recruit-agent', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    delete process.env.RECRUITOS_JWT
    delete process.env.RECRUITOS_TOKEN
  })

  it('registers bundled recruitment skills', async () => {
    const ctx = await setup()
    const fiber = await ctx.plugin(RecruitAgent, {
      authToken: 'test-token',
    })
    const resourcePath = fileURLToPath(new URL('../assets/skills/', import.meta.url))

    const listed = await ctx.skills.list()
    expect(listed.map(s => s.name).sort()).toEqual([
      'hr-analytics',
      'hr-interview',
      'hr-jd',
      'hr-offer',
      'hr-recruitment',
      'hr-resume',
    ])
    expect(listed[0].resourceBase).toEqual({ kind: 'directory', path: resourcePath })

    const loaded = await ctx.skills.get('hr-recruitment')
    expect(loaded?.content).toContain('RecruitOS')

    await fiber.dispose()
    expect(await ctx.skills.list()).toEqual([])
  })

  it('registers recruitos and hr_agent tools', async () => {
    const ctx = await setup()
    await ctx.plugin(RecruitAgent, { authToken: 'test-token' })

    const names = ctx.tools.schemas().map(s => s.name).sort()
    expect(names).toEqual([
      'hr_agent_invoke',
      'recruitos_propose_action',
      'recruitos_query',
      'recruitos_save_draft',
      'recruitos_search',
    ])
  })

  it('loads without auth token until a tool executes', async () => {
    const ctx = await setup()
    await ctx.plugin(RecruitAgent)
    expect(await ctx.skills.list()).toHaveLength(6)
    const result = await ctx.tools.execute({
      signal: testToolSignal,
      callId: CallId('c1'),
      name: 'recruitos_query',
      arguments: { objectType: 'job', id: 'job-1' },
    })
    expect(result.isError).toBe(true)
    expect(result.error?.message).toMatch(/RECRUITOS_JWT|authToken|认证/)
  })

  it('calls RecruitOS query through the tool executor', async () => {
    const fetchMock = vi.fn(async (url: string) => ({
      ok: true,
      json: async () => ({ id: 'job-1', title: '后端工程师' }),
      status: 200,
    }))
    vi.stubGlobal('fetch', fetchMock)

    process.env.RECRUITOS_JWT = 'env-token'
    const ctx = await setup()
    await ctx.plugin(RecruitAgent)

    const tool = ctx.tools.get('recruitos_query')
    expect(tool).toBeDefined()
    const result = await ctx.tools.execute({
      signal: testToolSignal,
      callId: CallId('c1'),
      name: 'recruitos_query',
      arguments: { objectType: 'job', id: 'job-1' },
    })
    expect(result.value).toEqual({ id: 'job-1', title: '后端工程师' })
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:3001/api/agent/query/job/job-1',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer env-token' }),
      }),
    )
  })
})
