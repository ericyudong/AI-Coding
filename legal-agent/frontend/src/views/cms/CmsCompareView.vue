<template>
  <div v-loading="loading" class="cms-page">
    <div class="page-header">
      <div>
        <h1>🔄 合同版本对比</h1>
        <p class="subtitle">对比同一份合同下两个历史版本的文本差异</p>
      </div>
      <span class="cms-ai-badge">AI 语义对比</span>
    </div>

    <div v-if="!contractId && !loading" class="cms-card">
      <div class="cms-card-body pick-contract">
        <p class="pick-hint">请选择要对比的合同（可输入合同名称或编号搜索）</p>
        <el-select
          v-model="pickedContractId"
          filterable
          remote
          clearable
          reserve-keyword
          placeholder="搜索合同名称或编号"
          :remote-method="searchContracts"
          :loading="loadingContracts"
          style="width: 420px"
          @change="onContractPick"
        >
          <el-option
            v-for="c in contractOptions"
            :key="c.id"
            :label="contractLabel(c)"
            :value="c.id"
          />
        </el-select>
      </div>
    </div>

    <template v-else-if="contractId">
      <div class="cms-card">
        <div class="cms-card-body">
          <div class="version-selector">
            <span>选择合同:</span>
            <el-select
              v-model="contractId"
              filterable
              remote
              reserve-keyword
              placeholder="搜索合同名称或编号"
              :remote-method="searchContracts"
              :loading="loadingContracts"
              style="width: 320px"
              @change="onContractChange"
            >
              <el-option
                v-for="c in contractOptions"
                :key="c.id"
                :label="contractLabel(c)"
                :value="c.id"
              />
            </el-select>
            <span>对比版本:</span>
            <el-select v-model="leftId" placeholder="旧版本（左）" style="width: 220px">
              <el-option
                v-for="v in versions"
                :key="v.id"
                :label="`${v.version} ${v.label}${v.is_current ? '（当前）' : ''}`"
                :value="v.id"
              />
            </el-select>
            <span>← VS →</span>
            <el-select v-model="rightId" placeholder="新版本（右）" style="width: 220px">
              <el-option
                v-for="v in versions"
                :key="v.id"
                :label="`${v.version} ${v.label}${v.is_current ? '（当前）' : ''}`"
                :value="v.id"
              />
            </el-select>
            <el-button
              type="primary"
              :disabled="!canCompare"
              :loading="comparing"
              @click="runCompare"
            >
              开始对比
            </el-button>
          </div>

          <el-alert
            v-if="versions.length < 2"
            type="warning"
            :closable="false"
            show-icon
            title="该合同仅有 1 个版本，无法对比。可通过「合同导入」关联已有合同以追加新版本。"
            class="version-alert"
          />

          <div v-if="compareResult" class="diff-summary">
            <div class="summary-title">🤖 AI 变更摘要</div>
            <div class="summary-grid">
              <div>✅ 共检测到 <strong>{{ compareResult.summary.total }}</strong> 处变更</div>
              <div>🔴 风险变更: <strong>{{ compareResult.summary.risk }}</strong> 处</div>
              <div>📝 新增条款: <strong>{{ compareResult.summary.added }}</strong> 处</div>
              <div>🗑️ 删除条款: <strong>{{ compareResult.summary.removed }}</strong> 处</div>
            </div>
            <div class="risk-note">⚠️ <strong>风险提示:</strong> {{ compareResult.risk_note }}</div>
          </div>
        </div>
      </div>

      <div v-if="compareResult?.changes.length" class="cms-card">
        <div class="card-head">
          <h3>📑 版本对比详情</h3>
          <div class="legend">
            <span><i class="dot added" /> 新增</span>
            <span><i class="dot removed" /> 删除</span>
            <span><i class="dot changed" /> 修改</span>
          </div>
        </div>
        <div class="diff-list">
          <div v-for="(c, i) in compareResult.changes" :key="i" class="change-block">
            <div class="section">{{ c.section }}</div>
            <div v-if="c.detail" class="change-detail">{{ c.detail }}</div>
            <div class="diff-row">
              <div class="diff-pane" :class="paneClass(c.change_type, 'left')">{{ c.left_text }}</div>
              <div class="diff-pane" :class="paneClass(c.change_type, 'right')">{{ c.right_text }}</div>
            </div>
            <div v-if="c.ai_note" class="ai-note"><span class="cms-ai-badge">AI 标注</span> {{ c.ai_note }}</div>
          </div>
        </div>
      </div>

      <div v-else-if="compareResult && !comparing" class="cms-card">
        <div class="cms-card-body empty-diff">两版本内容一致，未检测到差异。</div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  compareVersions,
  fetchContract,
  fetchContracts,
  fetchVersions,
  type ContractItem,
  type ContractVersion,
} from '@/api/cms'

const route = useRoute()
const router = useRouter()

const contractId = ref(0)
const pickedContractId = ref<number | null>(null)
const leftId = ref<number | undefined>()
const rightId = ref<number | undefined>()
const versions = ref<ContractVersion[]>([])
const contractOptions = ref<ContractItem[]>([])
const loading = ref(false)
const loadingContracts = ref(false)
const comparing = ref(false)
const compareResult = ref<Awaited<ReturnType<typeof compareVersions>> | null>(null)

const canCompare = computed(
  () =>
    versions.value.length >= 2 &&
    !!leftId.value &&
    !!rightId.value &&
    leftId.value !== rightId.value,
)

function parseQueryId(value: unknown): number | undefined {
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? n : undefined
}

function pickDefaultVersions(list: ContractVersion[], preferredLeft?: number, preferredRight?: number) {
  const ids = new Set(list.map((v) => v.id))
  if (preferredLeft && preferredRight && ids.has(preferredLeft) && ids.has(preferredRight)) {
    return { left: preferredLeft, right: preferredRight }
  }
  const sorted = [...list].sort((a, b) => a.id - b.id)
  const current = sorted.find((v) => v.is_current) || sorted[sorted.length - 1]
  if (sorted.length < 2) return {}
  const currentIdx = sorted.findIndex((v) => v.id === current.id)
  const left = currentIdx > 0 ? sorted[currentIdx - 1].id : sorted[0].id
  return { left, right: current.id }
}

function paneClass(changeType: string, side: 'left' | 'right') {
  if (changeType === 'removed') return side === 'left' ? 'removed' : ''
  if (changeType === 'added') return side === 'right' ? 'added' : ''
  if (changeType === 'modified') return 'modified'
  return ''
}

function contractLabel(c: ContractItem) {
  return `${c.code} · ${c.name}`
}

async function searchContracts(keyword = '') {
  loadingContracts.value = true
  try {
    const res = await fetchContracts({ q: keyword.trim(), page: 1, page_size: 50 })
    let items = res.items
    const keepId = contractId.value || pickedContractId.value
    if (keepId && !items.some((c) => c.id === keepId)) {
      try {
        const current = await fetchContract(keepId)
        items = [current, ...items]
      } catch {
        // ignore
      }
    }
    contractOptions.value = items
  } catch {
    contractOptions.value = []
  } finally {
    loadingContracts.value = false
  }
}

async function loadContractData(preferredLeft?: number, preferredRight?: number, autoCompare = true) {
  if (!contractId.value) {
    versions.value = []
    compareResult.value = null
    return
  }
  loading.value = true
  compareResult.value = null
  try {
    versions.value = await fetchVersions(contractId.value)
    const picked = pickDefaultVersions(versions.value, preferredLeft, preferredRight)
    leftId.value = picked.left
    rightId.value = picked.right
    if (autoCompare && canCompare.value) {
      await runCompare()
    }
  } finally {
    loading.value = false
  }
}

async function onContractPick(id: number) {
  contractId.value = id
  await router.replace({ path: '/cms/compare', query: { contractId: String(id) } })
  await loadContractData()
}

async function onContractChange(id: number) {
  await router.replace({ path: '/cms/compare', query: { contractId: String(id) } })
  await loadContractData(undefined, undefined, false)
}

async function runCompare() {
  if (!canCompare.value || !contractId.value || !leftId.value || !rightId.value) {
    if (leftId.value === rightId.value) {
      ElMessage.warning('请选择两个不同的版本')
    }
    return
  }
  comparing.value = true
  try {
    compareResult.value = await compareVersions(contractId.value, leftId.value, rightId.value)
    const total = compareResult.value.summary.total
    ElMessage.success(total > 0 ? `对比完成，共 ${total} 处变更` : '对比完成，两版本内容一致')
  } catch {
    compareResult.value = null
    ElMessage.error('版本对比失败，请确认版本属于当前合同')
  } finally {
    comparing.value = false
  }
}

async function initFromRoute() {
  await searchContracts('')
  const queryContractId = parseQueryId(route.query.contractId)
  const queryLeft = parseQueryId(route.query.left)
  const queryRight = parseQueryId(route.query.right)

  if (queryContractId) {
    contractId.value = queryContractId
    pickedContractId.value = queryContractId
    await loadContractData(queryLeft, queryRight, !!(queryLeft && queryRight))
    return
  }

  contractId.value = 0
  pickedContractId.value = null
}

onMounted(initFromRoute)

watch(
  () => [route.query.contractId, route.query.left, route.query.right],
  () => {
    initFromRoute()
  },
)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.page-header h1 { margin: 0; font-size: 26px; color: #1e1b4b; }
.subtitle { margin: 4px 0 0; color: var(--cms-muted); font-size: 14px; }
.version-selector { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.version-alert { margin-bottom: 16px; }
.diff-summary { padding: 16px; background: #f8fafc; border-radius: 8px; border: 1px solid var(--cms-border); }
.summary-title { font-weight: 600; margin-bottom: 8px; }
.summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 14px; }
.risk-note { margin-top: 8px; padding: 8px; background: rgba(239,68,68,0.05); border-radius: 6px; font-size: 13px; }
.card-head { display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; border-bottom: 1px solid var(--cms-border); }
.card-head h3 { margin: 0; }
.legend { display: flex; gap: 16px; font-size: 13px; }
.legend .dot { display: inline-block; width: 12px; height: 12px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
.legend .added { background: rgba(16,185,129,0.3); }
.legend .removed { background: rgba(239,68,68,0.2); }
.legend .changed { background: rgba(245,158,11,0.2); }
.diff-list { padding: 16px 24px; }
.change-block { margin-bottom: 16px; }
.section { font-weight: 600; margin-bottom: 8px; }
.change-detail {
  margin: -4px 0 10px;
  padding: 10px 12px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: #92400e;
}
.diff-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0; border: 1px solid var(--cms-border); border-radius: 8px; overflow: hidden; }
.diff-pane { padding: 12px 16px; font-size: 14px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.diff-pane:first-child { border-right: 1px solid var(--cms-border); }
.diff-pane.removed { background: rgba(239,68,68,0.08); }
.diff-pane.added { background: rgba(16,185,129,0.1); }
.diff-pane.modified { background: rgba(245,158,11,0.08); }
.ai-note { margin-top: 6px; font-size: 13px; color: var(--cms-muted); }
.empty-diff { text-align: center; color: var(--cms-muted); padding: 24px; }
.pick-contract { display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 32px 24px; }
.pick-hint { margin: 0; color: var(--cms-muted); font-size: 14px; }
@media (max-width: 768px) { .diff-row { grid-template-columns: 1fr; } }
</style>
