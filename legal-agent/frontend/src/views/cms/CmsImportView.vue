<template>
  <div class="cms-page">
    <div class="page-header">
      <div>
        <h1>合同导入</h1>
        <p class="subtitle">支持 PDF / Word / 图片上传，AI 自动 OCR 识别并提取关键信息</p>
      </div>
    </div>

    <div class="cms-card">
      <div class="cms-card-body">
        <div
          class="upload-zone"
          :class="{ dragging }"
          @dragover.prevent="dragging = true"
          @dragleave="dragging = false"
          @drop.prevent="onDrop"
          @click="triggerUpload"
        >
          <input ref="fileInput" type="file" hidden multiple accept=".pdf,.doc,.docx,.xlsx,.jpg,.jpeg,.png" @change="onFile" />
          <div class="icon">📄</div>
          <h3>拖拽文件到此处，或点击上传</h3>
          <p>支持 PDF、Word、Excel、JPG、PNG；单文件最大 100MB，支持批量（≤50）</p>
          <div class="formats">
            <span v-for="f in ['PDF', 'DOCX', 'XLSX', 'JPG', 'PNG']" :key="f">{{ f }}</span>
          </div>
        </div>

        <div v-if="processing" class="ocr-progress">
          <h4>⏳ 后台异步解析中 <span class="cms-ai-badge">Powered by AI</span></h4>
          <el-progress :percentage="pollProgress" />
          <div v-for="(step, i) in steps" :key="i" class="step">
            <span class="step-icon" :class="step.state">{{ step.icon }}</span>
            <div>
              <div>{{ step.label }}</div>
              <div class="step-status">{{ step.status }}</div>
            </div>
          </div>
        </div>

        <div class="parse-log">
          <div class="parse-log-head">
            <h4>解析日志</h4>
            <el-button link type="primary" @click="loadTaskLog">刷新</el-button>
          </div>
          <el-table :data="taskLog" size="small" stripe>
            <el-table-column prop="filename" label="文件名" min-width="160" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column prop="progress" label="进度" width="80" />
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button v-if="row.status === 'completed'" link type="primary" @click="selectTask(row)">查看详情</el-button>
                <el-button v-if="row.status === 'failed'" link type="warning" @click="onRetry(row.id)">重新解析</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>

    <div v-if="task" class="cms-card">
      <div class="card-head">
        <h3>📋 AI 提取结果 <span class="cms-ai-badge">置信度 {{ task.confidence }}%</span></h3>
        <div>
          <el-button @click="task = null">重新上传</el-button>
          <el-button type="primary" :loading="confirming" @click="onConfirm">✅ 确认入库</el-button>
        </div>
      </div>
      <div class="cms-card-body">
        <div class="info-grid">
          <div v-for="item in extractedFields" :key="item.label" class="info-item">
            <div class="label">{{ item.label }}</div>
            <div class="value">{{ item.value }}</div>
          </div>
        </div>
        <div v-if="clauses.length" class="clauses">
          <div class="clauses-title">🤖 AI 提取的关键条款</div>
          <span v-for="c in clauses" :key="c" class="cms-tag cms-tag-blue">{{ c }}</span>
        </div>
        <div v-if="task?.parse_warnings?.length" class="parse-warnings">
          <div class="clauses-title">⚠️ 解析提示</div>
          <p v-for="(w, i) in task.parse_warnings" :key="i">{{ w }}</p>
        </div>
        <div v-if="task?.char_count" class="char-count">正文已提取 {{ task.char_count }} 字</div>

        <div class="import-target">
          <div class="import-target-title">入库方式</div>
          <el-radio-group v-model="importMode">
            <el-radio value="new">新建合同台账</el-radio>
            <el-radio value="link">关联到已有合同（追加新版本）</el-radio>
          </el-radio-group>
          <div v-if="importMode === 'link'" class="link-fields">
            <div v-if="linkSuggestions.length" class="suggest-block">
              <div class="suggest-title">
                智能推荐
                <span class="cms-ai-badge">名称相似 · 甲乙双方一致</span>
              </div>
              <div
                v-for="item in linkSuggestions"
                :key="item.contract.id"
                class="suggest-item"
                :class="{ active: linkedContractId === item.contract.id }"
                @click="selectSuggestedContract(item.contract.id)"
              >
                <div class="suggest-main">
                  <span class="suggest-name">{{ item.contract.name }}</span>
                  <span class="suggest-score">{{ item.match_score }}%</span>
                </div>
                <div class="suggest-meta">
                  {{ item.contract.code }} · 甲方 {{ item.contract.party_a || '-' }} · 乙方 {{ item.contract.party_b || '-' }}
                </div>
                <div class="suggest-reason">{{ item.match_reason }}</div>
              </div>
            </div>
            <div v-else-if="!loadingSuggestions" class="suggest-empty">
              未找到名称相似且甲乙双方一致的合同，可手动搜索其他台账记录。
            </div>
            <el-select
              v-model="linkedContractId"
              filterable
              remote
              clearable
              reserve-keyword
              placeholder="手动搜索合同名称、编号或签约方"
              :remote-method="onContractSearch"
              :loading="loadingSuggestions"
              style="width: 100%"
            >
              <el-option
                v-for="c in contractOptions"
                :key="c.id"
                :label="`${c.code} · ${c.name}`"
                :value="c.id"
              />
            </el-select>
            <el-input
              v-model="versionLabel"
              placeholder="版本说明，如：对方修订版、终稿"
              maxlength="64"
              show-word-limit
            />
            <p class="link-hint">导入内容将作为所选合同的新版本入库，可在版本对比中查看差异。</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  confirmImport,
  fetchImportLinkSuggestions,
  fetchImportTask,
  fetchImportTasks,
  retryImportTask,
  trackAnalytics,
  uploadContractImport,
  uploadContractImportBatch,
  TYPE_MAP,
  type ContractItem,
  type ImportLinkSuggestion,
  type ImportTask,
} from '@/api/cms'

const router = useRouter()
const fileInput = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const processing = ref(false)
const confirming = ref(false)
const task = ref<ImportTask | null>(null)
const taskLog = ref<ImportTask[]>([])
const pollProgress = ref(0)
const importMode = ref<'new' | 'link'>('new')
const linkedContractId = ref<number | null>(null)
const versionLabel = ref('导入版本')
const contractOptions = ref<ContractItem[]>([])
const linkSuggestions = ref<ImportLinkSuggestion[]>([])
const loadingSuggestions = ref(false)
let pollTimer: number | undefined

const steps = ref([
  { label: '📁 文件上传完成', status: '等待上传...', state: 'pending', icon: '○' },
  { label: '📝 加入解析队列', status: '等待中', state: 'pending', icon: '○' },
  { label: '🔍 OCR / 正文解析', status: '等待中', state: 'pending', icon: '○' },
  { label: '🤖 AI 结构化提取', status: '等待中', state: 'pending', icon: '○' },
])

const extractedFields = computed(() => {
  const e = task.value?.extracted || {}
  return [
    { label: '合同名称', value: e.name || '-' },
    { label: '合同编号', value: e.code || '-' },
    { label: '合同类型', value: TYPE_MAP[String(e.contract_type)] || String(e.contract_type || '-') },
    { label: '签约甲方', value: e.party_a || '-' },
    { label: '签约乙方', value: e.party_b || '-' },
    { label: '合同金额', value: e.amount ? `¥${Number(e.amount).toLocaleString()}` : '-' },
    { label: '签署日期', value: e.sign_date || '-' },
    { label: '到期日期', value: e.expire_date || '-' },
  ]
})

const clauses = computed(() => (task.value?.extracted?.key_clauses as string[]) || [])

function mergeContractOptions(suggestions: ImportLinkSuggestion[]) {
  const seen = new Set<number>()
  const merged: ContractItem[] = []
  for (const item of suggestions) {
    if (!seen.has(item.contract.id)) {
      seen.add(item.contract.id)
      merged.push(item.contract)
    }
  }
  for (const item of contractOptions.value) {
    if (!seen.has(item.id)) {
      seen.add(item.id)
      merged.push(item)
    }
  }
  contractOptions.value = merged
}

async function loadLinkSuggestions(taskId: number, q = '') {
  loadingSuggestions.value = true
  try {
    const res = await fetchImportLinkSuggestions(taskId, q, 20)
    if (q) {
      mergeContractOptions(res.items)
      return
    }
    linkSuggestions.value = res.items
    contractOptions.value = res.items.map((item) => item.contract)
    if (importMode.value === 'link' && !linkedContractId.value && res.items.length > 0 && res.items[0].match_score >= 70) {
      linkedContractId.value = res.items[0].contract.id
    }
  } catch {
    if (!q) linkSuggestions.value = []
  } finally {
    loadingSuggestions.value = false
  }
}

function selectSuggestedContract(id: number) {
  linkedContractId.value = id
}

function onContractSearch(keyword: string) {
  if (!task.value) return
  const q = keyword.trim()
  loadLinkSuggestions(task.value.id, q)
}

watch(task, async (val) => {
  importMode.value = 'new'
  linkedContractId.value = null
  versionLabel.value = '导入版本'
  linkSuggestions.value = []
  contractOptions.value = []
  if (!val) return
  await loadLinkSuggestions(val.id)
})

watch(importMode, async (mode) => {
  if (mode !== 'link' || !task.value) return
  if (linkSuggestions.value.length === 0) {
    await loadLinkSuggestions(task.value.id)
  } else if (!linkedContractId.value && linkSuggestions.value[0].match_score >= 70) {
    linkedContractId.value = linkSuggestions.value[0].contract.id
  }
})

function triggerUpload() {
  fileInput.value?.click()
}

function onDrop(e: DragEvent) {
  dragging.value = false
  const files = Array.from(e.dataTransfer?.files || [])
  if (files.length) handleFiles(files)
}

function onFile(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (files.length) handleFiles(files)
}

async function loadTaskLog() {
  try {
    const res = await fetchImportTasks(30)
    taskLog.value = res.items
  } catch {
    /* ignore */
  }
}

function selectTask(row: ImportTask) {
  if (row.status === 'completed') task.value = row
}

async function onRetry(id: number) {
  await retryImportTask(id)
  ElMessage.success('已重新加入解析队列')
  await loadTaskLog()
}

async function pollUntilDone(taskId: number) {
  for (let i = 0; i < 120; i++) {
    const t = await fetchImportTask(taskId)
    pollProgress.value = t.progress || 0
    task.value = t
    if (t.status === 'processing' || t.status === 'queued') {
      markStep(2, 'loading', '⟳', `解析中 ${t.progress}%`)
    }
    if (t.status === 'completed') {
      markStep(2, 'done', '✓')
      markStep(3, 'done', '✓', '提取完成，请核对')
      return t
    }
    if (t.status === 'failed') {
      markStep(2, 'done', '!')
      markStep(3, 'done', '!', '解析失败，可在日志中重试')
      throw new Error('解析失败')
    }
    await delay(1000)
  }
  throw new Error('解析超时')
}

async function pollBatch(taskIds: number[]) {
  const remaining = new Set(taskIds)
  let last: ImportTask | null = null
  for (let i = 0; i < 180 && remaining.size; i++) {
    const doneProgress: number[] = []
    for (const id of [...remaining]) {
      const t = await fetchImportTask(id)
      last = t
      doneProgress.push(t.progress || 0)
      if (t.status === 'completed' || t.status === 'failed') remaining.delete(id)
    }
    pollProgress.value = doneProgress.length
      ? Math.round(doneProgress.reduce((a, b) => a + b, 0) / doneProgress.length)
      : 0
    if (last) task.value = last
    markStep(2, 'loading', '⟳', `批量解析 ${taskIds.length - remaining.size}/${taskIds.length}`)
    if (!remaining.size) break
    await delay(1000)
  }
  await loadTaskLog()
  return last
}

async function handleFiles(files: File[]) {
  const maxBytes = 100 * 1024 * 1024
  const valid = files.filter((f) => f.size <= maxBytes)
  if (!valid.length) {
    ElMessage.error('文件超过 100MB 或为空')
    return
  }
  processing.value = true
  task.value = null
  pollProgress.value = 0
  for (let i = 0; i < steps.value.length; i++) {
    steps.value[i].state = i === 0 ? 'loading' : 'pending'
    steps.value[i].icon = i === 0 ? '⟳' : '○'
    if (i === 0) steps.value[i].status = valid.map((f) => f.name).join(', ')
  }
  try {
    markStep(0, 'done', '✓')
    markStep(1, 'loading', '⟳', '上传并加入队列...')
    let first: ImportTask
    let ids: number[] = []
    if (valid.length === 1) {
      first = await uploadContractImport(valid[0])
      ids = [first.id]
    } else {
      const batch = await uploadContractImportBatch(valid.slice(0, 50))
      if (!batch.items.length) throw new Error('批量上传失败')
      first = batch.items[0]
      ids = batch.items.map((t) => t.id)
    }
    markStep(1, 'done', '✓', `任务 #${first.id}${ids.length > 1 ? ` 等 ${ids.length} 个` : ''}`)
    markStep(2, 'loading', '⟳', '后台 OCR 解析中...')
    if (ids.length === 1) {
      await pollUntilDone(first.id)
    } else {
      await pollBatch(ids)
      markStep(2, 'done', '✓')
      markStep(3, 'done', '✓', '批量解析完成，请在日志中核对')
    }
    ElMessage.success('解析完成')
    trackAnalytics('contract_import', { count: ids.length }).catch(() => undefined)
    await loadTaskLog()
  } catch {
    ElMessage.error('导入失败')
    await loadTaskLog()
  } finally {
    processing.value = false
  }
}

async function handleFile(file: File) {
  await handleFiles([file])
}

onMounted(loadTaskLog)
onUnmounted(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})

function markStep(index: number, state: string, icon: string, status?: string) {
  steps.value[index].state = state
  steps.value[index].icon = icon
  if (status) steps.value[index].status = status
}

async function onConfirm() {
  if (!task.value) return
  if (importMode.value === 'link' && !linkedContractId.value) {
    ElMessage.warning('请选择要关联的已有合同')
    return
  }
  confirming.value = true
  try {
    const result = await confirmImport(task.value.id, {
      target_contract_id: importMode.value === 'link' ? linkedContractId.value! : undefined,
      version_label: importMode.value === 'link' ? versionLabel.value : undefined,
    })
    const msg =
      result.import_mode === 'version'
        ? `已追加为 ${result.version} 版本`
        : '合同已新建入库'
    ElMessage.success(msg)
    router.push(`/cms/contracts/${result.contract.id}`)
  } finally {
    confirming.value = false
  }
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}
</script>

<style scoped>
.page-header h1 { margin: 0; font-size: 26px; color: #1e1b4b; }
.subtitle { margin: 4px 0 0; color: var(--cms-muted); font-size: 14px; }
.upload-zone {
  border: 2px dashed var(--cms-border);
  border-radius: 12px;
  padding: 48px;
  text-align: center;
  cursor: pointer;
  background: #f8fafc;
}
.upload-zone.dragging, .upload-zone:hover { border-color: var(--cms-primary); background: rgba(79,70,229,0.03); }
.upload-zone .icon { font-size: 48px; margin-bottom: 12px; }
.upload-zone h3 { margin: 0 0 8px; }
.upload-zone p { color: var(--cms-muted); font-size: 14px; }
.formats { margin-top: 12px; display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
.formats span { padding: 4px 12px; background: white; border: 1px solid var(--cms-border); border-radius: 6px; font-size: 12px; }
.ocr-progress { margin-top: 24px; }
.ocr-progress h4 { margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
.step { display: flex; gap: 12px; padding: 10px 0; align-items: center; }
.step-icon { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.step-icon.done { background: rgba(16,185,129,0.1); color: #10b981; }
.step-icon.loading { background: rgba(79,70,229,0.1); color: var(--cms-primary); }
.step-icon.pending { background: rgba(100,116,139,0.1); color: #94a3b8; }
.step-status { font-size: 12px; color: var(--cms-muted); }
.card-head { display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; border-bottom: 1px solid var(--cms-border); }
.card-head h3 { margin: 0; font-size: 16px; }
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.info-item .label { font-size: 12px; color: var(--cms-muted); margin-bottom: 4px; }
.info-item .value { font-size: 14px; font-weight: 500; }
.clauses { margin-top: 16px; padding: 12px; background: #f8fafc; border-radius: 8px; }
.clauses-title { font-size: 13px; font-weight: 500; margin-bottom: 8px; }
.clauses .cms-tag { margin-right: 6px; margin-bottom: 6px; }
.import-target {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--cms-border);
}
.import-target-title { font-size: 14px; font-weight: 600; margin-bottom: 12px; color: #1e1b4b; }
.link-fields { margin-top: 16px; display: flex; flex-direction: column; gap: 12px; max-width: 640px; }
.suggest-block { display: flex; flex-direction: column; gap: 8px; }
.suggest-title { font-size: 13px; font-weight: 600; color: #1e1b4b; display: flex; align-items: center; gap: 8px; }
.suggest-item {
  border: 1px solid var(--cms-border);
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  background: #fff;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.suggest-item:hover { border-color: var(--cms-primary); }
.suggest-item.active {
  border-color: var(--cms-primary);
  box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.12);
  background: rgba(79, 70, 229, 0.03);
}
.suggest-main { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.suggest-name { font-size: 14px; font-weight: 600; color: #1e1b4b; }
.suggest-score { font-size: 12px; color: var(--cms-primary); font-weight: 600; white-space: nowrap; }
.suggest-meta { margin-top: 4px; font-size: 12px; color: var(--cms-muted); }
.suggest-reason { margin-top: 4px; font-size: 12px; color: #6366f1; }
.suggest-empty { font-size: 12px; color: var(--cms-muted); padding: 8px 0; }
.link-hint { margin: 0; font-size: 12px; color: var(--cms-muted); }
.char-count { margin-top: 12px; font-size: 12px; color: var(--cms-muted); }
.parse-log { margin-top: 24px; }
.parse-log-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.parse-log h4 { margin: 0; }
.parse-warnings p { margin: 4px 0; font-size: 13px; color: #b45309; }
</style>
