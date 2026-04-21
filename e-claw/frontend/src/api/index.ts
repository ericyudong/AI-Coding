import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

const baseURL = '/api/v1'

const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    // 打印请求信息
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`, {
      params: config.params,
      data: config.data
    })
    return config
  },
  (error) => {
    console.error('[API Request Error]', error)
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    // 打印响应信息
    console.log(`[API Response] ${response.config.method?.toUpperCase()} ${response.config.url}`, {
      status: response.status,
      data: response.data
    })
    return response.data
  },
  (error) => {
    const message = error.response?.data?.detail || error.message || 'Request failed'
    console.error(`[API Error] ${error.config?.method?.toUpperCase()} ${error.config?.url}`, {
      status: error.response?.status,
      data: error.response?.data,
      message: message
    })
    ElMessage.error(message)
    
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    
    return Promise.reject(error)
  }
)

// Auth API - login uses special /api endpoint, others use /api/v1
export const authApi = {
  login: (username: string, password: string) =>
    axios.post('/api/login', { username, password }),
  register: (data: { username: string; email: string; password: string; full_name?: string }) =>
    api.post('/auth/register', data),
  getCurrentUser: () => api.get('/auth/me'),
  logout: () => api.post('/auth/logout'),
  changePassword: (oldPassword: string, newPassword: string) =>
    api.post('/auth/change-password', { old_password: oldPassword, new_password: newPassword })
}

// Tasks API - using direct endpoint to bypass local_kw issue
export const tasksApi = {
  list: (params?: { status?: string; page?: number; page_size?: number }) =>
    api.get('/direct/tasks', { params }),
  get: (id: string) => api.get(`/tasks/${id}`),
  // 使用FormData提交任务（支持文件上传）
  create: (formData: FormData) =>
    api.post('/tasks', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
  // 批量取消任务
  batchCancel: (ids: string[]) => api.post('/tasks/batch/cancel', { task_ids: ids }),
  // 批量删除任务
  batchDelete: (ids: string[]) => api.post('/tasks/batch/delete', { task_ids: ids }),
  cancel: (id: string) => api.delete(`/tasks/${id}`),
  resume: (id: string) => api.post(`/tasks/${id}/resume`),
  getCheckpoint: (id: string) => api.get(`/tasks/${id}/checkpoint`)
}

// Knowledge API - using direct endpoint to bypass local_kw issue
export const knowledgeApi = {
  list: (params?: { kb_type?: string; page?: number; page_size?: number }) =>
    api.get('/direct/knowledge', { params }),
  get: (id: string) => api.get(`/knowledge/${id}`),
  create: (data: { name: string; description?: string; kb_type: string }) =>
    api.post('/knowledge', data),
  update: (id: string, data: { name?: string; description?: string }) =>
    api.put(`/knowledge/${id}`, data),
  delete: (id: string) => api.delete(`/knowledge/${id}`),
  
  // Documents
  listDocuments: (kbId: string, params?: { page?: number; page_size?: number }) =>
    api.get(`/knowledge/${kbId}/documents`, { params }),
  uploadDocument: (kbId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/knowledge/${kbId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  deleteDocument: (kbId: string, docId: string) => 
    api.delete(`/knowledge/${kbId}/documents/${docId}`),
  
  // Search
  search: (data: { query: string; knowledge_base_id?: string; top_k?: number }) =>
    api.post('/knowledge/search', data)
}

// Admin API
export const adminApi = {
  // Tenants
  listTenants: (params?: { status?: string; page?: number; page_size?: number }): Promise<any[]> =>
    api.get('/admin/tenants', { params }),
  getTenant: (id: string): Promise<any> => api.get(`/admin/tenants/${id}`),
  createTenant: (data: { name: string; code: string; description?: string; total_quota?: number }) =>
    api.post('/direct/tenants', data),
  updateTenant: (id: string, data: { name?: string; description?: string; total_quota?: number; status?: string }) =>
    api.put(`/admin/tenants/${id}`, data),
  deleteTenant: (id: string) => api.delete(`/admin/tenants/${id}`),
  
  // Users
  createUser: (data: { username: string; email: string; password: string; full_name?: string; role?: string; tenant_id?: string; personal_quota?: number }) =>
    api.post('/admin/users', data),
  
  // Audit
  listAuditLogs: (params?: { tenant_id?: string; user_id?: string; action?: string; resource_type?: string; start_date?: string; end_date?: string; page?: number; page_size?: number }) =>
    api.get('/admin/audit', { params }),
  
  // Stats
  getStats: () => api.get('/admin/stats'),
  
  // Knowledge review
  listPendingKnowledge: (params?: { page?: number; page_size?: number }) =>
    api.get('/admin/knowledge/review', { params }),
  approveKnowledge: (id: string) => api.post(`/admin/knowledge/${id}/approve`),
  rejectKnowledge: (id: string, reason?: string) => api.post(`/admin/knowledge/${id}/reject`, { reason })
}

// Kubernetes Monitoring API
export const k8sApi = {
  // Cluster info
  getClusterInfo: () => api.get('/monitor/k8s/cluster'),
  
  // Pods
  getPods: (namespace?: string) => api.get('/monitor/k8s/pods', { params: { namespace } }),
  
  // Nodes
  getNodes: () => api.get('/monitor/k8s/nodes'),
  
  // Namespaces
  getNamespaces: () => api.get('/monitor/k8s/namespaces'),
  
  // System metrics
  getSystemMetrics: () => api.get('/monitor/metrics'),
  
  // Docker containers
  getDockerContainers: () => api.get('/monitor/docker'),
  
  // Processes
  getProcesses: (limit?: number) => api.get('/monitor/processes', { params: { limit } })
}

// Users API - using direct endpoint to bypass local_kw issue
export const usersApi = {
  list: (params?: { page?: number; page_size?: number }) => api.get('/direct/users', { params }),
  get: (id: string) => api.get(`/users/${id}`),
  update: (id: string, data: { full_name?: string; email?: string }) => api.put(`/users/${id}`, data),
  updateQuota: (id: string, data: { personal_quota: number }) => api.put(`/users/${id}/quota`, data),
  disable: (id: string) => api.post(`/users/${id}/disable`),
  enable: (id: string) => api.post(`/users/${id}/enable`)
}

// Instances API - OpenCLAW实例管理
export const instancesApi = {
  // 创建实例
  create: (data: {
    name: string
    description?: string
    instance_type?: string
    cpu_cores?: number
    memory_gb?: number
    disk_gb?: number
    gpu_enabled?: boolean
    gpu_count?: number
    os_type?: string
    os_version?: string
    image_registry?: string
    image_tag?: string
    storage_class?: string
  }) => api.post('/instances', data),
  
  // 获取实例列表 - using direct endpoint to bypass local_kw issue
  list: (params?: { status?: string; page?: number; page_size?: number }) =>
    api.get('/direct/instances', { params }),
  
  // 获取实例详情
  get: (id: string) => api.get(`/instances/${id}`),
  
  // 启动实例
  start: (id: string) => api.post(`/instances/${id}/start`),
  
  // 停止实例
  stop: (id: string) => api.post(`/instances/${id}/stop`),
  
  // 删除实例
  delete: (id: string) => api.delete(`/instances/${id}`),
  
  // 获取镜像模板列表
  getImageTemplates: () => api.get('/instances/image-templates'),
  
  // 保存镜像模板（仅管理员）
  saveImageTemplate: (data: {
    instance_type: string
    image: string
    display_name?: string
    description?: string
  }) => api.post('/instances/image-templates', null, { params: data }),
  
  // 删除镜像模板（仅管理员）
  deleteImageTemplate: (instanceType: string) => 
    api.delete(`/instances/image-templates/${instanceType}`)
}

// AI Gateway API
export const gatewayApi = {
  // Chat completions
  chat: (data: { model?: string; messages: any[]; temperature?: number; max_tokens?: number }) =>
    api.post('/gateway/llm/chat/completions', data),
  
  // Models
  listModels: (params?: { provider?: string; is_active?: boolean }) =>
    api.get('/gateway/llm/models', { params }),
  getModel: (modelId: string) => api.get(`/gateway/llm/models/${modelId}`),
  createModel: (data: { provider_type: string; display_name: string; model_name: string; endpoint: string; api_key_ref?: string; is_secure?: boolean; is_active?: boolean; input_price?: number; output_price?: number; currency?: string }) =>
    api.post('/gateway/llm/models', data),
  updateModel: (modelId: string, data: { display_name?: string; endpoint?: string; api_key_ref?: string; is_secure?: boolean; is_active?: boolean; input_price?: number; output_price?: number; currency?: string }) =>
    api.put(`/gateway/llm/models/${modelId}`, data),
  deleteModel: (modelId: string) => api.delete(`/gateway/llm/models/${modelId}`),
  
  // Risk rules
  listRiskRules: (params?: { category?: string; is_active?: boolean }) =>
    api.get('/gateway/risk-rules', { params }),
  createRiskRule: (data: { name: string; rule_type?: string; pattern: string; category: string; action?: string; is_active?: boolean; priority?: number; description?: string }) =>
    api.post('/gateway/risk-rules', data),
  updateRiskRule: (ruleId: string, data: { name?: string; pattern?: string; category?: string; action?: string; is_active?: boolean; priority?: number; description?: string }) =>
    api.put(`/gateway/risk-rules/${ruleId}`, data),
  deleteRiskRule: (ruleId: string) => api.delete(`/gateway/risk-rules/${ruleId}`),
  testRiskRule: (data: { rule_id: string; text: string }) =>
    api.post('/gateway/risk-rules/test', data),
  
  // Audit
  listAuditLogs: (params?: { user_id?: string; model_id?: string; start_date?: string; end_date?: string; page?: number; page_size?: number }) =>
    api.get('/gateway/audit', { params }),
  getAuditDetail: (traceId: string) => api.get(`/gateway/audit/${traceId}`),
  
  // Costs
  getCosts: (params?: { user_id?: string; days?: number }) =>
    api.get('/gateway/costs', { params }),
  
  // System
  getProviders: () => api.get('/gateway/providers'),
  getRiskCategories: () => api.get('/gateway/risk-categories')
}

// System Config API
export const systemApi = {
  // System config
  getConfig: () => api.get('/system/config'),
  
  // Services
  listServices: (params?: { service_type?: string }) => 
    api.get('/system/config/services', { params }),
  getService: (id: string) => api.get(`/system/config/services/${id}`),
  createService: (data: { name: string; service_type: string; enabled?: boolean; config: object; description?: string }) =>
    api.post('/system/config/services', data),
  updateService: (id: string, data: { name?: string; enabled?: boolean; config?: object; description?: string }) =>
    api.put(`/system/config/services/${id}`, data),
  deleteService: (id: string) => api.delete(`/system/config/services/${id}`),
  
  // LLM Config
  getLLMConfig: () => api.get('/system/config/llm'),
  updateLLMConfig: (data: { provider: string; model: string; api_key?: string; base_url?: string; temperature?: number; max_tokens?: number }) =>
    api.put('/system/config/llm', data),
  
  // RAG Config
  getRAGConfig: () => api.get('/system/config/rag'),
  updateRAGConfig: (data: { chunk_size?: number; chunk_overlap?: number; top_k?: number; vector_store_type?: string; embedding_model?: string; embedding_dim?: number }) =>
    api.put('/system/config/rag', data),
  
  // MCP Config
  getMCPConfig: () => api.get('/system/config/mcp'),
  updateMCPConfig: (data: { enabled: boolean; servers: object[] }) =>
    api.put('/system/config/mcp', data),
  addMCPServer: (server: object) => api.post('/system/config/mcp/servers', server),
  deleteMCPServer: (serverId: string) => api.delete(`/system/config/mcp/servers/${serverId}`)
}

export default api
