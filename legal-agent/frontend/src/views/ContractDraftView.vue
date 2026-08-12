<template>
  <div class="draft-page">
    <div class="page-head">
      <h2>{{ AI_NAME }} 合同起草</h2>
      <button type="button" class="history-link" @click="showHistory = !showHistory">
        历史记录{{ drafts.length ? ` (${drafts.length})` : '' }}
      </button>
    </div>

    <div class="layout">
      <div class="main-col">
        <div class="mode-tabs">
          <button
            type="button"
            class="mode-tab"
            :class="{ active: draftType === 'contract' }"
            @click="draftType = 'contract'"
          >
            生成合同
          </button>
          <button
            type="button"
            class="mode-tab"
            :class="{ active: draftType === 'clause' }"
            @click="draftType = 'clause'"
          >
            生成条款
          </button>
        </div>

        <div class="draft-form">
          <p class="form-intro">帮我起草一份{{ draftType === 'clause' ? '合同条款' : '合同' }}，按照以下要求：</p>
          <div class="field">
            <label>合同目的 <span class="required">必填</span></label>
            <el-input v-model="purpose" type="textarea" :rows="2" placeholder="例如，购买法律数据库年度订阅服务" />
          </div>
          <div class="field">
            <label>我方立场</label>
            <el-input v-model="position" placeholder="例如，购买方 / 甲方" />
          </div>
          <div class="field">
            <label>其他信息</label>
            <el-input
              v-model="extraInfo"
              type="textarea"
              :rows="2"
              placeholder="例如，使用 API 方式交付，每周更新数据，合同期限 1 年"
            />
          </div>

          <div class="form-toolbar">
            <el-select v-model="style" class="style-select" placeholder="起草风格">
              <el-option v-for="s in styles" :key="s" :label="s" :value="s" />
            </el-select>
            <button type="button" class="send-btn" :disabled="!purpose.trim() || loading" @click="submit">
              {{ loading ? '...' : '✈' }}
            </button>
          </div>
        </div>

        <div v-if="result" class="result-box">
          <div class="result-head">
            <h4>生成结果</h4>
            <button type="button" class="copy-btn" @click="copyResult">复制</button>
          </div>
          <div class="markdown-body">{{ result }}</div>
        </div>
      </div>

      <aside v-if="showHistory" class="history-panel">
        <h4>起草历史</h4>
        <el-empty v-if="!drafts.length" description="暂无记录" />
        <button v-for="d in drafts" :key="d.id" type="button" class="history-item" @click="loadDraft(d)">
          <span class="hi-purpose">{{ d.purpose || '未命名' }}</span>
          <span class="hi-meta">{{ formatDate(d.created_at) }} · {{ d.style || style }}</span>
        </button>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { AI_NAME } from '@/constants/brand'
import { draftContract, fetchDraftHistory, fetchDraftStyles, type ContractDraftItem } from '@/api/legal'

const draftType = ref('contract')
const purpose = ref('')
const position = ref('')
const extraInfo = ref('')
const style = ref('简明居中')
const styles = ref<string[]>([])
const result = ref('')
const loading = ref(false)
const drafts = ref<ContractDraftItem[]>([])
const showHistory = ref(false)

onMounted(async () => {
  styles.value = await fetchDraftStyles()
  try {
    drafts.value = await fetchDraftHistory()
  } catch {
    drafts.value = []
  }
})

function formatDate(iso: string) {
  return iso?.slice(0, 16).replace('T', ' ') || ''
}

function loadDraft(d: ContractDraftItem) {
  result.value = d.content
  if (d.purpose) purpose.value = d.purpose
  if (d.position) position.value = d.position
  if (d.style) style.value = d.style
  if (d.draft_type) draftType.value = d.draft_type
  ElMessage.success('已加载历史起草记录')
}

async function copyResult() {
  try {
    await navigator.clipboard.writeText(result.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败')
  }
}

async function submit() {
  if (!purpose.value.trim() || loading.value) return
  loading.value = true
  result.value = ''
  try {
    const data = await draftContract({
      draft_type: draftType.value,
      purpose: purpose.value,
      position: position.value,
      extra_info: extraInfo.value,
      style: style.value,
    })
    result.value = data.content
    drafts.value = await fetchDraftHistory()
    ElMessage.success('生成完成')
  } catch {
    ElMessage.error('生成失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.draft-page { max-width: 960px; margin: 0 auto; }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-head h2 { margin: 0; font-size: 20px; }
.history-link { border: none; background: none; color: var(--brand-primary); cursor: pointer; font-size: 13px; }
.layout { display: flex; gap: 20px; align-items: flex-start; }
.main-col { flex: 1; min-width: 0; }
.history-panel {
  width: 260px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 16px;
  max-height: 70vh;
  overflow-y: auto;
}
.history-panel h4 { margin: 0 0 12px; font-size: 14px; }
.history-item {
  display: block;
  width: 100%;
  text-align: left;
  border: none;
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
}
.history-item:hover { background: #eef7f8; }
.hi-purpose { display: block; font-size: 13px; font-weight: 500; margin-bottom: 4px; word-break: break-all; }
.hi-meta { font-size: 11px; color: var(--brand-muted); }
.mode-tabs { display: flex; border-bottom: 1px solid #e0e0e0; margin-bottom: 24px; }
.mode-tab {
  padding: 12px 24px;
  border: none;
  background: none;
  font-size: 14px;
  cursor: pointer;
  color: var(--brand-muted);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.mode-tab.active { color: var(--brand-primary); border-bottom-color: var(--brand-primary); }
.draft-form { background: #fff; border: 1px solid #e0e0e0; border-radius: 12px; padding: 24px; }
.form-intro { margin: 0 0 16px; font-size: 15px; }
.field { margin-bottom: 16px; }
.field label { display: block; margin-bottom: 8px; font-size: 13px; color: var(--brand-muted); }
.required { color: #e53935; }
.form-toolbar { display: flex; align-items: center; gap: 12px; margin-top: 16px; padding-top: 16px; border-top: 1px solid #f0f0f0; }
.style-select { flex: 1; max-width: 220px; }
.send-btn {
  margin-left: auto;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: none;
  background: var(--brand-primary);
  color: #fff;
  font-size: 18px;
  cursor: pointer;
}
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.result-box { margin-top: 24px; background: #fff; border-radius: 12px; padding: 24px; border: 1px solid #e8ecf0; }
.result-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.result-head h4 { margin: 0; color: var(--brand-primary); }
.copy-btn { border: none; background: none; color: var(--brand-primary); cursor: pointer; font-size: 13px; }
@media (max-width: 768px) {
  .layout { flex-direction: column; }
  .history-panel { width: 100%; }
}
</style>
