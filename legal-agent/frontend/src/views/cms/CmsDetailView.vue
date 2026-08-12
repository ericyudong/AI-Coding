<template>
  <div v-loading="loading" class="cms-page">
    <RouterLink to="/cms/ledger" class="back">← 返回台账</RouterLink>

    <div v-if="contract" class="detail-panel">
      <div class="main-col">
        <div class="cms-card">
          <div class="card-head">
            <div>
              <h2>📄 {{ contract.name }}</h2>
              <p class="code">合同编号: {{ contract.code }}</p>
            </div>
            <el-select
              :model-value="contract.status"
              class="status-select"
              :loading="updatingStatus"
              @change="onStatusChange"
            >
              <el-option
                v-for="(label, key) in STATUS_MAP"
                :key="key"
                :label="label"
                :value="key"
              />
            </el-select>
          </div>
          <div class="cms-card-body">
            <el-tabs v-model="activeTab">
              <el-tab-pane label="基本信息" name="basic">
                <div class="info-grid">
                  <div class="info-item">
                    <div class="label">合同状态</div>
                    <div class="value">
                      <span class="cms-status" :class="statusClass(contract.status)">
                        <span class="dot" />{{ STATUS_MAP[contract.status] || contract.status }}
                      </span>
                    </div>
                  </div>
                  <div class="info-item"><div class="label">合同类型</div><div class="value"><span class="cms-tag cms-tag-blue">{{ TYPE_MAP[contract.contract_type] }}</span></div></div>
                  <div class="info-item"><div class="label">合同金额</div><div class="value amount">{{ formatAmount(contract.amount) }}</div></div>
                  <div class="info-item"><div class="label">甲方</div><div class="value">{{ contract.party_a }}</div></div>
                  <div class="info-item"><div class="label">乙方</div><div class="value">{{ contract.party_b }}</div></div>
                  <div class="info-item"><div class="label">签署日期</div><div class="value">{{ contract.sign_date || '-' }}</div></div>
                  <div class="info-item"><div class="label">到期日期</div><div class="value">{{ contract.expire_date || '-' }}</div></div>
                  <div class="info-item"><div class="label">负责人</div><div class="value">{{ contract.owner || '-' }}</div></div>
                  <div class="info-item"><div class="label">风险等级</div><div class="value">{{ contract.risk_level }}</div></div>
                </div>
                <div class="tags-section">
                  <div class="tags-title">
                    🏷️ 智能标签
                    <span class="cms-ai-badge">{{ contract.tag_level1 || 'AI' }}{{ contract.tag_level2 ? ' / ' + contract.tag_level2 : '' }}</span>
                    <el-button link type="primary" @click="editTags">编辑</el-button>
                  </div>
                  <span v-for="t in contract.tags" :key="t" class="cms-tag" :class="tagClass(t)">{{ t }}</span>
                </div>
              </el-tab-pane>
              <el-tab-pane label="📝 AI摘要" name="summary">
                <div class="summary-card">
                  <div class="summary-types">
                    <button v-for="t in summaryTypes" :key="t.key" type="button" :class="{ active: summaryType === t.key }" @click="loadSummary(t.key)">{{ t.label }}</button>
                    <el-button size="small" @click="editSummary">手动修改</el-button>
                    <el-tag v-if="contract.summary_locked" size="small" type="warning">已人工锁定</el-tag>
                  </div>
                  <div v-for="(item, i) in summaryItems" :key="i" class="key-point">• {{ item }}</div>
                </div>
              </el-tab-pane>
              <el-tab-pane label="📋 操作日志" name="audits">
                <div v-for="a in audits" :key="a.id" class="audit-item">
                  <div><strong>{{ a.action }}</strong> · 用户#{{ a.user_id }} · {{ a.created_at?.slice(0, 19) }}</div>
                  <pre class="audit-diff">{{ JSON.stringify({ before: a.before, after: a.after }, null, 2) }}</pre>
                </div>
                <el-empty v-if="!audits.length" description="暂无变更记录" />
              </el-tab-pane>
              <el-tab-pane label="🔄 版本历史" name="versions">
                <div v-for="v in versions" :key="v.id" class="version-item" :class="{ active: v.is_current }">
                  <div class="v-number">{{ v.version }}</div>
                  <div class="v-info">
                    <div>{{ v.label }}</div>
                    <div class="v-date">{{ v.created_at?.slice(0, 10) }} · {{ v.created_by }}</div>
                  </div>
                  <el-tag v-if="v.is_current" size="small">当前版本</el-tag>
                  <el-button v-else link type="primary" @click="goCompare(v.id)">对比</el-button>
                </div>
              </el-tab-pane>
              <el-tab-pane label="📄 原文预览" name="original">
                <pre class="original">{{ contract.content_text }}</pre>
              </el-tab-pane>
            </el-tabs>
          </div>
        </div>
      </div>

      <div class="qa-panel">
        <div class="qa-header">
          <h3>💬 AI 问答助手 <span class="cms-ai-badge">RAG</span></h3>
          <el-button link @click="messages = []">清空</el-button>
        </div>
        <div ref="msgBox" class="qa-messages">
          <div v-if="!messages.length" class="welcome">
            <p>您好！可以问我关于这份合同的问题：</p>
            <button v-for="q in suggestions" :key="q" type="button" class="suggestion" @click="ask(q)">{{ q }}</button>
          </div>
          <div v-for="(m, i) in messages" :key="i" class="qa-msg" :class="m.role">
            <div class="bubble">
              <div v-html="m.content" />
              <div v-if="m.confidence" class="confidence">🟢 置信度: {{ m.confidence }}</div>
            </div>
          </div>
        </div>
        <div class="qa-input">
          <el-input v-model="question" placeholder="输入关于合同的问题..." @keyup.enter="ask(question)" />
          <el-button type="primary" :loading="asking" @click="ask(question)">发送</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  askContract,
  fetchContract,
  fetchContractSummary,
  fetchVersions,
  formatAmount,
  STATUS_MAP,
  TYPE_MAP,
  fetchContractAudits,
  updateContract,
  updateContractSummary,
  updateContractTags,
  trackAnalytics,
  fetchTagTaxonomy,
  type ContractItem,
  type ContractVersion,
  type TagTaxonomyNode,
} from '@/api/cms'
import { statusClass, tagClass } from '@/utils/cmsHelpers'

const route = useRoute()
const router = useRouter()
const contractId = Number(route.params.id)
const loading = ref(true)
const contract = ref<ContractItem | null>(null)
const versions = ref<ContractVersion[]>([])
const audits = ref<Array<{ id: number; action: string; before: Record<string, unknown>; after: Record<string, unknown>; note: string; user_id: number; created_at: string }>>([])
const taxonomy = ref<TagTaxonomyNode[]>([])
const activeTab = ref('basic')
const summaryType = ref('short')
const summaryItems = ref<string[]>([])
const summaryTypes = [
  { key: 'short', label: '简短摘要' },
  { key: 'detail', label: '详细摘要' },
  { key: 'risk', label: '⚠️ 风险摘要' },
  { key: 'timeline', label: '📅 时间线' },
]
const messages = ref<{ role: string; content: string; confidence?: string }[]>([])
const question = ref('')
const asking = ref(false)
const updatingStatus = ref(false)
const msgBox = ref<HTMLElement | null>(null)
const suggestions = ['违约金是多少？', '合同何时到期？', '付款条件是什么？']

onMounted(async () => {
  contract.value = await fetchContract(contractId)
  versions.value = await fetchVersions(contractId)
  audits.value = await fetchContractAudits(contractId).catch(() => [])
  taxonomy.value = await fetchTagTaxonomy().catch(() => [])
  await loadSummary('short')
  loading.value = false
})

async function loadSummary(type: string) {
  summaryType.value = type
  const data = await fetchContractSummary(contractId, type)
  summaryItems.value = data.items
}

async function editTags() {
  if (!contract.value) return
  try {
    const l1Options = taxonomy.value.map((t) => t.name)
    let l1 = contract.value.tag_level1 || ''
    if (l1Options.length) {
      const { value } = await ElMessageBox.prompt(
        `一级分类（可选：${l1Options.join(' / ')}）`,
        '标签层级',
        { inputValue: l1 },
      )
      l1 = value
    }
    const l1Node = taxonomy.value.find((t) => t.name === l1)
    const l2Options = (l1Node?.children || []).map((c) => c.name)
    let l2 = contract.value.tag_level2 || ''
    if (l2Options.length) {
      const { value } = await ElMessageBox.prompt(
        `二级分类（可选：${l2Options.join(' / ')}）`,
        '标签层级',
        { inputValue: l2 },
      )
      l2 = value
    }
    const l2Node = (l1Node?.children || []).find((c) => c.name === l2)
    const l3Suggest = (l2Node?.children || []).map((c) => c.name)
    const { value: tagsRaw } = await ElMessageBox.prompt(
      `三级标签，逗号分隔${l3Suggest.length ? `（建议：${l3Suggest.join(',')}）` : ''}`,
      '编辑智能标签',
      { inputValue: contract.value.tags.join(',') },
    )
    const tags = tagsRaw.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
    contract.value = await updateContractTags(contractId, {
      tags,
      tag_level1: l1 || undefined,
      tag_level2: l2 || undefined,
    })
    audits.value = await fetchContractAudits(contractId)
    trackAnalytics('tag_edit', { contract_id: contractId }).catch(() => undefined)
    ElMessage.success('标签已更新')
  } catch {
    /* cancel */
  }
}

async function editSummary() {
  if (!contract.value) return
  try {
    const { value } = await ElMessageBox.prompt('修改后将锁定，AI 不再自动覆盖', '编辑合同摘要', {
      inputValue: summaryItems.value.join('\n') || contract.value.ai_summary,
      inputType: 'textarea',
    })
    contract.value = await updateContractSummary(contractId, value)
    summaryItems.value = value.split(/\n/).filter((s: string) => s.trim())
    audits.value = await fetchContractAudits(contractId)
    trackAnalytics('summary_edit', { contract_id: contractId }).catch(() => undefined)
    ElMessage.success('摘要已保存并锁定')
  } catch {
    /* cancel */
  }
}

async function onStatusChange(status: string) {
  if (!contract.value || contract.value.status === status) return
  updatingStatus.value = true
  try {
    contract.value = await updateContract(contractId, { status })
    ElMessage.success(`状态已更新为「${STATUS_MAP[status] || status}」`)
  } catch {
    ElMessage.error('状态更新失败')
  } finally {
    updatingStatus.value = false
  }
}

async function ask(q: string) {
  if (!q.trim() || asking.value) return
  question.value = ''
  messages.value.push({ role: 'user', content: q })
  asking.value = true
  try {
    const res = await askContract(contractId, q)
    const cites = res.citations.map((c) => `<span class="cite">${c}</span>`).join(' ')
    messages.value.push({
      role: 'assistant',
      content: `${res.answer}<br>${cites}`,
      confidence: res.confidence === 'high' ? '高' : res.confidence,
    })
    await nextTick()
    msgBox.value?.scrollTo({ top: msgBox.value.scrollHeight, behavior: 'smooth' })
  } finally {
    asking.value = false
  }
}

function goCompare(versionId: number) {
  const current = versions.value.find((v) => v.is_current)
  const historical = versions.value.find((v) => v.id === versionId)
  if (!historical || !current) return
  const left = historical.id
  const right = current.id === historical.id
    ? versions.value.filter((v) => v.id !== historical.id).sort((a, b) => b.id - a.id)[0]?.id
    : current.id
  if (!right || left === right) {
    ElMessage.warning('需要至少两个版本才能对比')
    return
  }
  router.push({
    path: '/cms/compare',
    query: { contractId: String(contractId), left: String(left), right: String(right) },
  })
}
</script>

<style scoped>
.back { color: var(--cms-primary); font-size: 14px; text-decoration: none; display: inline-block; margin-bottom: 16px; }
.detail-panel { display: grid; grid-template-columns: 1fr 380px; gap: 20px; }
.card-head { display: flex; justify-content: space-between; align-items: flex-start; padding: 16px 24px; border-bottom: 1px solid var(--cms-border); }
.card-head h2 { margin: 0 0 4px; font-size: 18px; }
.status-select { width: 130px; }
.code { margin: 0; font-size: 13px; color: var(--cms-muted); }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.info-item .label { font-size: 12px; color: var(--cms-muted); }
.info-item .value { font-size: 14px; font-weight: 500; }
.amount { color: var(--cms-primary); font-weight: 700; }
.tags-section { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--cms-border); }
.tags-title { font-size: 13px; font-weight: 500; margin-bottom: 8px; }
.tags-section .cms-tag { margin-right: 6px; margin-bottom: 6px; }
.summary-card { background: linear-gradient(135deg, #eef2ff, #f0fdf4); border-radius: 12px; padding: 16px; }
.summary-types { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.summary-types button { padding: 4px 14px; border: 1px solid var(--cms-border); border-radius: 16px; background: white; font-size: 13px; cursor: pointer; }
.summary-types button.active { background: var(--cms-primary); color: white; border-color: var(--cms-primary); }
.audit-item { background: #f8fafc; border-radius: 8px; padding: 10px; margin-bottom: 8px; font-size: 12px; }
.audit-diff { margin: 6px 0 0; white-space: pre-wrap; color: #64748b; font-size: 11px; }
.key-point { padding: 4px 0; font-size: 14px; line-height: 1.6; }
.version-item { display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid var(--cms-border); border-radius: 8px; margin-bottom: 8px; }
.version-item.active { border-color: var(--cms-primary); background: rgba(79,70,229,0.04); }
.v-number { font-weight: 600; min-width: 40px; }
.v-date { font-size: 12px; color: var(--cms-muted); }
.original { white-space: pre-wrap; font-size: 14px; line-height: 1.8; background: #f8fafc; padding: 16px; border-radius: 8px; max-height: 400px; overflow: auto; }
.qa-panel { background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); display: flex; flex-direction: column; min-height: 560px; }
.qa-header { padding: 16px 20px; border-bottom: 1px solid var(--cms-border); display: flex; justify-content: space-between; align-items: center; }
.qa-header h3 { margin: 0; font-size: 15px; }
.qa-messages { flex: 1; overflow-y: auto; padding: 16px; }
.welcome p { font-size: 14px; color: var(--cms-muted); }
.suggestion { display: block; width: 100%; text-align: left; margin-top: 8px; padding: 8px 12px; border: 1px solid var(--cms-border); border-radius: 8px; background: white; cursor: pointer; font-size: 13px; }
.suggestion:hover { border-color: var(--cms-primary); color: var(--cms-primary); }
.qa-msg { margin-bottom: 12px; }
.qa-msg.user .bubble { background: var(--cms-primary); color: white; margin-left: auto; max-width: 85%; }
.qa-msg.assistant .bubble { background: #f1f5f9; max-width: 90%; }
.bubble { padding: 12px 16px; border-radius: 12px; font-size: 14px; line-height: 1.6; }
.confidence { font-size: 11px; margin-top: 6px; color: #059669; }
.qa-input { padding: 12px 16px; border-top: 1px solid var(--cms-border); display: flex; gap: 8px; }
:deep(.cite) { display: inline-block; background: rgba(79,70,229,0.1); color: var(--cms-primary); padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-top: 4px; }
@media (max-width: 1100px) { .detail-panel { grid-template-columns: 1fr; } }
</style>
