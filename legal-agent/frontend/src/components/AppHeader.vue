<template>
  <header class="app-header">
    <div class="header-left">
      <RouterLink to="/" class="brand">
        <span class="brand-logo">益</span>
        <div class="brand-text">
          <span class="brand-title">{{ PRODUCT_NAME }}</span>
          <span v-if="subtitle" class="brand-sub">{{ subtitle }}</span>
        </div>
      </RouterLink>
    </div>
    <div class="header-right">
      <span v-if="auth.user" class="user-email">{{ auth.user.email }}</span>
      <el-dropdown v-if="auth.user" trigger="click" @command="onCommand">
        <span class="user-trigger">
          <el-avatar :size="28">{{ avatarText }}</el-avatar>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="home">返回首页</el-dropdown-item>
            <el-dropdown-item divided command="logout">退出</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <HeaderNavMenus />
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import HeaderNavMenus from '@/components/HeaderNavMenus.vue'
import { PRODUCT_NAME } from '@/constants/brand'
import { useAuthStore } from '@/stores/auth'

defineProps<{ subtitle?: string }>()

const auth = useAuthStore()
const router = useRouter()

const avatarText = computed(() => auth.user?.display_name?.[0] || auth.user?.username?.[0] || 'U')

function onCommand(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  } else if (cmd === 'home') {
    router.push('/')
  }
}
</script>

<style scoped>
.app-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e8ecf0;
  position: sticky;
  top: 0;
  z-index: 100;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.brand-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--brand-text);
}

.brand-sub {
  font-size: 12px;
  color: var(--brand-muted);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: var(--brand-muted);
}

.user-email {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-trigger {
  cursor: pointer;
}

.header-link {
  cursor: pointer;
}

.header-link:hover {
  color: var(--brand-primary);
}
</style>
