<template>
  <div class="page">
    <h2>履约助手AI</h2>
    <p class="desc">选择合同后，AI 提取履约时间线；人工确认节点与责任人后生效。逾期无宽限期，超期自动标记违约。</p>

    <div class="toolbar">
      <el-input v-model="contractId" placeholder="合同 ID" style="width: 160px" />
      <el-button type="primary" :loading="loading" @click="loadPlan">提取/查看时间线</el-button>
      <el-button v-if="plan && plan.status !== 'active'" type="success" @click="confirm">确认履约计划</el-button>
    </div>

    <div v-if="plan" class="plan">
      <div class="plan-head">
        <h3>{{ plan.contract_name || `合同#${plan.contract_id}` }}</h3>
        <el-tag>{{ plan.status === 'active' ? '已生效' : '待确认' }}</el-tag>
      </div>

      <div class="timeline">
        <div v-for="node in plan.nodes" :key="node.id" class="node" :class="node.status">
          <div class="dot" />
          <div class="card">
            <div class="row">
              <strong>{{ node.title }}</strong>
              <el-tag size="small">{{ node.node_type }}</el-tag>
              <el-tag size="small" type="info">{{ node.confirm_status }}</el-tag>
              <el-tag size="small" :type="statusType(node.status)">{{ node.status }}</el-tag>
            </div>
            <div class="meta">
              到期：{{ node.due_date || '—' }}
              <span v-if="node.duration_days != null"> · 期间 {{ node.duration_days }} 天</span>
            </div>
            <div class="actions">
              <el-button size="small" @click="markDone(node.id)">标记完成</el-button>
              <el-button size="small" @click="assignSelf(node.id)">分配给我</el-button>
              <el-button size="small" type="warning" @click="adjustNode(node)">申请调整</el-button>
            </div>
          </div>
        </div>
        <p v-if="!plan.nodes.length" class="empty">未提取到节点，请确认合同正文含日期信息</p>
      </div>
    </div>

    <div v-if="canReview" class="pending">
      <h3>待审批调整</h3>
      <el-table :data="pendingAdj" size="small">
        <el-table-column prop="contract_name" label="合同" min-width="140" />
        <el-table-column prop="node_title" label="节点" width="120" />
        <el-table-column prop="reason" label="原因" min-width="120" />
        <el-table-column label="证据" min-width="160">
          <template #default="{ row }">
            <div>{{ row.evidence_note || '—' }}</div>
            <a
              v-if="row.evidence_path"
              href="#"
              @click.prevent="downloadEvidence(row.id, row.evidence_filename)"
            >{{ row.evidence_filename || '下载附件' }}</a>
          </template>
        </el-table-column>
        <el-table-column prop="new_due_date" label="新到期日" width="110" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="success" @click="reviewAdj(row.id, true)">通过</el-button>
            <el-button link type="danger" @click="reviewAdj(row.id, false)">驳回</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="alerts">
      <div class="alerts-head">
        <h3>站内+邮件预警</h3>
        <div>
          <el-button size="small" @click="dispatchMails">派发邮件</el-button>
          <el-button size="small" @click="loadAlerts">刷新预警</el-button>
        </div>
      </div>
      <el-table :data="alerts" size="small">
        <el-table-column prop="alert_type" label="类型" width="100" />
        <el-table-column prop="message" label="内容" min-width="200" />
        <el-table-column prop="email_status" label="邮件" width="100" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button v-if="!row.is_read" link type="primary" @click="readAlert(row.id)">已读</el-button>
            <span v-else class="muted">已读</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  confirmPerformancePlan,
  dispatchPerformanceAlerts,
  extractPerformancePlan,
  fetchPerformanceAlerts,
  fetchPerformancePlan,
  fetchPendingAdjustments,
  markPerformanceAlertRead,
  reviewPerformanceAdjustment,
  submitPerformanceAdjustment,
  updatePerformanceNode,
  uploadPerformanceEvidence,
  type PerformanceAlert,
  type PerformancePlan,
  type PendingAdjustment,
} from '@/api/prd'
import { trackAnalytics } from '@/api/cms'
import { useAuthStore } from '@/stores/auth'
import http from '@/api/http'

const REVIEW_ROLES = new Set(['system_admin', 'legal', 'finance', 'manager'])

const auth = useAuthStore()
const contractId = ref('')
const loading = ref(false)
const plan = ref<PerformancePlan | null>(null)
const alerts = ref<PerformanceAlert[]>([])
const pendingAdj = ref<PendingAdjustment[]>([])

const canReview = computed(() => REVIEW_ROLES.has(auth.user?.role || ''))

function statusType(s: string) {
  if (s === 'done') return 'success'
  if (s === 'defaulted') return 'danger'
  if (s === 'delayed') return 'warning'
  return 'info'
}

async function loadPlan() {
  const id = Number(contractId.value)
  if (!id) {
    ElMessage.warning('请输入合同 ID')
    return
  }
  loading.value = true
  try {
    plan.value = await extractPerformancePlan(id)
    trackAnalytics('performance_extract', { contract_id: id }).catch(() => undefined)
  } catch {
    try {
      plan.value = await fetchPerformancePlan(id)
    } catch (e: unknown) {
      ElMessage.error(e instanceof Error ? e.message : '加载失败')
    }
  } finally {
    loading.value = false
  }
}

async function confirm() {
  if (!plan.value) return
  plan.value = await confirmPerformancePlan(plan.value.id)
  ElMessage.success('履约计划已生效')
  trackAnalytics('performance_confirm', { plan_id: plan.value.id }).catch(() => undefined)
}

async function markDone(nodeId: number) {
  await updatePerformanceNode(nodeId, { status: 'done', confirm_status: 'confirmed' })
  ElMessage.success('已标记完成')
  await loadPlan()
}

async function assignSelf(nodeId: number) {
  const uid = auth.user?.id
  if (!uid) return
  await updatePerformanceNode(nodeId, {
    owner_ids: [uid],
    primary_owner_id: uid,
    confirm_status: 'confirmed',
  })
  ElMessage.success('已分配责任人')
  await loadPlan()
}

async function adjustNode(node: { id: number; title: string; due_date: string | null }) {
  try {
    const { value: reason } = await ElMessageBox.prompt('请说明调整原因', `申请调整：${node.title}`)
    const { value: evidence } = await ElMessageBox.prompt('证据说明（可选，若上传文件可简写）', '证据说明', {
      inputValue: '',
    })
    const pick = await ElMessageBox.confirm('是否上传证据文件（PDF/图片等）？取消则仅使用文字说明', '证据附件', {
      distinguishCancelAndClose: true,
      confirmButtonText: '选择文件',
      cancelButtonText: '仅文字',
    }).then(() => true).catch((action: string) => action === 'cancel' ? false : null)
    if (pick === null) return

    let evidence_path = ''
    let evidence_filename = ''
    if (pick) {
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = '.pdf,.png,.jpg,.jpeg,.doc,.docx,.xlsx'
      const file = await new Promise<File | null>((resolve) => {
        input.onchange = () => resolve(input.files?.[0] || null)
        input.click()
      })
      if (file) {
        const meta = await uploadPerformanceEvidence(node.id, file)
        evidence_path = meta.evidence_path
        evidence_filename = meta.evidence_filename
      }
    }
    if (!evidence?.trim() && !evidence_path) {
      ElMessage.warning('请填写证据说明或上传附件')
      return
    }
    const { value: newDate } = await ElMessageBox.prompt('新到期日 YYYY-MM-DD（可留空）', '调整日期', {
      inputValue: node.due_date || '',
    })
    await submitPerformanceAdjustment(node.id, {
      reason,
      evidence_note: evidence || '',
      evidence_path,
      evidence_filename,
      new_due_date: newDate || null,
      new_owner_ids: [],
    })
    ElMessage.success('调整申请已提交，等待审批')
    trackAnalytics('performance_adjust', { node_id: node.id }).catch(() => undefined)
    if (canReview.value) await loadPending()
  } catch {
    /* cancel */
  }
}

async function downloadEvidence(adjustmentId: number, filename?: string) {
  const { data } = await http.get(`/performance/adjustments/${adjustmentId}/evidence`, {
    responseType: 'blob',
  })
  const url = URL.createObjectURL(data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || `evidence-${adjustmentId}`
  a.click()
  URL.revokeObjectURL(url)
}

async function dispatchMails() {
  const res = await dispatchPerformanceAlerts()
  ElMessage.success(`新建预警 ${res.created}；邮件 sent=${res.email?.sent ?? 0} skipped=${res.email?.skipped ?? 0}`)
  await loadAlerts()
}

async function loadAlerts() {
  alerts.value = await fetchPerformanceAlerts()
}

async function readAlert(id: number) {
  await markPerformanceAlertRead(id)
  await loadAlerts()
}

async function loadPending() {
  if (!canReview.value) return
  try {
    pendingAdj.value = await fetchPendingAdjustments()
  } catch {
    pendingAdj.value = []
  }
}

async function reviewAdj(id: number, approve: boolean) {
  await reviewPerformanceAdjustment(id, approve)
  ElMessage.success(approve ? '已通过' : '已驳回')
  await loadPending()
  if (plan.value) await loadPlan()
}

onMounted(async () => {
  await loadAlerts()
  await loadPending()
})
</script>

<style scoped>
.page { padding: 24px; max-width: 960px; }
.desc { color: #64748b; font-size: 14px; }
.toolbar { display: flex; gap: 10px; margin: 16px 0; }
.plan-head { display: flex; align-items: center; gap: 12px; }
.timeline { margin-top: 16px; border-left: 2px solid #e2e8f0; padding-left: 16px; }
.node { position: relative; margin-bottom: 16px; }
.dot { position: absolute; left: -23px; top: 12px; width: 10px; height: 10px; border-radius: 50%; background: #0f766e; }
.node.defaulted .dot { background: #dc2626; }
.node.done .dot { background: #16a34a; }
.card { background: #fff; border-radius: 10px; padding: 12px 14px; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
.row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.meta { font-size: 12px; color: #64748b; margin: 6px 0; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.empty { color: #94a3b8; }
.alerts, .pending { margin-top: 28px; }
.alerts-head { display: flex; justify-content: space-between; align-items: center; }
.muted { color: #94a3b8; font-size: 12px; }
</style>
