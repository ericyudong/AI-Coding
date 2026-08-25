/**
 * HTTP client for RecruitOS agent APIs and HR Agent AI endpoints.
 * @module @deepseek-ai/dsh-recruit-agent/recruitos-client
 */

export interface RecruitAgentEndpoints {
  recruitosBaseUrl: string
  hrAgentBaseUrl: string
  authToken: string
}

/** RecruitOS structured query, search, draft, and action client. */
export class RecruitOsClient {
  constructor(private readonly endpoints: RecruitAgentEndpoints) {}

  private async request<T>(baseUrl: string, method: string, path: string, body?: unknown): Promise<T> {
    const url = `${baseUrl.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`
    const res = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.endpoints.authToken}`,
      },
      body: body !== undefined ? JSON.stringify(body) : null,
      signal: AbortSignal.timeout(120_000),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      const message = typeof (data as { message?: string }).message === 'string'
        ? (data as { message: string }).message
        : `${method} ${path} → ${res.status}`
      throw new Error(message)
    }
    return data as T
  }

  query(objectType: string, id: string) {
    return this.request(this.endpoints.recruitosBaseUrl, 'GET', `/api/agent/query/${objectType}/${id}`)
  }

  search(q: string, type?: string) {
    const qs = new URLSearchParams({ q })
    if (type) qs.set('type', type)
    return this.request(this.endpoints.recruitosBaseUrl, 'GET', `/api/agent/search?${qs}`)
  }

  saveDraft(payload: { type: string, content: string, refType?: string, refId?: string }) {
    return this.request(this.endpoints.recruitosBaseUrl, 'POST', '/api/agent/drafts', {
      ...payload,
      agentId: 'dsh-recruit-agent',
    })
  }

  proposeAction(payload: {
    actionKey: string
    payload: unknown
    idempotencyKey?: string
    autoConfirm?: boolean
  }) {
    return this.request(this.endpoints.recruitosBaseUrl, 'POST', '/api/agent/actions', {
      ...payload,
      agentId: 'dsh-recruit-agent',
    })
  }

  invokeHrAgent(capability: string, body: Record<string, unknown>) {
    const path = HR_AGENT_PATHS[capability]
    if (!path) {
      throw new Error(`未知 HR 能力: ${capability}。可选: ${Object.keys(HR_AGENT_PATHS).join(', ')}`)
    }
    return this.request(this.endpoints.hrAgentBaseUrl, 'POST', path, body)
  }
}

/** HR Agent capability keys mapped to HTTP paths. */
export const HR_AGENT_PATHS: Record<string, string> = {
  jd: '/ai/jd/generate',
  publish: '/ai/jd/publish-pack',
  resume_parse: '/ai/resume/parse',
  resume_screen: '/ai/resume/screen',
  talent: '/ai/talent/recommend',
  sourcing: '/ai/sourcing/run',
  schedule: '/ai/interview/schedule-assist',
  summary: '/ai/interview/summary',
  multimodal: '/ai/interview/multimodal-assess',
  nurture: '/ai/nurture/reply',
  offer: '/ai/offer/draft',
  analytics: '/ai/analytics/ask',
  chat: '/ai/chat',
}
