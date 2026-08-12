import http from './http'

export interface ContractStats {
  total: number
  active: number
  expiring_soon: number
  expired: number
  pending_sign: number
  archived: number
  high_risk: number
}

export interface ContractItem {
  id: number
  code: string
  name: string
  contract_type: string
  party_a: string
  party_b: string
  amount: number
  currency: string
  sign_date: string | null
  effective_date: string | null
  expire_date: string | null
  status: string
  owner: string
  risk_level: string
  tags: string[]
  tag_level1?: string
  tag_level2?: string
  ai_summary: string
  summary_locked?: boolean
  department_id?: number | null
  parse_status?: string
  content_text: string
  key_clauses: string[]
  created_at: string
  updated_at: string
}

export interface ContractListResult {
  items: ContractItem[]
  total: number
  page: number
  page_size: number
}

export interface ImportLinkSuggestion {
  contract: ContractItem
  match_score: number
  match_reason: string
}

export interface ImportLinkSuggestionsResult {
  items: ImportLinkSuggestion[]
  extracted_name: string
  extracted_party_a: string
  extracted_party_b: string
}

export interface ImportConfirmResult {
  contract: ContractItem
  import_mode: 'new' | 'version'
  version: string | null
}

export interface ImportConfirmOptions {
  target_contract_id?: number
  version_label?: string
}

export interface ImportTask {
  id: number
  filename: string
  status: string
  progress: number
  confidence: number
  extracted: Record<string, unknown>
  parse_warnings?: string[]
  char_count?: number
  retry_count?: number
  created_at: string
}

export interface FieldFilter {
  field: string
  operator: string
  value: string
}

export interface SearchResult {
  items: {
    contract: ContractItem
    relevance: number
    highlight: string
    match_type?: string
  }[]
  total: number
  elapsed_ms: number
  ai_suggestion?: string
  mode?: string
  interpreted_query?: string
  applied_filters?: FieldFilter[]
}

export interface SearchSuggestions {
  suggestions: string[]
  contracts: string[]
}

export type SearchMode = 'hybrid' | 'keyword' | 'semantic' | 'field' | 'regex' | 'natural'

export interface ContractVersion {
  id: number
  version: string
  label: string
  content: string
  is_current: boolean
  created_by: string
  created_at: string
}

export async function fetchCmsStats() {
  const { data } = await http.get<ContractStats>('/cms/stats')
  return data
}

export async function fetchContracts(params: Record<string, string | number>) {
  const { data } = await http.get<ContractListResult>('/cms/contracts', { params })
  return data
}

export async function fetchContract(id: number) {
  const { data } = await http.get<ContractItem>(`/cms/contracts/${id}`)
  return data
}

export async function createContract(payload: Record<string, unknown>) {
  const { data } = await http.post<ContractItem>('/cms/contracts', payload)
  return data
}

export async function updateContract(id: number, payload: Record<string, unknown>) {
  const { data } = await http.put<ContractItem>(`/cms/contracts/${id}`, payload)
  return data
}

export async function batchUpdateContracts(payload: {
  ids: number[]
  status?: string
  owner?: string
  add_tags?: string[]
}) {
  const { data } = await http.post<{ updated: number }>('/cms/contracts/batch', payload)
  return data
}

export async function deleteContract(id: number) {
  await http.delete(`/cms/contracts/${id}`)
}

export async function exportContractsCsv() {
  const response = await http.get('/cms/contracts/export/csv', { responseType: 'blob' })
  const disposition = String(response.headers['content-disposition'] || '')
  const match = disposition.match(/filename="?([^";]+)"?/)
  const filename = match?.[1] || `contracts_${new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15)}.csv`
  return { blob: response.data as Blob, filename }
}

export async function uploadContractImport(file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<ImportTask>('/cms/import/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function fetchImportTask(taskId: number) {
  const { data } = await http.get<ImportTask>(`/cms/import/${taskId}`)
  return data
}

export async function fetchImportTasks(limit = 50) {
  const { data } = await http.get<{ items: ImportTask[]; total: number }>('/cms/import/tasks', {
    params: { limit },
  })
  return data
}

export async function retryImportTask(taskId: number) {
  const { data } = await http.post<ImportTask>(`/cms/import/${taskId}/retry`)
  return data
}

export async function uploadContractImportBatch(files: File[]) {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  const { data } = await http.post<{ items: ImportTask[]; total: number }>('/cms/import/upload-batch', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function updateContractTags(
  id: number,
  payload: { tags: string[]; tag_level1?: string; tag_level2?: string },
) {
  const { data } = await http.put<ContractItem>(`/cms/contracts/${id}/tags`, payload)
  return data
}

export async function updateContractSummary(id: number, ai_summary: string) {
  const { data } = await http.put<ContractItem>(`/cms/contracts/${id}/summary`, { ai_summary })
  return data
}

export async function fetchContractAudits(id: number) {
  const { data } = await http.get<
    Array<{ id: number; action: string; before: Record<string, unknown>; after: Record<string, unknown>; note: string; user_id: number; created_at: string }>
  >(`/cms/contracts/${id}/audits`)
  return data
}

export async function trackAnalytics(event_name: string, props: Record<string, unknown> = {}) {
  await http.post('/cms/analytics/track', { event_name, props })
}

export interface TagTaxonomyNode {
  id: number
  level: number
  code: string
  name: string
  parent_id: number | null
  sort_order: number
  is_active?: boolean
  children?: TagTaxonomyNode[]
}

export async function fetchTagTaxonomy() {
  const { data } = await http.get<TagTaxonomyNode[]>('/cms/tags/taxonomy')
  return data
}

export async function fetchAdminTags(params: { tree?: boolean; all?: boolean } = {}) {
  const { data } = await http.get<TagTaxonomyNode[]>('/admin/tags', {
    params: { tree: params.tree ?? true, all: params.all ?? false },
  })
  return data
}

export async function createAdminTag(body: {
  level: number
  name: string
  code?: string
  parent_id?: number | null
  sort_order?: number
}) {
  const { data } = await http.post('/admin/tags', body)
  return data
}

export async function updateAdminTag(id: number, body: Record<string, unknown>) {
  const { data } = await http.put(`/admin/tags/${id}`, body)
  return data
}

export async function deleteAdminTag(id: number) {
  const { data } = await http.delete(`/admin/tags/${id}`)
  return data
}

export async function fetchImportLinkSuggestions(taskId: number, q = '', limit = 20) {
  const { data } = await http.get<ImportLinkSuggestionsResult>(
    `/cms/import/${taskId}/link-suggestions`,
    { params: { q, limit } },
  )
  return data
}

export async function confirmImport(taskId: number, options: ImportConfirmOptions = {}) {
  const { data } = await http.post<ImportConfirmResult>(`/cms/import/${taskId}/confirm`, options)
  return data
}

export async function searchContracts(q: string, mode: SearchMode = 'hybrid') {
  const { data } = await http.get<SearchResult>('/cms/search', { params: { q, mode } })
  return data
}

export async function advancedSearchContracts(payload: {
  q?: string
  mode?: SearchMode
  filters?: FieldFilter[]
  limit?: number
}) {
  const { data } = await http.post<SearchResult>('/cms/search', payload)
  return data
}

export async function fetchSearchSuggestions(q = '') {
  const { data } = await http.get<SearchSuggestions>('/cms/search/suggestions', { params: { q } })
  return data
}

export async function fetchTagCloud() {
  const { data } = await http.get<{ name: string; count: number }[]>('/cms/tags/cloud')
  return data
}

export async function fetchContractSummary(id: number, summaryType: string) {
  const { data } = await http.get<{ summary_type: string; items: string[] }>(
    `/cms/contracts/${id}/summary`,
    { params: { summary_type: summaryType } }
  )
  return data
}

export async function askContract(id: number, question: string) {
  const { data } = await http.post<{
    answer: string
    citations: string[]
    citation_details?: { section: string; excerpt: string; chunk_id?: number }[]
    confidence: string
  }>(`/cms/contracts/${id}/qa`, { question })
  return data
}

export async function fetchVersions(id: number) {
  const { data } = await http.get<ContractVersion[]>(`/cms/contracts/${id}/versions`)
  return data
}

export async function compareVersions(id: number, leftVersionId: number, rightVersionId: number) {
  const { data } = await http.post<{
    summary: Record<string, number>
    changes: { change_type: string; section: string; left_text: string; right_text: string; detail?: string; ai_note?: string }[]
    risk_note: string
  }>(`/cms/contracts/${id}/compare`, {
    left_version_id: leftVersionId,
    right_version_id: rightVersionId,
  })
  return data
}

export const STATUS_MAP: Record<string, string> = {
  pending_sign: '待签署',
  active: '履行中',
  expired: '已到期',
  archived: '已归档',
  terminated: '已终止',
}

export const TYPE_MAP: Record<string, string> = {
  purchase: '采购合同',
  sales: '销售合同',
  lease: '租赁合同',
  labor: '劳务合同',
  nda: '保密协议',
  tech: '技术开发',
  other: '其他',
}

export function formatAmount(amount: number, currency = 'CNY') {
  if (!amount) return '-'
  const prefix = currency === 'CNY' ? '¥' : currency + ' '
  return `${prefix}${amount.toLocaleString('zh-CN')}`
}
