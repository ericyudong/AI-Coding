<template>
  <div class="review-page">
    <div class="page-head">
      <h2>{{ AI_NAME }} | 合同审核</h2>
      <div class="head-actions">
        <button type="button" class="link-btn" @click="showChecklist = true">审核清单</button>
        <button type="button" class="link-btn" @click="showHistory = !showHistory">
          历史记录{{ history.length ? ` (${history.length})` : '' }}
        </button>
      </div>
    </div>

    <div class="layout">
      <div class="main-col">
        <div class="mode-tabs">
          <button
            type="button"
            class="mode-tab"
            :class="{ active: reviewMode === 'checklist' }"
            @click="reviewMode = 'checklist'"
          >
            清单审核
          </button>
          <button
            type="button"
            class="mode-tab"
            :class="{ active: reviewMode === 'reference' }"
            @click="reviewMode = 'reference'"
          >
            参照审核
          </button>
        </div>

        <div
          class="upload-zone"
          :class="{ dragging }"
          @dragover.prevent="dragging = true"
          @dragleave="dragging = false"
          @drop.prevent="onDrop"
          @click="triggerFile"
        >
          <input ref="fileInput" type="file" accept=".doc,.docx,.pdf" hidden @change="onFileChange" />
          <div class="upload-icon">☁</div>
          <p class="upload-title">脱敏上传、拖拽或点击上传</p>
          <p class="upload-hint">支持 50MB 以内的 doc、docx、pdf（非扫描件图片 PDF）</p>
          <button type="button" class="sample-link" @click.stop="loadSample">加载示例合同</button>
          <p v-if="selectedFile" class="selected-file">已选择：{{ selectedFile.name }}</p>
          <p v-if="parseInfo" class="parse-info">
            已解析 {{ parseInfo.char_count }} 字
            <span v-if="parseInfo.parse_warnings?.length" class="parse-warn">
              （{{ parseInfo.parse_warnings.join('；') }}）
            </span>
          </p>
        </div>

        <div class="actions">
          <button type="button" class="enter-btn" :disabled="!selectedFile || loading" @click="startReview">
            {{ loading ? 'AI 审核中...' : '进入审核' }}
          </button>
        </div>

        <div v-if="reviewResult" class="result-box">
          <div class="result-head">
            <h4>审核报告</h4>
            <button type="button" class="link-btn" @click="copyResult">复制</button>
          </div>
          <div class="markdown-body">{{ reviewResult }}</div>
        </div>
      </div>

      <aside v-if="showHistory" class="history-panel">
        <h4>审核历史</h4>
        <el-empty v-if="!history.length" description="暂无记录" />
        <button
          v-for="item in history"
          :key="item.id"
          type="button"
          class="history-item"
          @click="loadHistory(item)"
        >
          <span class="hi-name">{{ item.filename }}</span>
          <span class="hi-meta">{{ formatDate(item.created_at) }} · {{ statusLabel(item.status) }}</span>
        </button>
      </aside>
    </div>

    <el-dialog v-model="showChecklist" title="合同审核清单" width="520px">
      <ul class="checklist">
        <li v-for="item in checklistItems" :key="item">{{ item }}</li>
      </ul>
      <p class="checklist-tip">清单审核模式将按以上维度逐项分析合同并输出 Markdown 报告。</p>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { AI_NAME } from '@/constants/brand'
import {
  fetchReviewHistory,
  runContractReview,
  uploadContract,
  type ContractReviewItem,
} from '@/api/legal'

const reviewMode = ref('checklist')
const selectedFile = ref<File | null>(null)
const dragging = ref(false)
const loading = ref(false)
const reviewResult = ref('')
const parseInfo = ref<{ char_count: number; parse_warnings: string[] } | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const history = ref<ContractReviewItem[]>([])
const showHistory = ref(false)
const showChecklist = ref(false)

const checklistItems = [
  '主体资质与签约资格',
  '权利义务对等性',
  '付款/交付条款',
  '违约责任与赔偿上限',
  '保密与知识产权',
  '争议解决方式',
  '合规与监管风险',
]

onMounted(async () => {
  try {
    history.value = await fetchReviewHistory()
  } catch {
    history.value = []
  }
})

function formatDate(iso: string) {
  return iso?.slice(0, 16).replace('T', ' ') || ''
}

function statusLabel(s: string) {
  const map: Record<string, string> = {
    uploaded: '已上传',
    processing: '审核中',
    completed: '已完成',
  }
  return map[s] || s
}

function triggerFile() {
  fileInput.value?.click()
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.[0]) {
    selectedFile.value = input.files[0]
    reviewResult.value = ''
    parseInfo.value = null
  }
}

function onDrop(e: DragEvent) {
  dragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) {
    selectedFile.value = file
    reviewResult.value = ''
    parseInfo.value = null
  }
}

function loadSample() {
  const sample = `采购合同

甲方：益慧科技有限公司
乙方：示例供应商有限公司

第一条 合同标的
乙方向甲方提供企业级软件许可服务。

第二条 合同金额
合同总金额为人民币 500,000 元。

第三条 付款方式
签约后支付 30%，验收后支付 60%，质保期满支付 10%。

第四条 违约责任
逾期交付每日按合同总额 0.5‰ 支付违约金。

第五条 保密义务
双方对合作中知悉的商业秘密承担保密义务，期限为合同终止后 3 年。`
  const blob = new Blob([sample], { type: 'text/plain' })
  selectedFile.value = new File([blob], '示例采购合同.docx', {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  })
  reviewResult.value = ''
  parseInfo.value = null
  ElMessage.info('已加载示例合同')
}

function loadHistory(item: ContractReviewItem) {
  reviewResult.value = item.result || '（该记录暂无审核报告）'
  reviewMode.value = item.review_mode
  parseInfo.value = {
    char_count: item.char_count,
    parse_warnings: item.parse_warnings || [],
  }
  ElMessage.success('已加载历史审核记录')
}

async function copyResult() {
  try {
    await navigator.clipboard.writeText(reviewResult.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败')
  }
}

async function startReview() {
  if (!selectedFile.value || loading.value) return
  loading.value = true
  try {
    const upload = await uploadContract(selectedFile.value, reviewMode.value)
    parseInfo.value = {
      char_count: upload.char_count ?? 0,
      parse_warnings: upload.parse_warnings ?? [],
    }
    const result = await runContractReview(upload.id)
    reviewResult.value = result.result
    history.value = await fetchReviewHistory()
    ElMessage.success('审核完成')
  } catch {
    ElMessage.error('审核失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.review-page { max-width: 960px; margin: 0 auto; }
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-head h2 { margin: 0; font-size: 20px; }
.head-actions { display: flex; gap: 16px; }
.link-btn { border: none; background: none; color: var(--brand-primary); cursor: pointer; font-size: 14px; }
.layout { display: flex; gap: 20px; align-items: flex-start; }
.main-col { flex: 1; min-width: 0; }
.history-panel {
  width: 260px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #e8ecf0;
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
.hi-name { display: block; font-size: 13px; font-weight: 500; margin-bottom: 4px; word-break: break-all; }
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
.mode-tab.active { color: var(--brand-primary); border-bottom-color: var(--brand-primary); font-weight: 500; }
.upload-zone {
  border: 2px dashed #c5e1e8;
  border-radius: 16px;
  padding: 56px 32px;
  text-align: center;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.upload-zone.dragging, .upload-zone:hover { border-color: var(--brand-primary); background: #f0fafb; }
.upload-icon { font-size: 48px; color: var(--brand-accent); margin-bottom: 16px; }
.upload-title { margin: 0 0 8px; font-size: 16px; font-weight: 500; }
.upload-hint { margin: 0 0 16px; font-size: 13px; color: var(--brand-muted); }
.sample-link { border: none; background: none; color: var(--brand-primary); cursor: pointer; font-size: 13px; }
.selected-file { margin-top: 16px; font-size: 13px; color: var(--brand-primary); }
.parse-info { margin-top: 8px; font-size: 12px; color: var(--brand-muted); }
.parse-warn { color: #e6a23c; }
.actions { text-align: center; margin-top: 32px; }
.enter-btn {
  padding: 12px 48px;
  border: none;
  border-radius: 999px;
  background: var(--brand-primary);
  color: #fff;
  font-size: 15px;
  cursor: pointer;
}
.enter-btn:disabled { background: #ccc; cursor: not-allowed; }
.result-box { margin-top: 32px; background: #fff; border-radius: 12px; padding: 24px; border: 1px solid #e8ecf0; }
.result-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.result-head h4 { margin: 0; color: var(--brand-primary); }
.checklist { margin: 0; padding-left: 20px; line-height: 1.9; }
.checklist-tip { margin: 16px 0 0; font-size: 13px; color: var(--brand-muted); }
@media (max-width: 768px) {
  .layout { flex-direction: column; }
  .history-panel { width: 100%; max-height: none; }
}
</style>
