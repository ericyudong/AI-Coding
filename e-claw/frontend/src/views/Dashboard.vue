<template>
  <div class="dashboard">
    <!-- Header -->
    <div class="dashboard-header">
      <div class="header-left">
        <h1>欢迎回来, {{ authStore.user?.full_name || authStore.user?.username }}</h1>
        <p class="subtitle">E-Claw 企业级AI智能体运行平台</p>
      </div>
      <div class="header-right">
        <el-tag :type="roleTagType" size="large">{{ roleLabel }}</el-tag>
      </div>
    </div>

    <!-- Stats Cards -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon tasks">
            <el-icon :size="32"><Operation /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.total_tasks }}</div>
            <div class="stat-label">总任务数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon completed">
            <el-icon :size="32"><CircleCheck /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.completed_tasks }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon knowledge">
            <el-icon :size="32"><Document /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.knowledge_bases }}</div>
            <div class="stat-label">知识库</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon tokens">
            <el-icon :size="32"><Coin /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ formatNumber(stats.total_token_usage) }}</div>
            <div class="stat-label">Token使用量</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Quick Actions -->
    <el-row :gutter="20" class="actions-row">
      <el-col :span="24">
        <el-card class="actions-card">
          <template #header>
            <div class="card-header">
              <span>快速操作</span>
            </div>
          </template>
          <div class="quick-actions">
            <div class="action-item" @click="router.push('/tasks')">
              <div class="action-icon">
                <el-icon :size="28"><Plus /></el-icon>
              </div>
              <span>提交任务</span>
            </div>
            <div class="action-item" @click="router.push('/knowledge')">
              <div class="action-icon">
                <el-icon :size="28"><FolderOpened /></el-icon>
              </div>
              <span>知识库</span>
            </div>
            <div class="action-item" @click="router.push('/tenants')" v-if="authStore.isSuperAdmin">
              <div class="action-icon">
                <el-icon :size="28"><OfficeBuilding /></el-icon>
              </div>
              <span>租户管理</span>
            </div>
            <div class="action-item" @click="router.push('/audit')" v-if="authStore.isAdmin">
              <div class="action-icon">
                <el-icon :size="28"><List /></el-icon>
              </div>
              <span>审计日志</span>
            </div>
            <div class="action-item" @click="router.push('/users')" v-if="authStore.isAdmin">
              <div class="action-icon">
                <el-icon :size="28"><User /></el-icon>
              </div>
              <span>用户管理</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Recent Tasks & Quota -->
    <el-row :gutter="20">
      <!-- Recent Tasks -->
      <el-col :span="16">
        <el-card class="recent-card">
          <template #header>
            <div class="card-header">
              <span>最近任务</span>
              <el-button type="primary" link @click="router.push('/tasks')">查看全部</el-button>
            </div>
          </template>
          <el-table :data="recentTasks" style="width: 100%" v-loading="tasksLoading">
            <el-table-column prop="name" label="任务名称" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="80">
              <template #default="{ row }">
                <el-tag :type="getPriorityType(row.priority)">{{ getPriorityLabel(row.priority) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="submit_time" label="提交时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.submit_time) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- Quota Info -->
      <el-col :span="8">
        <el-card class="quota-card">
          <template #header>
            <div class="card-header">
              <span>配额信息</span>
            </div>
          </template>
          <div class="quota-content">
            <div class="quota-item">
              <span class="quota-label">个人配额</span>
              <span class="quota-value">{{ formatNumber(authStore.user?.personal_quota || 0) }}</span>
            </div>
            <div class="quota-item">
              <span class="quota-label">已使用</span>
              <span class="quota-value used">{{ formatNumber(authStore.user?.personal_used || 0) }}</span>
            </div>
            <el-progress 
              :percentage="quotaPercentage" 
              :color="quotaColor"
              :stroke-width="10"
            />
            <div class="quota-item available">
              <span class="quota-label">可用配额</span>
              <span class="quota-value">{{ formatNumber(authStore.availableQuota) }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { adminApi, tasksApi } from '@/api'
import { 
  Operation, 
  CircleCheck, 
  Document, 
  Coin, 
  Plus, 
  FolderOpened, 
  OfficeBuilding,
  List,
  User
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()

const stats = ref({
  total_tasks: 0,
  completed_tasks: 0,
  failed_tasks: 0,
  total_token_usage: 0,
  active_tenants: 0,
  knowledge_bases: 0,
  documents: 0
})

const recentTasks = ref<any[]>([])
const tasksLoading = ref(false)

const roleLabel = computed(() => {
  const roleMap: Record<string, string> = {
    'super_admin': '超级管理员',
    'dept_admin': '部门管理员',
    'employee': '员工',
    'ops': '运维'
  }
  return roleMap[authStore.user?.role || ''] || '员工'
})

const roleTagType = computed(() => {
  const typeMap: Record<string, string> = {
    'super_admin': 'danger',
    'dept_admin': 'warning',
    'employee': 'success',
    'ops': 'info'
  }
  return typeMap[authStore.user?.role || ''] || 'success'
})

const quotaPercentage = computed(() => {
  if (!authStore.user) return 0
  const { personal_quota, personal_used } = authStore.user
  if (personal_quota === 0) return 0
  return Math.round((personal_used / personal_quota) * 100)
})

const quotaColor = computed(() => {
  const percentage = quotaPercentage.value
  if (percentage >= 90) return '#f56c6c'
  if (percentage >= 70) return '#e6a23c'
  return '#67c23a'
})

const formatNumber = (num: number) => {
  if (!num) return '0'
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const getStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    'pending': 'info',
    'running': 'primary',
    'completed': 'success',
    'failed': 'danger',
    'cancelled': 'warning'
  }
  return typeMap[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const labelMap: Record<string, string> = {
    'pending': '等待中',
    'running': '运行中',
    'completed': '已完成',
    'failed': '失败',
    'cancelled': '已取消'
  }
  return labelMap[status] || status
}

const getPriorityType = (priority: string) => {
  const typeMap: Record<string, string> = {
    'low': 'info',
    'medium': 'warning',
    'high': 'danger'
  }
  return typeMap[priority] || 'info'
}

const getPriorityLabel = (priority: string) => {
  const labelMap: Record<string, string> = {
    'low': '低',
    'medium': '中',
    'high': '高'
  }
  return labelMap[priority] || priority
}

const loadStats = async () => {
  try {
    const data = await adminApi.getStats()
    stats.value = data
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

const loadRecentTasks = async () => {
  tasksLoading.value = true
  try {
    const data = await tasksApi.list({ page: 1, page_size: 5 })
    recentTasks.value = data
  } catch (error) {
    console.error('Failed to load tasks:', error)
  } finally {
    tasksLoading.value = false
  }
}

onMounted(() => {
  loadStats()
  loadRecentTasks()
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left h1 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.subtitle {
  margin: 8px 0 0;
  color: #909399;
  font-size: 14px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  cursor: pointer;
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-4px);
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  padding: 20px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
}

.stat-icon.tasks {
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  color: white;
}

.stat-icon.completed {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
  color: white;
}

.stat-icon.knowledge {
  background: linear-gradient(135deg, #e6a23c 0%, #ebb563 100%);
  color: white;
}

.stat-icon.tokens {
  background: linear-gradient(135deg, #909399 0%, #a6a9ad 100%);
  color: white;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.actions-row {
  margin-bottom: 20px;
}

.actions-card :deep(.el-card__body) {
  padding: 20px;
}

.quick-actions {
  display: flex;
  gap: 40px;
}

.action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  transition: transform 0.2s;
}

.action-item:hover {
  transform: scale(1.05);
}

.action-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #409eff;
  margin-bottom: 8px;
}

.action-item span {
  font-size: 14px;
  color: #606266;
}

.recent-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.quota-content {
  padding: 10px 0;
}

.quota-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.quota-label {
  color: #909399;
}

.quota-value {
  font-weight: 500;
  color: #303133;
}

.quota-value.used {
  color: #409eff;
}

.quota-item.available {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.quota-item.available .quota-value {
  color: #67c23a;
  font-size: 18px;
}
</style>