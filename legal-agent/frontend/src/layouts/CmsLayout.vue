<template>
  <div class="cms-app">
    <nav class="cms-navbar">
      <div class="cms-brand">
        <RouterLink to="/" class="back-home" title="返回法务首页">←</RouterLink>
        <div class="logo-icon">📋</div>
        <div>
          <span class="brand-title">合同AI</span>
        </div>
      </div>
      <div class="cms-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: isActive(item.to) }"
        >
          {{ item.label }}
        </RouterLink>
      </div>
      <div class="cms-nav-right">
        <span v-if="auth.user" class="user-name">{{ auth.user.display_name || auth.user.username }}</span>
        <div class="avatar">{{ avatarText }}</div>
      </div>
    </nav>
    <main class="cms-container">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()

const navItems = [
  { to: '/cms/ledger', label: '合同列表' },
  { to: '/cms/import', label: '导入与解析' },
  { to: '/cms/search', label: '企业合同搜索' },
  { to: '/cms/compare', label: '版本管理' },
]

const avatarText = computed(() => auth.user?.display_name?.[0] || auth.user?.username?.[0] || 'U')

function isActive(path: string) {
  if (path === '/cms/ledger') {
    return route.path === '/cms' || route.path.startsWith('/cms/ledger') || route.path.startsWith('/cms/contracts/')
  }
  return route.path.startsWith(path)
}
</script>

<style scoped>
.cms-app {
  min-height: 100vh;
  background: var(--cms-bg);
}

.cms-navbar {
  background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #3730a3 100%);
  color: white;
  padding: 0 32px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 20px rgba(79, 70, 229, 0.3);
}

.cms-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-home {
  color: rgba(255, 255, 255, 0.8);
  text-decoration: none;
  font-size: 18px;
  padding: 4px 8px;
  border-radius: 6px;
}

.back-home:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #818cf8, #6366f1);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.brand-title {
  font-size: 18px;
  font-weight: 700;
}

.cms-nav {
  display: flex;
  gap: 4px;
}

.nav-link {
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
}

.nav-link:hover,
.nav-link.active {
  color: white;
  background: rgba(255, 255, 255, 0.15);
}

.cms-nav-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-name {
  font-size: 13px;
  opacity: 0.85;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #818cf8, #6366f1);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.cms-container {
  max-width: 1440px;
  margin: 0 auto;
  padding: 24px 32px 48px;
}

@media (max-width: 768px) {
  .cms-nav { display: none; }
  .cms-container { padding: 16px; }
}
</style>
