/**
 * HTTP client for Legal Agent FastAPI backend.
 */

import { readFile, stat } from 'node:fs/promises'
import path from 'node:path'

export interface LegalAgentConfig {
  baseUrl: string
  token?: string
  username?: string
  password?: string
}

export interface SearchResult {
  answer: string
  search_type: string
  references: string[]
}

export interface ChatResult {
  session_id: number
  reply: { content: string }
}

export interface ContractDraftResult {
  id: number
  content: string
  draft_type: string
  purpose: string
  style: string
}

export interface ContractReviewResult {
  id: number
  filename: string
  review_mode: string
  status: string
  result: string
  content_preview: string
  char_count: number
  parse_warnings: string[]
}

export interface ContractCompareResult {
  left_filename: string
  right_filename: string
  summary: Record<string, unknown>
  changes: Array<{
    change_type: string
    section: string
    left_text: string
    right_text: string
    detail?: string | null
    ai_note?: string | null
  }>
  risk_note: string
  elapsed_ms: number
}

export interface ContentMetadata {
  search_types: Array<{ id: string; label: string }>
  draft_styles: string[]
  chat_modules: Array<{ id: string; label: string }>
}

const CHAT_MODULES = [
  { id: 'labor_law', label: '劳动法' },
  { id: 'qa', label: '法律问答' },
  { id: 'financial', label: '金融合规' },
  { id: 'overseas', label: '企业出海' },
] as const

export class LegalAgentClient {
  private token: string | undefined
  private loginPromise: Promise<string> | undefined

  constructor(private readonly config: LegalAgentConfig) {
    this.token = config.token?.trim() || undefined
  }

  static fromEnv(): LegalAgentClient {
    return new LegalAgentClient({
      baseUrl: process.env.LEGAL_AGENT_URL ?? 'http://127.0.0.1:8010',
      token: process.env.LEGAL_AGENT_TOKEN,
      username: process.env.LEGAL_AGENT_USERNAME ?? 'admin',
      password: process.env.LEGAL_AGENT_PASSWORD ?? 'admin123',
    })
  }

  private base(pathname: string): string {
    return `${this.config.baseUrl.replace(/\/$/, '')}${pathname.startsWith('/') ? pathname : `/${pathname}`}`
  }

  private async ensureToken(): Promise<string> {
    if (this.token) return this.token
    if (!this.loginPromise) {
      this.loginPromise = this.login()
    }
    this.token = await this.loginPromise
    return this.token
  }

  private async login(): Promise<string> {
    const username = this.config.username
    const password = this.config.password
    if (!username || !password) {
      throw new Error('未配置 LEGAL_AGENT_TOKEN，且缺少 LEGAL_AGENT_USERNAME / LEGAL_AGENT_PASSWORD')
    }
    const res = await fetch(this.base('/api/v1/auth/login'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      signal: AbortSignal.timeout(30_000),
    })
    const data = await res.json().catch(() => ({})) as { access_token?: string; detail?: string }
    if (!res.ok || !data.access_token) {
      const detail = data.detail ?? `登录失败 (${res.status})`
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
    }
    return data.access_token
  }

  private async request<T>(method: string, pathname: string, body?: unknown): Promise<T> {
    const token = await this.ensureToken()
    const res = await fetch(this.base(pathname), {
      method,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(180_000),
    })
    const data = await res.json().catch(() => ({})) as T & { detail?: string | unknown }
    if (!res.ok) {
      const detail = data.detail
      const message = typeof detail === 'string'
        ? detail
        : detail !== undefined
          ? JSON.stringify(detail)
          : `${method} ${pathname} → ${res.status}`
      throw new Error(message)
    }
    return data as T
  }

  async search(query: string, searchType = 'comprehensive', optimize = false): Promise<SearchResult> {
    return this.request('POST', '/api/v1/search', { query, search_type: searchType, optimize })
  }

  async chat(message: string, module = 'labor_law', sessionId?: number): Promise<ChatResult> {
    const body: Record<string, unknown> = { message, module }
    if (sessionId !== undefined) body.session_id = sessionId
    const data = await this.request<{
      session_id: number
      reply: { content: string }
    }>('POST', '/api/v1/chat', body)
    return { session_id: data.session_id, reply: { content: data.reply.content } }
  }

  async draftContract(params: {
    purpose: string
    position?: string
    extra_info?: string
    style?: string
    draft_type?: string
  }): Promise<ContractDraftResult> {
    return this.request('POST', '/api/v1/contract/draft', {
      purpose: params.purpose,
      position: params.position ?? '',
      extra_info: params.extra_info ?? '',
      style: params.style ?? '简明居中',
      draft_type: params.draft_type ?? 'contract',
    })
  }

  async uploadContract(filePath: string, reviewMode = 'checklist'): Promise<ContractReviewResult> {
    const resolved = path.resolve(filePath)
    const fileStat = await stat(resolved)
    if (!fileStat.isFile()) {
      throw new Error(`文件不存在: ${resolved}`)
    }
    const ext = path.extname(resolved).toLowerCase()
    if (!['.doc', '.docx', '.pdf'].includes(ext)) {
      throw new Error('仅支持 doc、docx、pdf 格式')
    }

    const token = await this.ensureToken()
    const form = new FormData()
    const buffer = await readFile(resolved)
    const blob = new Blob([buffer])
    form.append('file', blob, path.basename(resolved))
    form.append('review_mode', reviewMode)

    const res = await fetch(this.base('/api/v1/contract/upload'), {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
      signal: AbortSignal.timeout(180_000),
    })
    const data = await res.json().catch(() => ({})) as ContractReviewResult & { detail?: string }
    if (!res.ok) {
      throw new Error(typeof data.detail === 'string' ? data.detail : `上传失败 (${res.status})`)
    }
    return data
  }

  async runReview(reviewId: number): Promise<ContractReviewResult> {
    return this.request('POST', `/api/v1/contract/review/${reviewId}`)
  }

  async reviewContractFile(filePath: string, reviewMode = 'checklist'): Promise<ContractReviewResult> {
    const uploaded = await this.uploadContract(filePath, reviewMode)
    return this.runReview(uploaded.id)
  }

  async compareContractFiles(leftPath: string, rightPath: string): Promise<ContractCompareResult> {
    const left = path.resolve(leftPath)
    const right = path.resolve(rightPath)
    for (const p of [left, right]) {
      const fileStat = await stat(p)
      if (!fileStat.isFile()) throw new Error(`文件不存在: ${p}`)
      const ext = path.extname(p).toLowerCase()
      if (!['.doc', '.docx', '.pdf'].includes(ext)) {
        throw new Error(`仅支持 doc、docx、pdf 格式: ${p}`)
      }
    }

    const token = await this.ensureToken()
    const form = new FormData()
    const leftBuf = await readFile(left)
    const rightBuf = await readFile(right)
    form.append('left_file', new Blob([leftBuf]), path.basename(left))
    form.append('right_file', new Blob([rightBuf]), path.basename(right))

    const res = await fetch(this.base('/api/v1/contract/compare'), {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
      signal: AbortSignal.timeout(180_000),
    })
    const data = await res.json().catch(() => ({})) as ContractCompareResult & { detail?: string }
    if (!res.ok) {
      throw new Error(typeof data.detail === 'string' ? data.detail : `比对失败 (${res.status})`)
    }
    return data
  }

  async getMetadata(): Promise<ContentMetadata> {
    const searchTypesRes = await this.request<{ items: Array<{ id: string; label: string }> }>(
      'GET',
      '/api/v1/content/search-types',
    ).catch(() => ({ items: [
      { id: 'comprehensive', label: '综合分析' },
      { id: 'regulation', label: '法规查询' },
      { id: 'case', label: '类案检索' },
      { id: 'penalty', label: '行政处罚' },
      { id: 'interpretation', label: '专业解读' },
    ] }))

    const draftStylesRes = await this.request<{ items: string[] }>(
      'GET',
      '/api/v1/content/draft-styles',
    ).catch(() => ({ items: ['简明居中', '详细严谨', '偏向甲方', '偏向乙方'] }))

    return {
      search_types: searchTypesRes.items,
      draft_styles: draftStylesRes.items,
      chat_modules: [...CHAT_MODULES],
    }
  }
}

/** Format API result as MCP text content. */
export function formatJson(data: unknown): string {
  return JSON.stringify(data, null, 2)
}
