<template>
  <div class="cms-page">
    <div class="page-header">
      <div>
        <h1>合同检索</h1>
        <p class="subtitle">支持关键词、语义、字段、正则与自然语言的多模态搜索</p>
      </div>
    </div>

    <div class="cms-card">
      <div class="cms-card-body">
        <div class="search-bar">
          <el-autocomplete
            v-model="query"
            :fetch-suggestions="onSuggest"
            clearable
            placeholder="输入关键词、自然语言或字段条件..."
            class="search-input"
            @select="onSuggestSelect"
            @keyup.enter="search"
          >
            <template #prefix>🔍</template>
          </el-autocomplete>
          <el-select v-model="mode" style="width: 140px">
            <el-option v-for="m in modeOptions" :key="m.value" :label="m.label" :value="m.value" />
          </el-select>
          <el-button type="primary" :loading="loading" @click="search">搜索</el-button>
          <el-button :type="showAdvanced ? 'primary' : 'default'" plain @click="showAdvanced = !showAdvanced">
            高级搜索 {{ showAdvanced ? '▲' : '▼' }}
          </el-button>
        </div>

        <el-collapse-transition>
          <div v-show="showAdvanced" class="advanced-panel">
            <div v-for="(row, idx) in filters" :key="idx" class="filter-row">
              <el-select v-model="row.field" placeholder="字段" style="width: 130px">
                <el-option v-for="f in fieldOptions" :key="f.value" :label="f.label" :value="f.value" />
              </el-select>
              <el-select v-model="row.operator" placeholder="条件" style="width: 110px">
                <el-option v-for="o in operatorOptions" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
              <el-input v-model="row.value" placeholder="值" style="flex: 1" />
              <el-button link type="danger" @click="removeFilter(idx)">删除</el-button>
            </div>
            <div class="advanced-actions">
              <el-button link type="primary" @click="addFilter">+ 添加条件</el-button>
              <el-button link @click="savePreset">保存为预设</el-button>
            </div>
            <p class="advanced-hint">
              结构化示例：<code>金额&gt;100万 AND 状态=履行中</code> · 正则示例：<code>合同编号:CT-\d{8}</code>
            </p>
          </div>
        </el-collapse-transition>

        <div v-if="history.length" class="chips-row">
          <span class="chips-label">历史:</span>
          <button v-for="h in history" :key="h" type="button" class="chip" @click="applyQuery(h)">{{ h }}</button>
          <el-button link size="small" @click="clearHistory">清空</el-button>
        </div>

        <div v-if="presets.length" class="chips-row">
          <span class="chips-label">预设:</span>
          <button
            v-for="p in presets"
            :key="p.name"
            type="button"
            class="chip preset"
            @click="applyPreset(p)"
          >
            {{ p.name }}
          </button>
        </div>

        <div v-if="results" class="results">
          <div class="results-head">
            <span>
              找到 <strong>{{ results.total }}</strong> 条结果 ({{ (results.elapsed_ms / 1000).toFixed(1) }}秒)
              <span v-if="results.mode" class="mode-tag">{{ modeLabel(results.mode) }}</span>
            </span>
            <span class="cms-ai-badge">语义相关度排序</span>
          </div>

          <div v-if="results.applied_filters?.length" class="applied-filters">
            已解析条件：
            <span v-for="(f, i) in results.applied_filters" :key="i" class="cms-tag cms-tag-blue">
              {{ fieldLabel(f.field) }} {{ opLabel(f.operator) }} {{ f.value }}
            </span>
          </div>

          <el-empty v-if="!results.items.length" description="未找到匹配合同，请调整关键词或筛选条件" />

          <div
            v-for="item in results.items"
            :key="item.contract.id"
            class="result-item"
            @click="$router.push(`/cms/contracts/${item.contract.id}`)"
          >
            <div class="result-top">
              <strong>📄 {{ item.contract.name }}</strong>
              <div class="result-meta">
                <span v-if="item.match_type" class="match-type">{{ item.match_type }}</span>
                <span class="relevance">相关度: {{ item.relevance }}%</span>
              </div>
            </div>
            <p class="highlight" v-html="renderHighlight(item.highlight)" />
            <div class="tags">
              <span class="cms-tag cms-tag-blue">{{ TYPE_MAP[item.contract.contract_type] || item.contract.contract_type }}</span>
              <span v-for="t in item.contract.tags.slice(0, 3)" :key="t" class="cms-tag" :class="tagClass(t)">{{ t }}</span>
              <span v-if="item.contract.amount >= 1000000" class="cms-tag cms-tag-orange">⚠️高金额</span>
              <span v-if="hasConfidentialTag(item.contract)" class="cms-tag cms-tag-green">有保密条款</span>
              <span class="amount">{{ formatAmount(item.contract.amount) }}</span>
            </div>
          </div>

          <div v-if="results.ai_suggestion" class="ai-suggestion">
            <strong>ℹ️ AI 建议</strong>
            <p>{{ results.ai_suggestion }}</p>
          </div>
        </div>
      </div>
    </div>

    <div class="cms-card">
      <div class="card-head"><h3>🏷️ 智能标签云</h3><span class="cms-ai-badge">AI 自动分类</span></div>
      <div class="cms-card-body">
        <div class="tag-cloud">
          <button v-for="t in tagCloud" :key="t.name" type="button" class="cloud-item" @click="applyQuery(t.name)">
            {{ t.name }} <span class="count">{{ t.count }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  advancedSearchContracts,
  fetchSearchSuggestions,
  fetchTagCloud,
  formatAmount,
  TYPE_MAP,
  type FieldFilter,
  type SearchMode,
  type SearchResult,
} from '@/api/cms'
import { tagClass } from '@/utils/cmsHelpers'

interface SearchPreset {
  name: string
  q: string
  mode: SearchMode
  filters: FieldFilter[]
}

const HISTORY_KEY = 'cms_search_history'
const PRESETS_KEY = 'cms_search_presets'

const modeOptions = [
  { value: 'hybrid', label: '混合检索' },
  { value: 'semantic', label: '语义检索' },
  { value: 'keyword', label: '关键词' },
  { value: 'field', label: '字段检索' },
  { value: 'regex', label: '正则检索' },
  { value: 'natural', label: '自然语言' },
] as const

const fieldOptions = [
  { value: 'amount', label: '金额' },
  { value: 'status', label: '状态' },
  { value: 'contract_type', label: '合同类型' },
  { value: 'party_a', label: '甲方' },
  { value: 'party_b', label: '乙方' },
  { value: 'code', label: '合同编号' },
  { value: 'name', label: '合同名称' },
  { value: 'owner', label: '负责人' },
  { value: 'risk_level', label: '风险等级' },
]

const operatorOptions = [
  { value: 'eq', label: '等于' },
  { value: 'contains', label: '包含' },
  { value: 'gt', label: '大于' },
  { value: 'gte', label: '大于等于' },
  { value: 'lt', label: '小于' },
  { value: 'lte', label: '小于等于' },
  { value: 'regex', label: '正则' },
]

const query = ref('')
const mode = ref<SearchMode>('hybrid')
const loading = ref(false)
const showAdvanced = ref(false)
const results = ref<SearchResult | null>(null)
const tagCloud = ref<{ name: string; count: number }[]>([])
const filters = ref<FieldFilter[]>([])
const history = ref<string[]>(loadJson(HISTORY_KEY, []))
const presets = ref<SearchPreset[]>(loadJson(PRESETS_KEY, []))

function loadJson<T>(key: string, fallback: T): T {
  try {
    return JSON.parse(localStorage.getItem(key) || 'null') ?? fallback
  } catch {
    return fallback
  }
}

function modeLabel(m: string) {
  return modeOptions.find((x) => x.value === m)?.label || m
}

function fieldLabel(field: string) {
  return fieldOptions.find((f) => f.value === field)?.label || field
}

function opLabel(op: string) {
  return operatorOptions.find((o) => o.value === op)?.label || op
}

function renderHighlight(text: string) {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return escaped.replace(/\*\*(.+?)\*\*/g, '<mark>$1</mark>')
}

function hasConfidentialTag(contract: { tags: string[]; content_text?: string }) {
  return contract.tags.some((t) => t.includes('保密')) || (contract.content_text || '').includes('保密')
}

function addFilter() {
  filters.value.push({ field: 'amount', operator: 'gt', value: '' })
}

function removeFilter(idx: number) {
  filters.value.splice(idx, 1)
}

function applyQuery(q: string) {
  query.value = q
  search()
}

function applyPreset(p: SearchPreset) {
  query.value = p.q
  mode.value = p.mode
  filters.value = [...p.filters]
  showAdvanced.value = p.filters.length > 0
  search()
}

async function savePreset() {
  const { value } = await ElMessageBox.prompt('请输入预设名称', '保存搜索条件', {
    confirmButtonText: '保存',
    cancelButtonText: '取消',
  }).catch(() => ({ value: '' }))
  if (!value?.trim()) return
  const preset: SearchPreset = {
    name: value.trim(),
    q: query.value,
    mode: mode.value,
    filters: filters.value.filter((f) => f.value.trim()),
  }
  presets.value = [preset, ...presets.value.filter((p) => p.name !== preset.name)].slice(0, 10)
  localStorage.setItem(PRESETS_KEY, JSON.stringify(presets.value))
  ElMessage.success('预设已保存')
}

function pushHistory(q: string) {
  if (!q.trim()) return
  history.value = [q, ...history.value.filter((h) => h !== q)].slice(0, 8)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
}

function clearHistory() {
  history.value = []
  localStorage.removeItem(HISTORY_KEY)
}

async function onSuggest(queryStr: string, cb: (items: { value: string }[]) => void) {
  try {
    const data = await fetchSearchSuggestions(queryStr)
    const items = [
      ...data.suggestions.map((s) => ({ value: s })),
      ...data.contracts.map((s) => ({ value: s })),
    ]
    cb(items.slice(0, 10))
  } catch {
    cb([])
  }
}

function onSuggestSelect(item: { value: string }) {
  query.value = item.value
  search()
}

async function search() {
  const q = query.value.trim()
  const activeFilters = filters.value.filter((f) => f.field && f.value.trim())
  if (!q && !activeFilters.length) {
    ElMessage.warning('请输入搜索词或添加筛选条件')
    return
  }
  loading.value = true
  try {
    if (showAdvanced.value || activeFilters.length || mode.value === 'field') {
      results.value = await advancedSearchContracts({
        q,
        mode: mode.value,
        filters: activeFilters,
      })
    } else {
      results.value = await advancedSearchContracts({ q, mode: mode.value })
    }
    if (q) pushHistory(q)
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ElMessage.error(typeof msg === 'string' ? msg : '搜索失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  tagCloud.value = await fetchTagCloud()
})
</script>

<style scoped>
.page-header h1 { margin: 0; font-size: 26px; color: #1e1b4b; }
.subtitle { margin: 4px 0 24px; color: var(--cms-muted); font-size: 14px; }
.search-bar { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.search-input { flex: 1; min-width: 280px; }
.advanced-panel {
  margin: 12px 0;
  padding: 16px;
  background: #f8fafc;
  border: 1px solid var(--cms-border);
  border-radius: 8px;
}
.filter-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.advanced-actions { display: flex; gap: 12px; margin-top: 4px; }
.advanced-hint { margin: 10px 0 0; font-size: 12px; color: var(--cms-muted); }
.advanced-hint code { background: #fff; padding: 2px 6px; border-radius: 4px; }
.chips-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 10px 0; }
.chips-label { font-size: 12px; color: var(--cms-muted); }
.chip {
  padding: 4px 12px;
  border-radius: 14px;
  border: 1px solid var(--cms-border);
  background: #fff;
  font-size: 12px;
  cursor: pointer;
}
.chip:hover { border-color: var(--cms-primary); color: var(--cms-primary); }
.chip.preset { background: rgba(79,70,229,0.06); }
.results-head { display: flex; justify-content: space-between; margin: 16px 0; font-size: 14px; color: var(--cms-muted); }
.mode-tag { margin-left: 8px; padding: 2px 8px; background: #eef2ff; border-radius: 10px; font-size: 12px; }
.applied-filters { margin-bottom: 12px; font-size: 13px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.result-item { padding: 16px; border: 1px solid var(--cms-border); border-radius: 8px; margin-bottom: 12px; cursor: pointer; }
.result-item:hover { border-color: var(--cms-primary-light); background: rgba(79,70,229,0.02); }
.result-top { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; }
.result-meta { display: flex; gap: 10px; align-items: center; }
.match-type { font-size: 11px; color: var(--cms-muted); background: #f1f5f9; padding: 2px 8px; border-radius: 8px; }
.relevance { color: #059669; font-size: 13px; white-space: nowrap; }
.highlight { font-size: 14px; line-height: 1.6; margin: 0 0 8px; color: var(--cms-text); }
.highlight :deep(mark) { background: #fef08a; padding: 0 2px; border-radius: 2px; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.amount { margin-left: auto; font-size: 12px; color: var(--cms-muted); }
.ai-suggestion { margin-top: 16px; padding: 16px; background: linear-gradient(135deg, #eef2ff, #f0fdf4); border-radius: 8px; border: 1px solid rgba(79,70,229,0.1); }
.ai-suggestion p { margin: 8px 0 0; font-size: 14px; }
.card-head { display: flex; justify-content: space-between; align-items: center; padding: 16px 24px; border-bottom: 1px solid var(--cms-border); }
.card-head h3 { margin: 0; font-size: 16px; }
.tag-cloud { display: flex; flex-wrap: wrap; gap: 8px; }
.cloud-item { padding: 6px 16px; border-radius: 16px; background: rgba(79,70,229,0.06); border: 1px solid rgba(79,70,229,0.12); font-size: 13px; cursor: pointer; }
.cloud-item:hover { background: var(--cms-primary); color: white; }
.count { font-size: 11px; opacity: 0.7; margin-left: 4px; }
.cms-tag-orange { background: rgba(245,158,11,0.12); color: #b45309; }
.cms-tag-green { background: rgba(16,185,129,0.12); color: #047857; }
</style>
