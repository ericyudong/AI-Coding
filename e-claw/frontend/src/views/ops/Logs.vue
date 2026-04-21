<template>
  <div class="logs-page">
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="page-header">
          <h2>日志查看</h2>
          <div class="header-actions">
            <el-button type="primary" @click="loadLogs" :loading="loading">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
            <el-button @click="exportLogs">
              <el-icon><Download /></el-icon>导出
            </el-button>
            <el-button type="danger" @click="clearLogs" :disabled="!logs.length">
              <el-icon><Delete /></el-icon>清空
            </el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- Filters -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="日志级别">
          <el-select v-model="filters.level" placeholder="全部" clearable style="width: 120px">
            <el-option label="全部" value="" />
            <el-option label="DEBUG" value="DEBUG" />
            <el-option label="INFO" value="INFO" />
            <el-option label="WARNING" value="WARNING" />
            <el-option label="ERROR" value="ERROR" />
            <el-option label="CRITICAL" value="CRITICAL" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="搜索日志内容" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="filters.source" placeholder="全部" clearable style="width: 150px">
            <el-option label="全部" value="" />
            <el-option label="系统" value="system" />
            <el-option label="认证" value="auth" />
            <el-option label="任务" value="task" />
            <el-option label="知识库" value="knowledge" />
            <el-option label="API" value="api" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadLogs">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Log Stats -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总日志数</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card error">
          <div class="stat-value">{{ stats.error }}</div>
          <div class="stat-label">错误</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card warning">
          <div class="stat-value">{{ stats.warning }}</div>
          <div class="stat-label">警告</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card info">
          <div class="stat-value">{{ stats.info }}</div>
          <div class="stat-label">信息</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card debug">
          <div class="stat-value">{{ stats.debug }}</div>
          <div class="stat-label">调试</div>
        </div>
      </el-col>
    </el-row>

    <!-- Auto Refresh Toggle -->
    <div class="auto-refresh">
      <el-switch v-model="autoRefresh" />
      <span>自动刷新 ({{ autoRefreshInterval }}秒)</span>
      <el-slider 
        v-model="autoRefreshInterval" 
        :min="5" 
        :max="60" 
        :step="5" 
        style="width: 150px; margin-left: 10px"
        :disabled="!autoRefresh"
      />
    </div>

    <!-- Log List -->
    <el-card class="logs-card">
      <el-table 
        :data="displayLogs" 
        v-loading="loading" 
        style="width: 100%"
        :row-class-name="getRowClassName"
        max-height="600"
      >
        <el-table-column prop="timestamp" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.timestamp) }}
          </template>
        </el-table-column>
        <el-table-column prop="level" label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="getLevelType(row.level)" size="small">
              {{ row.level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="100" />
        <el-table-column prop="message" label="内容" min-width="400">
          <template #default="{ row }">
            <div class="log-message" @click="showLogDetail(row)">
              {{ row.message }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="showLogDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="total"
          :page-sizes="[50, 100, 200, 500]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadLogs"
          @current-change="loadLogs"
        />
      </div>
    </el-card>

    <!-- Log Detail Dialog -->
    <el-dialog v-model="showDetailDialog" title="日志详情" width="700px">
      <el-descriptions :column="2" border v-if="currentLog">
        <el-descriptions-item label="时间">{{ formatTime(currentLog.timestamp) }}</el-descriptions-item>
        <el-descriptions-item label="级别">
          <el-tag :type="getLevelType(currentLog.level)">{{ currentLog.level }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="来源">{{ currentLog.source }}</el-descriptions-item>
        <el-descriptions-item label="模块">{{ currentLog.module || '-' }}</el-descriptions-item>
        <el-descriptions-item label="内容" :span="2">
          <pre class="log-content">{{ currentLog.message }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="堆栈信息" :span="2" v-if="currentLog.traceback">
          <pre class="log-traceback">{{ currentLog.traceback }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="请求ID" :span="2">{{ currentLog.request_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="用户ID" :span="2">{{ currentLog.user_id || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { Refresh, Download, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const logs = ref<any[]>([])
const total = ref(0)
const showDetailDialog = ref(false)
const currentLog = ref<any>(null)
const autoRefresh = ref(false)
const autoRefreshInterval = ref(10)

let autoRefreshTimer: ReturnType<typeof setInterval> | null = null

const filters = reactive({
  level: '',
  dateRange: [] as string[],
  keyword: '',
  source: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 100
})

const stats = reactive({
  total: 0,
  error: 0,
  warning: 0,
  info: 0,
  debug: 0
})

// Filtered logs
const displayLogs = computed(() => {
  return logs.value
})

// Calculate stats
const calculateStats = () => {
  stats.total = logs.value.length
  stats.error = logs.value.filter(l => l.level === 'ERROR' || l.level === 'CRITICAL').length
  stats.warning = logs.value.filter(l => l.level === 'WARNING').length
  stats.info = logs.value.filter(l => l.level === 'INFO').length
  stats.debug = logs.value.filter(l => l.level === 'DEBUG').length
}

const getLevelType = (level: string) => {
  const typeMap: Record<string, string> = {
    'DEBUG': 'info',
    'INFO': 'success',
    'WARNING': 'warning',
    'ERROR': 'danger',
    'CRITICAL': 'danger'
  }
  return typeMap[level] || 'info'
}

const getRowClassName = ({ row }: any) => {
  if (row.level === 'ERROR' || row.level === 'CRITICAL') return 'error-row'
  if (row.level === 'WARNING') return 'warning-row'
  return ''
}

const formatTime = (timestamp: string) => {
  if (!timestamp) return '-'
  return new Date(timestamp).toLocaleString('zh-CN')
}

const loadLogs = async () => {
  loading.value = true
  try {
    // Call API with filters
    const params: any = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    
    if (filters.level) params.level = filters.level
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.source) params.source = filters.source
    if (filters.dateRange && filters.dateRange.length === 2) {
      params.start_date = filters.dateRange[0]
      params.end_date = filters.dateRange[1]
    }

    // Use mock data for demo
    const mockLogs = generateMockLogs(50)
    
    // Apply filters locally for demo
    let filtered = mockLogs
    if (filters.level) {
      filtered = filtered.filter(l => l.level === filters.level)
    }
    if (filters.keyword) {
      filtered = filtered.filter(l => l.message.toLowerCase().includes(filters.keyword.toLowerCase()))
    }
    if (filters.source) {
      filtered = filtered.filter(l => l.source === filters.source)
    }
    
    logs.value = filtered
    total.value = filtered.length
    
    calculateStats()
  } catch (error) {
    console.error('Failed to load logs:', error)
  } finally {
    loading.value = false
  }
}

// Generate mock logs for demo
const generateMockLogs = (count: number) => {
  const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
  const sources = ['system', 'auth', 'task', 'knowledge', 'api']
  const messages = {
    DEBUG: [
      'Starting request processing',
      'Database query executed in 5ms',
      'Cache hit for key: user_session_123',
      'Loading configuration from file',
      'WebSocket connection established'
    ],
    INFO: [
      'User login successful',
      'Task created successfully',
      'Document uploaded to knowledge base',
      'System health check passed',
      'Backup completed successfully'
    ],
    WARNING: [
      'High memory usage detected: 85%',
      'Rate limit approaching for API key',
      'Token quota low for user 12345',
      'Disk space below threshold: 20%',
      'Session timeout for user'
    ],
    ERROR: [
      'Database connection failed: timeout',
      'Failed to process task: invalid input',
      'Authentication failed: invalid token',
      'API request failed: 500 internal error',
      'File upload failed: size exceeds limit'
    ],
    CRITICAL: [
      'Database connection lost',
      'System out of memory',
      'Disk write failed: no space left',
      'Security breach detected'
    ]
  }

  const result = []
  const now = new Date()
  
  for (let i = 0; i < count; i++) {
    const level = levels[Math.floor(Math.random() * levels.length)]
    const source = sources[Math.floor(Math.random() * sources.length)]
    const levelMessages = messages[level as keyof typeof messages]
    const message = levelMessages[Math.floor(Math.random() * levelMessages.length)]
    
    const timestamp = new Date(now.getTime() - Math.random() * 3600000 * 24) // Last 24 hours
    
    result.push({
      id: `log-${i}`,
      timestamp: timestamp.toISOString(),
      level,
      source,
      message,
      module: `app.${source}`,
      request_id: `req-${Math.random().toString(36).substr(2, 9)}`,
      user_id: Math.random() > 0.5 ? `user-${Math.floor(Math.random() * 1000)}` : null,
      traceback: level === 'ERROR' || level === 'CRITICAL' ? 
        `Traceback (most recent call last):
  File "/app/api/v1/${source}.py", line ${Math.floor(Math.random() * 100) + 10}, in process
    raise ValueError("Error occurred")
ValueError: Some error message` : null
    })
  }
  
  return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
}

const resetFilters = () => {
  filters.level = ''
  filters.dateRange = []
  filters.keyword = ''
  filters.source = ''
  pagination.page = 1
  loadLogs()
}

const showLogDetail = (row: any) => {
  currentLog.value = row
  showDetailDialog.value = true
}

const exportLogs = () => {
  const content = logs.value.map(log => {
    return `[${log.timestamp}] [${log.level}] [${log.source}] ${log.message}`
  }).join('\n')
  
  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `e-claw-logs-${new Date().toISOString().split('T')[0]}.log`
  a.click()
  URL.revokeObjectURL(url)
  
  ElMessage.success('日志导出成功')
}

const clearLogs = async () => {
  try {
    await ElMessageBox.confirm('确认要清空当前显示的日志吗?', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    logs.value = []
    total.value = 0
    calculateStats()
    ElMessage.success('日志已清空')
  } catch (e) {
    // User cancelled
  }
}

// Auto refresh
watch(autoRefresh, (value) => {
  if (value) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

watch(autoRefreshInterval, () => {
  if (autoRefresh.value) {
    stopAutoRefresh()
    startAutoRefresh()
  }
})

const startAutoRefresh = () => {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
  }
  autoRefreshTimer = setInterval(() => {
    loadLogs()
  }, autoRefreshInterval.value * 1000)
}

const stopAutoRefresh = () => {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

onMounted(() => {
  loadLogs()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.logs-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.filter-card {
  margin-bottom: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 15px;
  text-align: center;
}

.stat-card.error {
  background: #fef0f0;
}

.stat-card.warning {
  background: #fdf6ec;
}

.stat-card.info {
  background: #f0f9ff;
}

.stat-card.debug {
  background: #f4f4f5;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-card.error .stat-value {
  color: #f56c6c;
}

.stat-card.warning .stat-value {
  color: #e6a23c;
}

.stat-card.info .stat-value {
  color: #409eff;
}

.stat-card.debug .stat-value {
  color: #909399;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.auto-refresh {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
  gap: 10px;
}

.auto-refresh span {
  color: #606266;
  font-size: 14px;
}

.logs-card {
  margin-bottom: 20px;
}

.log-message {
  cursor: pointer;
  word-break: break-all;
}

.log-message:hover {
  color: #409eff;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.log-content, .log-traceback {
  margin: 0;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 13px;
}

.log-traceback {
  color: #f56c6c;
  background: #fef0f0;
}

:deep(.error-row) {
  background-color: #fef0f0 !important;
}

:deep(.warning-row) {
  background-color: #fdf6ec !important;
}
</style>