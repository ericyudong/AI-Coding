<template>
  <div class="audit-page">
    <!-- Header -->
    <div class="page-header">
      <h2>审计日志</h2>
      <el-button type="primary" @click="exportLogs">
        <el-icon><Download /></el-icon>导出
      </el-button>
    </div>

    <!-- Filters -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="操作类型">
          <el-select v-model="filters.action" placeholder="全部" clearable style="width: 150px">
            <el-option label="全部" value="" />
            <el-option label="登录" value="login" />
            <el-option label="登出" value="logout" />
            <el-option label="创建" value="create" />
            <el-option label="更新" value="update" />
            <el-option label="删除" value="delete" />
            <el-option label="查询" value="query" />
          </el-select>
        </el-form-item>
        <el-form-item label="资源类型">
          <el-select v-model="filters.resource_type" placeholder="全部" clearable style="width: 150px">
            <el-option label="全部" value="" />
            <el-option label="用户" value="user" />
            <el-option label="任务" value="task" />
            <el-option label="知识库" value="knowledge" />
            <el-option label="租户" value="tenant" />
            <el-option label="系统" value="system" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadLogs">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Audit Log Table -->
    <el-card class="table-card">
      <el-table :data="logs" v-loading="loading" style="width: 100%">
        <el-table-column prop="action" label="操作" width="100">
          <template #default="{ row }">
            <el-tag :type="getActionType(row.action)">{{ getActionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="资源类型" width="100">
          <template #default="{ row }">
            {{ getResourceTypeLabel(row.resource_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="resource_id" label="资源ID" width="200" show-overflow-tooltip />
        <el-table-column prop="method" label="方法" width="80" />
        <el-table-column prop="path" label="路径" min-width="200" show-overflow-tooltip />
        <el-table-column prop="ip_address" label="IP地址" width="140" />
        <el-table-column prop="response_status" label="状态码" width="80">
          <template #default="{ row }">
            <el-tag :type="row.response_status >= 400 ? 'danger' : 'success'">{{ row.response_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadLogs"
          @current-change="loadLogs"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { adminApi } from '@/api'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'

const loading = ref(false)
const logs = ref<any[]>([])
const total = ref(0)
const dateRange = ref<[string, string] | null>(null)

const filters = reactive({
  action: '',
  resource_type: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 50
})

const getActionType = (action: string) => {
  const typeMap: Record<string, string> = {
    'login': 'success',
    'logout': 'info',
    'create': 'primary',
    'update': 'warning',
    'delete': 'danger',
    'query': 'info'
  }
  return typeMap[action] || 'info'
}

const getActionLabel = (action: string) => {
  const labelMap: Record<string, string> = {
    'login': '登录',
    'logout': '登出',
    'create': '创建',
    'update': '更新',
    'delete': '删除',
    'query': '查询'
  }
  return labelMap[action] || action
}

const getResourceTypeLabel = (type: string) => {
  const labelMap: Record<string, string> = {
    'user': '用户',
    'task': '任务',
    'knowledge': '知识库',
    'tenant': '租户',
    'system': '系统'
  }
  return labelMap[type] || type
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const loadLogs = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    
    if (filters.action) {
      params.action = filters.action
    }
    if (filters.resource_type) {
      params.resource_type = filters.resource_type
    }
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    
    const data = await adminApi.listAuditLogs(params)
    logs.value = data
    total.value = data.length
  } catch (error) {
    console.error('Failed to load audit logs:', error)
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.action = ''
  filters.resource_type = ''
  dateRange.value = null
  pagination.page = 1
  loadLogs()
}

const exportLogs = () => {
  // Simple CSV export
  const headers = ['操作', '资源类型', '资源ID', '方法', '路径', 'IP地址', '状态码', '时间']
  const rows = logs.value.map(log => [
    getActionLabel(log.action),
    getResourceTypeLabel(log.resource_type),
    log.resource_id,
    log.method,
    log.path,
    log.ip_address,
    log.response_status,
    log.created_at
  ])
  
  const csvContent = [headers, ...rows]
    .map(row => row.map(cell => `"${cell || ''}"`).join(','))
    .join('\n')
  
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(url)
  
  ElMessage.success('导出成功')
}

onMounted(() => {
  loadLogs()
})
</script>

<style scoped>
.audit-page {
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

.filter-card {
  margin-bottom: 20px;
}

.table-card {
  margin-bottom: 20px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>