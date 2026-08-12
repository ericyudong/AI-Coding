<template>
  <div class="compare-page">
    <div class="page-head">
      <h2>{{ AI_NAME }} | 合同比对</h2>
      <p class="subtitle">上传原始版与修订版，AI 自动识别条款差异与风险</p>
    </div>

    <div class="compare-grid">
      <div class="upload-box">
        <h4>原始合同</h4>
        <div
          class="upload-zone"
          :class="{ dragging: draggingLeft, filled: !!leftFile }"
          @dragover.prevent="draggingLeft = true"
          @dragleave="draggingLeft = false"
          @drop.prevent="onDrop($event, 'left')"
          @click="triggerPick('left')"
        >
          <input ref="leftInput" type="file" accept=".doc,.docx,.pdf" hidden @change="onPick($event, 'left')" />
          <template v-if="leftFile">
            <p class="file-name">📄 {{ leftFile.name }}</p>
            <button type="button" class="clear-btn" @click.stop="clearFile('left')">移除</button>
          </template>
          <template v-else>
            <p>拖拽或点击上传</p>
            <span class="hint">支持 doc、docx、pdf</span>
          </template>
        </div>
      </div>
      <div class="upload-box">
        <h4>修订合同</h4>
        <div
          class="upload-zone"
          :class="{ dragging: draggingRight, filled: !!rightFile }"
          @dragover.prevent="draggingRight = true"
          @dragleave="draggingRight = false"
          @drop.prevent="onDrop($event, 'right')"
          @click="triggerPick('right')"
        >
          <input ref="rightInput" type="file" accept=".doc,.docx,.pdf" hidden @change="onPick($event, 'right')" />
          <template v-if="rightFile">
            <p class="file-name">📄 {{ rightFile.name }}</p>
            <button type="button" class="clear-btn" @click.stop="clearFile('right')">移除</button>
          </template>
          <template v-else>
            <p>拖拽或点击上传</p>
            <span class="hint">支持 doc、docx、pdf</span>
          </template>
        </div>
      </div>
    </div>

    <div class="actions">
      <button type="button" class="compare-btn" :disabled="!canCompare || loading" @click="startCompare">
        {{ loading ? '比对中...' : '开始比对' }}
      </button>
    </div>

    <div v-if="result" class="result-panel">
      <div class="summary-card">
        <h4>🤖 AI 变更摘要</h4>
        <div class="summary-grid">
          <span>共 <strong>{{ result.summary.total }}</strong> 处变更</span>
          <span>风险变更 <strong>{{ result.summary.risk }}</strong></span>
          <span>新增 <strong>{{ result.summary.added }}</strong></span>
          <span>删除 <strong>{{ result.summary.removed }}</strong></span>
        </div>
        <p class="file-pair">{{ result.left_filename }} ↔ {{ result.right_filename }}（{{ result.elapsed_ms }}ms）</p>
        <p class="risk-note">⚠️ {{ result.risk_note }}</p>
      </div>

      <el-empty v-if="!result.changes.length" description="两版合同内容一致，未检测到差异" />

      <div v-for="(c, i) in result.changes" :key="i" class="change-block">
        <div class="section-title">{{ c.section }}</div>
        <div v-if="c.detail" class="change-detail">{{ c.detail }}</div>
        <div class="diff-row">
          <div class="diff-pane" :class="paneClass(c.change_type, 'left')">{{ c.left_text }}</div>
          <div class="diff-pane" :class="paneClass(c.change_type, 'right')">{{ c.right_text }}</div>
        </div>
        <p v-if="c.ai_note" class="ai-note">💡 {{ c.ai_note }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { AI_NAME } from '@/constants/brand'
import { compareContractFiles, type ContractCompareResult } from '@/api/legal'

const leftFile = ref<File | null>(null)
const rightFile = ref<File | null>(null)
const draggingLeft = ref(false)
const draggingRight = ref(false)
const loading = ref(false)
const result = ref<ContractCompareResult | null>(null)
const leftInput = ref<HTMLInputElement | null>(null)
const rightInput = ref<HTMLInputElement | null>(null)

const canCompare = computed(() => !!leftFile.value && !!rightFile.value)

function triggerPick(side: 'left' | 'right') {
  if (side === 'left') leftInput.value?.click()
  else rightInput.value?.click()
}

function onPick(e: Event, side: 'left' | 'right') {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (side === 'left') leftFile.value = file
  else rightFile.value = file
  result.value = null
}

function onDrop(e: DragEvent, side: 'left' | 'right') {
  if (side === 'left') draggingLeft.value = false
  else draggingRight.value = false
  const file = e.dataTransfer?.files?.[0]
  if (!file) return
  if (side === 'left') leftFile.value = file
  else rightFile.value = file
  result.value = null
}

function clearFile(side: 'left' | 'right') {
  if (side === 'left') leftFile.value = null
  else rightFile.value = null
  result.value = null
}

function paneClass(changeType: string, side: 'left' | 'right') {
  if (changeType === 'removed') return side === 'left' ? 'removed' : ''
  if (changeType === 'added') return side === 'right' ? 'added' : ''
  if (changeType === 'modified') return 'modified'
  return ''
}

async function startCompare() {
  if (!leftFile.value || !rightFile.value || loading.value) return
  loading.value = true
  result.value = null
  try {
    result.value = await compareContractFiles(leftFile.value, rightFile.value)
    ElMessage.success(`比对完成，共 ${result.value.summary.total} 处变更`)
  } catch {
    ElMessage.error('比对失败，请确认文件格式并稍后重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.compare-page { max-width: 900px; margin: 0 auto; }
.page-head { margin-bottom: 24px; }
.page-head h2 { margin: 0 0 6px; font-size: 20px; }
.subtitle { margin: 0; font-size: 13px; color: var(--brand-muted); }
.compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.upload-box h4 { margin: 0 0 12px; font-size: 14px; }
.upload-zone {
  border: 2px dashed #c5e1e8;
  border-radius: 12px;
  padding: 40px 20px;
  text-align: center;
  background: #fff;
  color: var(--brand-muted);
  cursor: pointer;
  min-height: 140px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  transition: border-color 0.2s, background 0.2s;
}
.upload-zone.dragging, .upload-zone:hover { border-color: var(--brand-primary); background: #f0fafb; }
.upload-zone.filled { border-style: solid; border-color: var(--brand-accent); }
.file-name { margin: 0; font-size: 13px; color: var(--brand-text); word-break: break-all; }
.clear-btn { margin-top: 8px; border: none; background: none; color: #e53935; cursor: pointer; font-size: 12px; }
.hint { font-size: 12px; }
.actions { text-align: center; margin-top: 24px; }
.compare-btn {
  padding: 12px 48px;
  border: none;
  border-radius: 999px;
  background: var(--brand-primary);
  color: #fff;
  font-size: 15px;
  cursor: pointer;
}
.compare-btn:disabled { background: #ccc; cursor: not-allowed; }
.result-panel { margin-top: 32px; }
.summary-card {
  background: #fff;
  border: 1px solid #e8ecf0;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}
.summary-card h4 { margin: 0 0 12px; color: var(--brand-primary); }
.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; font-size: 14px; }
.file-pair { margin: 12px 0 0; font-size: 12px; color: var(--brand-muted); }
.risk-note { margin: 10px 0 0; padding: 10px; background: rgba(229,57,53,0.06); border-radius: 8px; font-size: 13px; }
.change-block { background: #fff; border: 1px solid #e8ecf0; border-radius: 10px; padding: 16px; margin-bottom: 12px; }
.section-title { font-weight: 600; margin-bottom: 10px; font-size: 14px; }
.change-detail {
  margin: -2px 0 10px;
  padding: 10px 12px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: #92400e;
}
.diff-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden; }
.diff-pane { padding: 12px; font-size: 13px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.diff-pane:first-child { border-right: 1px solid #e0e0e0; }
.diff-pane.removed { background: rgba(229,57,53,0.08); }
.diff-pane.added { background: rgba(38,166,154,0.1); }
.diff-pane.modified { background: rgba(255,193,7,0.1); }
.ai-note { margin: 8px 0 0; font-size: 12px; color: var(--brand-muted); }
@media (max-width: 768px) {
  .compare-grid { grid-template-columns: 1fr; }
  .summary-grid { grid-template-columns: 1fr 1fr; }
  .diff-row { grid-template-columns: 1fr; }
}
</style>
