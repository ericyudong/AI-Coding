import http from './http'

export interface UserInfo {
  id: number
  username: string
  email: string
  display_name: string
  role?: string
  department_id?: number | null
  department_name?: string | null
  is_active?: boolean
  features?: string[]
}

export interface ContractReviewItem {
  id: number
  filename: string
  review_mode: string
  status: string
  result: string
  content_text: string
  content_preview: string
  char_count: number
  parse_status: string
  parse_warnings: string[]
  created_at: string
}

export interface ContractDraftItem {
  id: number
  content: string
  created_at: string
  draft_type?: string
  purpose?: string
  position?: string
  extra_info?: string
  style?: string
}

export interface ContractCompareChange {
  change_type: string
  section: string
  left_text: string
  right_text: string
  detail?: string
  ai_note?: string
}

export interface ContractCompareResult {
  left_filename: string
  right_filename: string
  summary: Record<string, number>
  changes: ContractCompareChange[]
  risk_note: string
  elapsed_ms: number
}

export async function login(username: string, password: string) {
  const { data } = await http.post<{ access_token: string }>('/auth/login', { username, password })
  return data
}

export async function fetchMe() {
  const { data } = await http.get<UserInfo>('/auth/me')
  return data
}

export async function fetchQuickLinks() {
  const { data } = await http.get('/content/quick-links')
  return data
}

export async function fetchAiModules() {
  const { data } = await http.get('/content/ai-modules')
  return data
}

export async function fetchNews(category?: string) {
  const { data } = await http.get('/content/news', { params: { category } })
  return data
}

export async function fetchSearchSuggestions() {
  const { data } = await http.get<{ items: string[] }>('/content/search-suggestions')
  return data.items
}

export async function fetchLaborExamples() {
  const { data } = await http.get<{ items: string[] }>('/content/labor-examples')
  return data.items
}

export async function fetchSearchTypes() {
  const { data } = await http.get<{ items: { id: string; label: string }[] }>('/content/search-types')
  return data.items
}

export async function fetchDraftStyles() {
  const { data } = await http.get<{ items: string[] }>('/content/draft-styles')
  return data.items
}

export async function legalSearch(query: string, searchType: string) {
  const { data } = await http.post('/search', { query, search_type: searchType })
  return data
}

export async function sendChat(message: string, module: string, sessionId?: number) {
  const { data } = await http.post('/chat', { message, module, session_id: sessionId })
  return data
}

export async function uploadContract(file: File, reviewMode: string) {
  const form = new FormData()
  form.append('file', file)
  form.append('review_mode', reviewMode)
  const { data } = await http.post<ContractReviewItem>('/contract/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function runContractReview(reviewId: number) {
  const { data } = await http.post<ContractReviewItem>(`/contract/review/${reviewId}`)
  return data
}

export async function fetchReviewHistory() {
  const { data } = await http.get<ContractReviewItem[]>('/contract/reviews')
  return data
}

export async function draftContract(payload: {
  draft_type: string
  purpose: string
  position: string
  extra_info: string
  style: string
}) {
  const { data } = await http.post<ContractDraftItem>('/contract/draft', payload)
  return data
}

export async function fetchDraftHistory() {
  const { data } = await http.get<ContractDraftItem[]>('/contract/drafts')
  return data
}

export async function compareContractFiles(left: File, right: File) {
  const form = new FormData()
  form.append('left_file', left)
  form.append('right_file', right)
  const { data } = await http.post<ContractCompareResult>('/contract/compare', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
