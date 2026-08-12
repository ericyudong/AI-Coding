<template>
  <div class="page">
    <h2>履约总览</h2>
    <div v-loading="loading" class="stats">
      <div class="stat"><div class="n">{{ overview?.total_plans ?? 0 }}</div><div class="l">履约计划</div></div>
      <div class="stat"><div class="n">{{ overview?.active_plans ?? 0 }}</div><div class="l">已生效</div></div>
      <div class="stat warn"><div class="n">{{ overview?.pending_confirm ?? 0 }}</div><div class="l">待确认</div></div>
      <div class="stat alert"><div class="n">{{ overview?.upcoming_alerts ?? 0 }}</div><div class="l">即将到期</div></div>
      <div class="stat danger"><div class="n">{{ overview?.overdue_nodes ?? 0 }}</div><div class="l">已违约</div></div>
    </div>

    <h3>站内预警</h3>
    <el-table :data="alerts" stripe size="small" style="margin-bottom: 24px">
      <el-table-column prop="alert_type" label="类型" width="100" />
      <el-table-column prop="message" label="内容" min-width="260" />
      <el-table-column prop="email_status" label="邮件" width="100" />
      <el-table-column prop="created_at" label="时间" width="170">
        <template #default="{ row }">{{ row.created_at?.slice(0, 19) || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button v-if="!row.is_read" link type="primary" @click="readAlert(row.id)">已读</el-button>
          <span v-else class="muted">已读</span>
        </template>
      </el-table-column>
    </el-table>

    <h3>我的待办</h3>
    <el-table :data="overview?.my_todos || []" stripe>
      <el-table-column prop="contract_name" label="合同" min-width="180" />
      <el-table-column prop="title" label="节点" min-width="120" />
      <el-table-column prop="due_date" label="到期日" width="120" />
      <el-table-column label="剩余" width="100">
        <template #default="{ row }">
          <span :class="{ danger: row.days_left != null && row.days_left < 0 }">
            {{ row.days_left == null ? '—' : row.days_left < 0 ? `逾期${-row.days_left}天` : `${row.days_left}天` }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <RouterLink :to="`/cms/contracts/${row.contract_id}`">查看合同</RouterLink>
        </template>
      </el-table-column>
    </el-table>

    <div class="links">
      <RouterLink to="/performance/assistant">履约助手</RouterLink>
      <RouterLink to="/performance/suppliers">供应商中心</RouterLink>
      <RouterLink to="/performance/customers">客户中心</RouterLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchPerformanceAlerts,
  fetchPerformanceOverview,
  markPerformanceAlertRead,
  type PerformanceAlert,
  type PerformanceOverview,
} from '@/api/prd'
import { trackAnalytics } from '@/api/cms'

const loading = ref(false)
const overview = ref<PerformanceOverview | null>(null)
const alerts = ref<PerformanceAlert[]>([])

async function load() {
  loading.value = true
  try {
    overview.value = await fetchPerformanceOverview()
    alerts.value = await fetchPerformanceAlerts().catch(() => [])
    trackAnalytics('performance_overview_view').catch(() => undefined)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function readAlert(id: number) {
  await markPerformanceAlertRead(id)
  alerts.value = await fetchPerformanceAlerts()
}

onMounted(load)
</script>

<style scoped>
.page { padding: 24px; }
.stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin: 16px 0 24px; }
.stat { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
.stat .n { font-size: 28px; font-weight: 700; color: #0f766e; }
.stat.warn .n { color: #d97706; }
.stat.alert .n { color: #ea580c; }
.stat.danger .n { color: #dc2626; }
.stat .l { font-size: 12px; color: #64748b; margin-top: 4px; }
.danger { color: #dc2626; }
.muted { color: #94a3b8; font-size: 12px; }
.links { margin-top: 20px; display: flex; gap: 16px; }
.links a { color: #0f766e; }
@media (max-width: 900px) { .stats { grid-template-columns: 1fr 1fr; } }
</style>
