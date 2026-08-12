<template>
  <div class="app-layout">
    <AppHeader :subtitle="AI_NAME" />
    <div class="layout-body">
      <aside class="sidebar">
        <nav class="sidebar-nav">
          <div v-for="group in visibleNav" :key="group.label" class="nav-group">
            <div class="nav-group-title">
              <span class="nav-icon">{{ navIcon(group.icon) }}</span>
              {{ group.label }}
            </div>
            <RouterLink
              v-for="child in group.children"
              :key="child.route"
              :to="child.route"
              class="nav-item"
              :class="{ active: isActive(child.route), reserved: child.reserved }"
            >
              {{ child.label }}
              <span v-if="child.reserved" class="badge">预留</span>
            </RouterLink>
          </div>
        </nav>
      </aside>
      <main class="main-content">
        <RouterView />
      </main>
    </div>
    <RightToolbar />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'
import RightToolbar from '@/components/RightToolbar.vue'
import { AI_NAME } from '@/constants/brand'
import { SIDEBAR_NAV } from '@/constants/navigation'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()

const visibleNav = computed(() => {
  const features = new Set(auth.user?.features || [])
  const isAdmin = features.has('system_admin')
  return SIDEBAR_NAV.map((group) => ({
    ...group,
    children: (group.children || []).filter((child) => {
      if (child.reserved) return true
      if (!child.feature) return true
      if (isAdmin) return true
      return features.has(child.feature)
    }),
  })).filter((g) => (g.children || []).length > 0)
})

function navIcon(name: string) {
  const map: Record<string, string> = {
    knowledge: '💡',
    contract: '📄',
    performance: '⏱',
    business: '📊',
    admin: '⚙',
  }
  return map[name] || '•'
}

function isActive(path: string) {
  const [pathname] = path.split('?')
  return route.path === pathname || route.path.startsWith(pathname + '/')
}
</script>

<style scoped>
.app-layout {
  min-height: 100vh;
  background: var(--brand-bg);
}

.layout-body {
  display: flex;
  min-height: calc(100vh - var(--header-height));
}

.sidebar {
  width: var(--sidebar-width);
  background: #fff;
  border-right: 1px solid #e8ecf0;
  padding: 16px 0;
  display: flex;
  flex-direction: column;
}

.nav-group {
  margin-bottom: 8px;
}

.nav-group-title {
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-text);
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px 8px 44px;
  font-size: 13px;
  color: var(--brand-muted);
  border-left: 3px solid transparent;
  text-decoration: none;
}

.nav-item.active {
  color: var(--brand-primary, #00838f);
  background: rgba(0, 131, 143, 0.06);
  border-left-color: var(--brand-primary, #00838f);
}

.nav-item.reserved {
  opacity: 0.7;
}

.badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: #f1f5f9;
  color: #64748b;
}

.main-content {
  flex: 1;
  min-width: 0;
}
</style>
