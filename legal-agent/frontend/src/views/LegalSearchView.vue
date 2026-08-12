<template>
  <div class="search-page">
    <div class="page-head">
      <h2>{{ AI_NAME }} | 法律检索</h2>
      <RouterLink to="/search" class="history-link">历史记录</RouterLink>
    </div>

    <div class="type-tabs">
      <button
        v-for="t in searchTypes"
        :key="t.id"
        type="button"
        class="type-tab"
        :class="{ active: activeType === t.id }"
        @click="activeType = t.id"
      >
        {{ t.label }}
      </button>
    </div>

    <div class="input-area">
      <textarea
        v-model="query"
        class="query-input"
        placeholder="输入你的法律问题..."
        rows="4"
        @keydown.ctrl.enter="submit"
      />
      <div class="input-toolbar">
        <button type="button" class="tool-btn" @click="optimizeQuery">问题优化</button>
        <button type="button" class="send-btn" :disabled="loading || !query.trim()" @click="submit">
          {{ loading ? '...' : '→' }}
        </button>
      </div>
    </div>

    <div v-if="answer" class="result-box">
      <h4>分析结果</h4>
      <div class="markdown-body">{{ answer }}</div>
      <ul v-if="references.length" class="refs">
        <li v-for="(ref, i) in references" :key="i">{{ ref }}</li>
      </ul>
    </div>

    <div class="suggestions">
      <div class="suggestions-head">
        <span>试一试：</span>
        <button type="button" class="refresh-btn" @click="rotateSuggestions">换一换</button>
      </div>
      <div class="suggestion-grid">
        <button
          v-for="(item, i) in visibleSuggestions"
          :key="i"
          type="button"
          class="suggestion-card"
          @click="useSuggestion(item)"
        >
          {{ item }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { AI_NAME } from '@/constants/brand'
import { fetchSearchSuggestions, fetchSearchTypes, legalSearch } from '@/api/legal'

const route = useRoute()
const searchTypes = ref<{ id: string; label: string }[]>([])
const suggestions = ref<string[]>([])
const visibleSuggestions = ref<string[]>([])
const activeType = ref('comprehensive')
const query = ref('')
const answer = ref('')
const references = ref<string[]>([])
const loading = ref(false)
let suggestionOffset = 0

onMounted(async () => {
  searchTypes.value = await fetchSearchTypes()
  suggestions.value = await fetchSearchSuggestions()
  rotateSuggestions()
  if (route.query.type) activeType.value = String(route.query.type)
  if (route.query.q) query.value = String(route.query.q)
})

watch(
  () => route.query.type,
  (v) => {
    if (v) activeType.value = String(v)
  }
)

function rotateSuggestions() {
  const items = suggestions.value
  if (!items.length) return
  const slice = []
  for (let i = 0; i < 4; i++) {
    slice.push(items[(suggestionOffset + i) % items.length])
  }
  visibleSuggestions.value = slice
  suggestionOffset = (suggestionOffset + 1) % items.length
}

function useSuggestion(text: string) {
  query.value = text
}

function optimizeQuery() {
  if (!query.value.trim()) return
  query.value = `请从法律依据、实务要点、风险提示三个维度分析：${query.value}`
  ElMessage.success('已优化问题表述')
}

async function submit() {
  if (!query.value.trim() || loading.value) return
  loading.value = true
  answer.value = ''
  try {
    const data = await legalSearch(query.value, activeType.value)
    answer.value = data.answer
    references.value = data.references || []
  } catch {
    ElMessage.error('检索失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.search-page {
  max-width: 800px;
  margin: 0 auto;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-head h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.history-link {
  font-size: 13px;
  color: var(--brand-muted);
}

.type-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.type-tab {
  padding: 8px 20px;
  border: 1px solid #e0e0e0;
  border-radius: 999px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  color: var(--brand-muted);
}

.type-tab.active {
  background: var(--brand-primary);
  border-color: var(--brand-primary);
  color: #fff;
}

.input-area {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 24px;
}

.query-input {
  width: 100%;
  border: none;
  outline: none;
  resize: vertical;
  font-size: 15px;
  line-height: 1.6;
  font-family: inherit;
}

.input-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.tool-btn {
  border: none;
  background: none;
  color: var(--brand-muted);
  font-size: 13px;
  cursor: pointer;
}

.send-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: var(--brand-primary);
  color: #fff;
  font-size: 18px;
  cursor: pointer;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.result-box {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
  border: 1px solid #e8ecf0;
}

.result-box h4 {
  margin: 0 0 12px;
  color: var(--brand-primary);
}

.refs {
  margin: 12px 0 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--brand-muted);
}

.suggestions-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  font-size: 14px;
}

.refresh-btn {
  border: none;
  background: none;
  color: var(--brand-primary);
  cursor: pointer;
  font-size: 13px;
}

.suggestion-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.suggestion-card {
  text-align: left;
  padding: 16px;
  background: #fff;
  border: 1px solid #e8ecf0;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
  cursor: pointer;
  color: var(--brand-text);
}

.suggestion-card:hover {
  border-color: var(--brand-primary-light);
  background: #f0fafb;
}
</style>
