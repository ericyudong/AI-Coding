<template>
  <div class="ai-gateway-page">
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="page-header">
          <h2>AI Gateway</h2>
          <div class="header-actions">
            <el-button type="primary" @click="showChat = true">
              <el-icon><ChatDotRound /></el-icon>AI 对话
            </el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- Stats Cards -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #409eff">
            <el-icon :size="24"><ChatLineRound /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.total_calls }}</div>
            <div class="stat-label">总调用次数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #67c23a">
            <el-icon :size="24"><Coin /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ formatNumber(stats.total_tokens) }}</div>
            <div class="stat-label">Token消耗</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #e6a23c">
            <el-icon :size="24"><Money /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">${{ stats.total_cost?.toFixed(4) }}</div>
            <div class="stat-label">总成本</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #f56c6c">
            <el-icon :size="24"><Warning /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.failed_calls }}</div>
            <div class="stat-label">失败次数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Model Stats -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>模型使用统计</span>
          </template>
          <el-table :data="modelStatsList" style="width: 100%">
            <el-table-column prop="model" label="模型" />
            <el-table-column prop="calls" label="调用次数" width="120" />
            <el-table-column prop="tokens" label="Token数量" width="150">
              <template #default="{ row }">
                {{ formatNumber(row.tokens) }}
              </template>
            </el-table-column>
            <el-table-column prop="cost" label="成本" width="100">
              <template #default="{ row }">
                ${{ row.cost?.toFixed(4) }}
              </template>
            </el-table-column>
            <el-table-column label="占比" width="150">
              <template #default="{ row }">
                <el-progress :percentage="getPercentage(row.calls)" :stroke-width="10" />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- Recent Invocations -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>最近调用记录</span>
              <el-button type="primary" size="small" @click="loadAuditLogs">刷新</el-button>
            </div>
          </template>
          <el-table :data="invocations" v-loading="loading" style="width: 100%">
            <el-table-column prop="trace_id" label="Trace ID" width="180">
              <template #default="{ row }">
                <el-button type="primary" link @click="viewTrace(row.trace_id)">
                  {{ row.trace_id?.substring(0, 12) }}...
                </el-button>
              </template>
            </el-table-column>
            <el-table-column prop="model_name" label="模型" width="150" />
            <el-table-column prop="provider_type" label="提供商" width="120" />
            <el-table-column label="Token" width="150">
              <template #default="{ row }">
                {{ row.total_tokens || 0 }}
              </template>
            </el-table-column>
            <el-table-column label="成本" width="80">
              <template #default="{ row }">
                ${{ row.cost?.toFixed(4) }}
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- AI Chat Dialog -->
    <el-dialog v-model="showChat" title="AI 对话" width="700px" :close-on-click-modal="false">
      <div class="chat-container">
        <div class="chat-messages" ref="chatMessagesRef">
          <div 
            v-for="(msg, index) in chatMessages" 
            :key="index" 
            :class="['chat-message', msg.role]"
          >
            <div class="message-avatar">
              <el-icon v-if="msg.role === 'user'"><User /></el-icon>
              <el-icon v-else><ChatDotRound /></el-icon>
            </div>
            <div class="message-content">
              <div class="message-text">{{ msg.content }}</div>
            </div>
          </div>
          <div v-if="chatLoading" class="chat-message assistant">
            <div class="message-avatar">
              <el-icon><ChatDotRound /></el-icon>
            </div>
            <div class="message-content">
              <div class="message-text loading">
                <span class="dot">.</span>
                <span class="dot">.</span>
                <span class="dot">.</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="chat-input">
          <el-select v-model="selectedModel" placeholder="选择模型" style="width: 150px; margin-right: 10px">
            <el-option
              v-for="model in availableModels"
              :key="model.id"
              :label="model.display_name"
              :value="model.id"
            />
          </el-select>
          <el-input 
            v-model="chatInput" 
            placeholder="输入消息..." 
            @keyup.enter="sendMessage"
            :disabled="chatLoading"
          />
          <el-button type="primary" @click="sendMessage" :loading="chatLoading" style="margin-left: 10px">
            发送
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- Trace Detail Dialog -->
    <el-dialog v-model="showTraceDialog" title="调用详情" width="600px">
      <el-descriptions :column="2" border v-if="currentTrace">
        <el-descriptions-item label="Trace ID" :span="2">{{ currentTrace.trace_id }}</el-descriptions-item>
        <el-descriptions-item label="模型">{{ currentTrace.model_name }}</el-descriptions-item>
        <el-descriptions-item label="提供商">{{ currentTrace.provider_type }}</el-descriptions-item>
        <el-descriptions-item label="请求Token">{{ currentTrace.request_tokens }}</el-descriptions-item>
        <el-descriptions-item label="响应Token">{{ currentTrace.response_tokens }}</el-descriptions-item>
        <el-descriptions-item label="总Token">{{ currentTrace.total_tokens }}</el-descriptions-item>
        <el-descriptions-item label="成本">${{ currentTrace.cost?.toFixed(6) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="currentTrace.status === 'success' ? 'success' : 'danger'">
            {{ currentTrace.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="时间">{{ formatTime(currentTrace.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="错误信息" :span="2" v-if="currentTrace.error_message">
          <div class="error-message">{{ currentTrace.error_message }}</div>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { ChatDotRound, ChatLineRound, Coin, Money, Warning, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { gatewayApi } from '@/api'

const loading = ref(false)
const showChat = ref(false)
const showTraceDialog = ref(false)
const chatInput = ref('')
const chatLoading = ref(false)
const selectedModel = ref('')
const chatMessages = ref<any[]>([])
const chatMessagesRef = ref<HTMLElement>()

const invocations = ref<any[]>([])
const availableModels = ref<any[]>([])

const stats = reactive({
  total_calls: 0,
  total_tokens: 0,
  total_cost: 0,
  failed_calls: 0,
  model_stats: {} as Record<string, any>
})

const currentTrace = ref<any>(null)

const modelStatsList = computed(() => {
  return Object.entries(stats.model_stats).map(([model, data]: [string, any]) => ({
    model,
    ...data
  }))
})

const getPercentage = (calls: number) => {
  if (stats.total_calls === 0) return 0
  return Math.round((calls / stats.total_calls) * 100)
}

const formatNumber = (num: number) => {
  if (!num) return '0'
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const loadModels = async () => {
  try {
    const response = await gatewayApi.listModels()
    availableModels.value = response
    if (response.length > 0) {
      selectedModel.value = response[0].id
    }
  } catch (error) {
    console.error('Failed to load models:', error)
  }
}

const loadStats = async () => {
  try {
    const response = await gatewayApi.getCosts({ days: 7 })
    Object.assign(stats, response)
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

const loadAuditLogs = async () => {
  loading.value = true
  try {
    const response = await gatewayApi.listAuditLogs({ page_size: 20 })
    invocations.value = response.invocations || []
  } catch (error) {
    console.error('Failed to load audit logs:', error)
  } finally {
    loading.value = false
  }
}

const viewTrace = async (traceId: string) => {
  try {
    const response = await gatewayApi.getAuditDetail(traceId)
    currentTrace.value = response
    showTraceDialog.value = true
  } catch (error) {
    ElMessage.error('获取详情失败')
  }
}

const sendMessage = async () => {
  if (!chatInput.value.trim() || chatLoading.value) return

  const userMessage = chatInput.value.trim()
  chatInput.value = ''

  chatMessages.value.push({ role: 'user', content: userMessage })
  chatLoading.value = true

  await nextTick()
  scrollToBottom()

  try {
    const response = await gatewayApi.chat({
      model: selectedModel.value,
      messages: chatMessages.value
        .filter(m => m.role !== 'system')
        .map(m => ({ role: m.role, content: m.content })),
      temperature: 0.7,
      max_tokens: 2000
    })

    if (response.error) {
      chatMessages.value.push({
        role: 'assistant',
        content: `错误: ${response.error}`
      })
    } else {
      chatMessages.value.push({
        role: 'assistant',
        content: response.choices[0].message.content
      })
    }

    // Refresh stats
    loadStats()
    loadAuditLogs()
  } catch (error: any) {
    chatMessages.value.push({
      role: 'assistant',
      content: `请求失败: ${error.message || '未知错误'}`
    })
  } finally {
    chatLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

const scrollToBottom = () => {
  if (chatMessagesRef.value) {
    chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight
  }
}

onMounted(() => {
  loadModels()
  loadStats()
  loadAuditLogs()
})
</script>

<style scoped>
.ai-gateway-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  color: #303133;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  margin-right: 15px;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chat-container {
  height: 400px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
}

.chat-messages {
  height: 100%;
  overflow-y: auto;
  padding: 20px;
  background: #f5f7fa;
}

.chat-message {
  display: flex;
  margin-bottom: 20px;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #409eff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 10px;
  flex-shrink: 0;
}

.chat-message.assistant .message-avatar {
  background: #67c23a;
}

.message-content {
  max-width: 70%;
  background: white;
  border-radius: 8px;
  padding: 10px 15px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.chat-message.user .message-content {
  background: #409eff;
  color: white;
}

.message-text {
  word-break: break-all;
  white-space: pre-wrap;
}

.loading .dot {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 0; }
  50% { opacity: 1; }
}

.chat-input {
  display: flex;
  align-items: center;
}

.error-message {
  color: #f56c6c;
  padding: 10px;
  background: #fef0f0;
  border-radius: 4px;
}
</style>