import http from './http'

export interface Supplier {
  id: number
  name: string
  credit_code: string
  contact: string
  industry: string
  risk_level: string
  contract_count: number
  total_amount: number
  delay_count: number
  notes: string
}

export interface Customer {
  id: number
  name: string
  credit_code: string
  contact: string
  industry: string
  risk_level: string
  contract_count: number
  order_count: number
  total_sales: number
  total_qty: number
  payment_delay_count: number
  notes: string
  related: Array<{
    id: number
    name: string
    relation_type: string
    equity_ratio: number
    total_sales: number
    contract_count: number
  }>
}

export interface PerformanceOverview {
  total_plans: number
  active_plans: number
  pending_confirm: number
  upcoming_alerts: number
  overdue_nodes: number
  my_todos: Array<{
    node_id: number
    plan_id: number
    contract_id: number
    contract_name: string
    title: string
    due_date: string | null
    days_left: number | null
    status: string
    owners: number[]
  }>
}

export interface PerformancePlan {
  id: number
  contract_id: number
  contract_name: string
  status: string
  confirmed_at: string | null
  nodes: Array<{
    id: number
    title: string
    node_type: string
    due_date: string | null
    duration_days: number | null
    status: string
    confirm_status: string
    owner_ids: number[]
    primary_owner_id: number | null
    notes: string
  }>
}

export interface AdminUser {
  id: number
  username: string
  email: string
  display_name: string
  role: string
  department_id: number | null
  department_name: string | null
  is_active: boolean
  features: string[]
}

export async function fetchWorkbenchRecommendations() {
  const { data } = await http.get<{ questions: string[]; role: string; role_label: string }>(
    '/admin/workbench/recommendations',
  )
  return data
}

export async function fetchPerformanceOverview() {
  const { data } = await http.get<PerformanceOverview>('/performance/overview')
  return data
}

export async function fetchSuppliers() {
  const { data } = await http.get<Supplier[]>('/performance/suppliers')
  return data
}

export async function fetchCustomers(merged = false) {
  const { data } = await http.get<Customer[]>('/performance/customers', { params: { merged } })
  return data
}

export async function fetchPerformancePlan(contractId: number) {
  const { data } = await http.get<PerformancePlan>(`/performance/contracts/${contractId}/plan`)
  return data
}

export async function extractPerformancePlan(contractId: number) {
  const { data } = await http.post<PerformancePlan>(`/performance/contracts/${contractId}/extract`)
  return data
}

export async function confirmPerformancePlan(planId: number) {
  const { data } = await http.post<PerformancePlan>(`/performance/plans/${planId}/confirm`)
  return data
}

export async function updatePerformanceNode(nodeId: number, body: Record<string, unknown>) {
  const { data } = await http.patch(`/performance/nodes/${nodeId}`, body)
  return data
}

export interface PerformanceAlert {
  id: number
  node_id: number
  alert_type: string
  message: string
  is_read: boolean
  email_status?: string
  email_sent_at?: string | null
  email_error?: string
  created_at: string | null
}

export interface PendingAdjustment {
  id: number
  node_id: number
  node_title: string
  contract_id: number | null
  contract_name: string
  reason: string
  evidence_note: string
  evidence_path?: string
  evidence_filename?: string
  new_due_date: string | null
  applicant_id: number
  created_at: string | null
}

export async function submitPerformanceAdjustment(
  nodeId: number,
  body: {
    reason: string
    evidence_note?: string
    evidence_path?: string
    evidence_filename?: string
    new_due_date?: string | null
    new_owner_ids?: number[]
  },
) {
  const { data } = await http.post<{ id: number; status: string }>(`/performance/nodes/${nodeId}/adjust`, body)
  return data
}

export async function uploadPerformanceEvidence(nodeId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<{ evidence_path: string; evidence_filename: string; size: number }>(
    `/performance/nodes/${nodeId}/evidence`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  )
  return data
}

export async function reviewPerformanceAdjustment(adjustmentId: number, approve: boolean, note = '') {
  const { data } = await http.post<{ id: number; status: string }>(
    `/performance/adjustments/${adjustmentId}/review`,
    null,
    { params: { approve, note } },
  )
  return data
}

export async function fetchPendingAdjustments() {
  const { data } = await http.get<PendingAdjustment[]>('/performance/adjustments/pending')
  return data
}

export async function fetchPerformanceAlerts() {
  const { data } = await http.get<PerformanceAlert[]>('/performance/alerts')
  return data
}

export async function markPerformanceAlertRead(alertId: number) {
  const { data } = await http.post<{ ok: boolean }>(`/performance/alerts/${alertId}/read`)
  return data
}

export async function dispatchPerformanceAlerts() {
  const { data } = await http.post<{ created: number; email: Record<string, number> }>(
    '/performance/alerts/dispatch',
  )
  return data
}

export interface ErpOrder {
  id: number
  external_id: string
  order_no: string
  customer_id: number | null
  contract_id: number | null
  contract_code: string
  customer_name: string
  product_name: string
  qty: number
  unit_price: number
  amount: number
  order_date: string | null
  delivery_date: string | null
  status: string
  link_status: string
  source: string
}

export async function importErpOrders(file: File) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<{
    job_id: number
    row_count: number
    linked_count: number
    errors: string[]
    status: string
  }>('/performance/orders/import', form, { headers: { 'Content-Type': 'multipart/form-data' } })
  return data
}

export async function fetchErpOrders(params: { customer_id?: number; link_status?: string } = {}) {
  const { data } = await http.get<ErpOrder[]>('/performance/orders', { params })
  return data
}

export async function linkErpOrder(orderId: number, body: { customer_id?: number | null; contract_id?: number | null }) {
  const { data } = await http.patch<ErpOrder>(`/performance/orders/${orderId}/link`, body)
  return data
}

export async function fetchErpSyncJobs() {
  const { data } = await http.get<
    Array<{ id: number; filename: string; status: string; row_count: number; linked_count: number; error_log: string; created_at: string | null }>
  >('/performance/orders/sync-jobs')
  return data
}

export async function addCustomerRelation(
  customerId: number,
  relatedCustomerId: number,
  relationType = 'sibling',
  equityRatio = 1,
) {
  const { data } = await http.post(`/performance/customers/${customerId}/relations`, {
    related_customer_id: relatedCustomerId,
    relation_type: relationType,
    equity_ratio: equityRatio,
  })
  return data
}

export async function fetchAdminUsers() {
  const { data } = await http.get<AdminUser[]>('/admin/users')
  return data
}

export async function fetchDepartments() {
  const { data } = await http.get<Array<{ id: number; name: string; code: string }>>('/admin/departments')
  return data
}

export async function fetchRoles() {
  const { data } = await http.get<Array<{ id: string; label: string }>>('/admin/roles')
  return data
}

export async function createAdminUser(body: Record<string, unknown>) {
  const { data } = await http.post<AdminUser>('/admin/users', body)
  return data
}

export async function updateAdminUser(userId: number, body: Record<string, unknown>) {
  const { data } = await http.put<AdminUser>(`/admin/users/${userId}`, body)
  return data
}
