<template>
  <div class="workbench">
    <header class="wb-header">
      <div class="wb-header-inner">
        <RouterLink to="/" class="brand">
          <span class="brand-logo">益</span>
          <span class="brand-title">{{ PRODUCT_NAME }}</span>
        </RouterLink>
        <div class="wb-header-right">
          <span v-if="auth.user" class="role-tag">{{ roleLabel }}</span>
          <span v-if="auth.user" class="user-email">{{ auth.user.display_name || auth.user.email }}</span>
          <el-avatar :size="28">{{ avatarText }}</el-avatar>
          <HeaderNavMenus />
          <button type="button" class="logout" @click="logout">退出</button>
        </div>
      </div>
    </header>

    <div class="wb-body">
      <aside class="history-panel" :class="{ collapsed: historyCollapsed }">
        <div class="history-head">
          <span>历史对话</span>
          <button type="button" @click="historyCollapsed = !historyCollapsed">
            {{ historyCollapsed ? '展开' : '收起' }}
          </button>
        </div>
        <ul v-if="!historyCollapsed" class="history-list">
          <li v-for="(h, i) in history" :key="i" @click="question = h">{{ h }}</li>
          <li v-if="!history.length" class="empty">暂无历史记录</li>
        </ul>
      </aside>

      <main class="wb-main">
        <section class="ai-dialog">
          <h1>法务Agent 工作台</h1>
          <p class="subtitle">以自然语言访问企业知识资产 · {{ roleLabel }}</p>

          <div class="dialog-box">
            <textarea
              v-model="question"
              rows="3"
              placeholder="请输入您想了解的问题……例如：公司以前签过类似的软件采购合同吗？"
              @keydown.ctrl.enter="ask"
            />
            <div class="dialog-actions">
              <button type="button" class="ask-btn" :disabled="asking || !question.trim()" @click="ask">
                {{ asking ? '思考中…' : '提问' }}
              </button>
              <button type="button" class="deep-btn" :disabled="asking || !question.trim()" @click="askDeep">
                深度分析
              </button>
            </div>
          </div>

          <div class="recommend">
            <span class="recommend-label">推荐问题</span>
            <button
              v-for="q in recommendations"
              :key="q"
              type="button"
              class="chip"
              @click="question = q; ask()"
            >
              {{ q }}
            </button>
          </div>

          <div v-if="answer" class="answer-card">
            <h3>AI 回答</h3>
            <div class="answer-body">{{ answer }}</div>
            <div v-if="citations.length" class="citations">
              <span class="cite-label">引用来源</span>
              <button
                v-for="(c, idx) in citations"
                :key="idx"
                type="button"
                class="cite"
                @click="goCitation(c)"
              >
                {{ c }}
              </button>
            </div>
          </div>
        </section>

        <section class="modules">
          <div
            v-for="mod in aiModules"
            :key="mod.id"
            class="module-card"
            :class="{ reserved: mod.id === 'business-model' }"
            @click="enterModule(mod)"
          >
            <div class="module-head">
              <h3>{{ mod.title }}</h3>
              <span>{{ cardIcon(mod.id) }}</span>
            </div>
            <p>{{ mod.subtitle }}</p>
            <div class="features">
              <span v-for="f in mod.features" :key="f">{{ f }}</span>
            </div>
            <button type="button" class="enter">
              {{ mod.id === 'business-model' ? '功能开发中' : '进入 →' }}
            </button>
          </div>
        </section>

        <section class="quick-row">
          <button
            v-for="link in quickLinks"
            :key="link.id"
            type="button"
            class="quick"
            @click="onQuickLink(link)"
          >
            {{ link.label }}
          </button>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import HeaderNavMenus from '@/components/HeaderNavMenus.vue'
import { PRODUCT_NAME } from '@/constants/brand'
import { fetchAiModules, fetchQuickLinks, sendChat } from '@/api/legal'
import { fetchWorkbenchRecommendations } from '@/api/prd'
import { useAuthStore } from '@/stores/auth'

interface QuickLinkItem {
  id: string
  label: string
  icon: string
}

interface AiModuleItem {
  id: string
  title: string
  subtitle: string
  features: string[]
  route: string
}

const auth = useAuthStore()
const router = useRouter()

const question = ref('')
const answer = ref('')
const citations = ref<string[]>([])
const asking = ref(false)
const historyCollapsed = ref(false)
const history = ref<string[]>([])
const recommendations = ref<string[]>([])
const roleLabel = ref('法务人员')
const quickLinks = ref<QuickLinkItem[]>([])
const aiModules = ref<AiModuleItem[]>([])
const sessionId = ref<number | null>(null)

const avatarText = computed(() => auth.user?.display_name?.[0] || 'U')

onMounted(async () => {
  await auth.loadUser()
  const [mods, links, rec] = await Promise.all([
    fetchAiModules(),
    fetchQuickLinks(),
    fetchWorkbenchRecommendations().catch(() => ({ questions: [], role: 'legal', role_label: '法务人员' })),
  ])
  aiModules.value = mods
  quickLinks.value = links
  recommendations.value = rec.questions
  roleLabel.value = rec.role_label
})

function cardIcon(id: string) {
  const map: Record<string, string> = {
    knowledge: '💡',
    contract: '📄',
    performance: '⏱',
    'business-model': '📊',
  }
  return map[id] || '✦'
}

async function ask() {
  if (!question.value.trim()) return
  asking.value = true
  try {
    const res = await sendChat(question.value.trim(), 'qa', sessionId.value ?? undefined)
    sessionId.value = res.session_id
    answer.value = res.reply?.content || ''
    citations.value = []
    if (!answer.value || answer.value.includes('演示')) {
      // keep UX clear for demo mode
    }
    history.value = [question.value.trim(), ...history.value.filter((h) => h !== question.value.trim())].slice(0, 20)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '提问失败')
  } finally {
    asking.value = false
  }
}

async function askDeep() {
  question.value = `请从法律依据、实务要点、风险提示三个维度深度分析：${question.value}`
  await ask()
}

function goCitation(c: string) {
  const m = c.match(/合同[#：:]?\s*(\d+)/)
  if (m) {
    router.push(`/cms/contracts/${m[1]}`)
    return
  }
  router.push('/cms/search')
}

function enterModule(mod: AiModuleItem) {
  if (mod.id === 'business-model') {
    ElMessage.info('商业模式AI功能开发中，敬请期待')
    router.push('/business-model')
    return
  }
  router.push(mod.route)
}

function onQuickLink(link: QuickLinkItem) {
  const map: Record<string, string> = {
    'contract-import': '/cms/import',
    'contract-search': '/cms/search',
    performance: '/performance',
    suppliers: '/performance/suppliers',
    customers: '/performance/customers',
    knowledge: '/knowledge',
    admin: '/admin/users',
  }
  router.push(map[link.id] || '/')
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.workbench {
  min-height: 100vh;
  background: linear-gradient(180deg, #0f766e 0%, #0d9488 35%, #f8fafc 35%);
}

.wb-header {
  background: rgba(255, 255, 255, 0.96);
  border-bottom: 1px solid #e2e8f0;
}

.wb-header-inner {
  max-width: 1280px;
  margin: 0 auto;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: #0f172a;
}

.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #0f766e;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}

.brand-title {
  font-weight: 600;
  font-size: 14px;
}

.wb-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #64748b;
}

.role-tag {
  background: #ecfdf5;
  color: #0f766e;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
}

.logout {
  border: none;
  background: none;
  color: inherit;
  cursor: pointer;
  font: inherit;
}

.wb-body {
  max-width: 1280px;
  margin: 0 auto;
  display: flex;
  gap: 16px;
  padding: 20px;
  min-height: calc(100vh - 56px);
}

.history-panel {
  width: 220px;
  background: #fff;
  border-radius: 12px;
  padding: 12px;
  height: fit-content;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
  transition: width 0.2s;
}

.history-panel.collapsed {
  width: 72px;
}

.history-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}

.history-head button {
  border: none;
  background: none;
  color: #0f766e;
  cursor: pointer;
  font-size: 12px;
}

.history-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.history-list li {
  font-size: 12px;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  color: #475569;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-list li:hover {
  background: #f1f5f9;
}

.history-list .empty {
  color: #94a3b8;
  cursor: default;
}

.wb-main {
  flex: 1;
  min-width: 0;
}

.ai-dialog {
  background: #fff;
  border-radius: 16px;
  padding: 28px;
  box-shadow: 0 8px 32px rgba(15, 23, 42, 0.08);
}

.ai-dialog h1 {
  margin: 0;
  font-size: 24px;
  color: #0f172a;
}

.subtitle {
  margin: 8px 0 20px;
  color: #64748b;
  font-size: 14px;
}

.dialog-box textarea {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 14px;
  font: inherit;
  resize: vertical;
  box-sizing: border-box;
}

.dialog-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

.ask-btn,
.deep-btn {
  border: none;
  border-radius: 999px;
  padding: 10px 20px;
  font-weight: 600;
  cursor: pointer;
}

.ask-btn {
  background: #0f766e;
  color: #fff;
}

.deep-btn {
  background: #f1f5f9;
  color: #334155;
}

.ask-btn:disabled,
.deep-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.recommend {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.recommend-label {
  font-size: 12px;
  color: #94a3b8;
}

.chip {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  color: #334155;
}

.answer-card {
  margin-top: 20px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.answer-card h3 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #0f766e;
}

.answer-body {
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.7;
  color: #1e293b;
}

.citations {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.cite-label {
  font-size: 12px;
  color: #94a3b8;
}

.cite {
  border: none;
  background: #ecfdf5;
  color: #0f766e;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}

.modules {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-top: 20px;
}

.module-card {
  background: #fff;
  border-radius: 14px;
  padding: 18px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
  cursor: pointer;
  transition: transform 0.15s;
}

.module-card:hover {
  transform: translateY(-2px);
}

.module-card.reserved {
  opacity: 0.85;
}

.module-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.module-head h3 {
  margin: 0;
  font-size: 16px;
  color: #0f172a;
}

.module-card p {
  margin: 8px 0 12px;
  font-size: 12px;
  color: #64748b;
}

.features {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}

.features span {
  font-size: 11px;
  background: #f1f5f9;
  color: #475569;
  padding: 3px 8px;
  border-radius: 4px;
}

.enter {
  border: 1px solid #cbd5e1;
  background: transparent;
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
  color: #0f766e;
}

.quick-row {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.quick {
  border: none;
  background: #fff;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 12px;
  color: #334155;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
  cursor: pointer;
}

@media (max-width: 960px) {
  .wb-body {
    flex-direction: column;
  }
  .history-panel,
  .history-panel.collapsed {
    width: 100%;
  }
  .modules {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
