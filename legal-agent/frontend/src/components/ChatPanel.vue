<template>
  <div class="chat-panel">
    <div class="panel-head">
      <h2>{{ AI_NAME }} | {{ title }}</h2>
      <p v-if="subtitle" class="subtitle">{{ subtitle }}</p>
    </div>

    <div v-if="messages.length === 0" class="examples">
      <p class="examples-label">试一试：</p>
      <div class="example-cards">
        <button
          v-for="(ex, i) in examples"
          :key="i"
          type="button"
          class="example-card"
          @click="ask(ex)"
        >
          <span class="ex-label">示例{{ i + 1 }}：</span>
          {{ ex }}
          <span class="ex-arrow">→</span>
        </button>
      </div>
    </div>

    <div v-else class="messages">
      <div v-for="msg in messages" :key="msg.id" class="message" :class="msg.role">
        <div class="bubble">{{ msg.content }}</div>
      </div>
    </div>

    <div class="input-area">
      <textarea
        v-model="input"
        class="chat-input"
        placeholder="请在这里提问，问题尽可能详细具体……"
        rows="3"
        @keydown.ctrl.enter="send"
      />
      <button type="button" class="send-btn" :disabled="!input.trim() || loading" @click="send">
        {{ loading ? '...' : '✈' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { AI_NAME } from '@/constants/brand'
import { sendChat } from '@/api/legal'

const props = defineProps<{
  module: string
  title: string
  subtitle?: string
  examples: string[]
}>()

interface Message {
  id: number
  role: string
  content: string
}

const input = ref('')
const loading = ref(false)
const messages = ref<Message[]>([])
const sessionId = ref<number | undefined>()

function ask(text: string) {
  input.value = text
  send()
}

async function send() {
  if (!input.value.trim() || loading.value) return
  const text = input.value.trim()
  input.value = ''
  loading.value = true
  try {
    const data = await sendChat(text, props.module, sessionId.value)
    sessionId.value = data.session_id
    messages.value.push(data.message, data.reply)
  } catch {
    ElMessage.error('发送失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.chat-panel {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - var(--header-height) - 96px);
}

.panel-head {
  text-align: center;
  margin-bottom: 32px;
}

.panel-head h2 {
  margin: 0 0 8px;
  font-size: 20px;
}

.subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--brand-muted);
}

.examples-label {
  font-size: 14px;
  margin-bottom: 12px;
}

.example-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.example-card {
  text-align: left;
  padding: 16px 20px;
  background: #fff;
  border: 1px solid #b2dfdb;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  cursor: pointer;
  position: relative;
  color: var(--brand-text);
}

.example-card:hover {
  border-color: var(--brand-primary);
  background: #f0fafb;
}

.ex-label {
  color: var(--brand-primary);
  font-weight: 500;
}

.ex-arrow {
  position: absolute;
  right: 16px;
  bottom: 16px;
  color: var(--brand-primary);
}

.messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 16px;
}

.message.user {
  align-self: flex-end;
}

.message.assistant {
  align-self: flex-start;
}

.bubble {
  max-width: 600px;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}

.message.user .bubble {
  background: var(--brand-primary);
  color: #fff;
}

.message.assistant .bubble {
  background: #fff;
  border: 1px solid #e8ecf0;
}

.input-area {
  margin-top: auto;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 12px;
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.chat-input {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-size: 14px;
  line-height: 1.6;
  font-family: inherit;
}

.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: var(--brand-primary);
  color: #fff;
  font-size: 18px;
  cursor: pointer;
  flex-shrink: 0;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
