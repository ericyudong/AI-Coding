<template>
  <div class="app-container">
    <Menubar :model="menuItems" v-if="authStore.isAuthenticated">
      <template #start>
        <span class="app-title">JIRA System</span>
      </template>
      <template #end>
        <span class="user-info">{{ authStore.user?.username }}</span>
        <Button label="Logout" icon="pi pi-sign-out" @click="logout" text />
      </template>
    </Menubar>
    
    <div class="main-content">
      <router-view />
    </div>
    
    <Toast />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import Menubar from 'primevue/menubar'
import Button from 'primevue/button'
import Toast from 'primevue/toast'

const router = useRouter()
const authStore = useAuthStore()

const menuItems = computed(() => [
  { label: 'Projects', icon: 'pi pi-folder', command: () => router.push('/projects') },
  { label: 'My Issues', icon: 'pi pi-list', command: () => router.push('/my-issues') },
])

const logout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.app-container {
  min-height: 100vh;
  background: #f5f7fa;
}

.app-title {
  font-weight: 600;
  font-size: 1.2rem;
  margin-right: 2rem;
}

.main-content {
  padding: 1rem;
}

.user-info {
  margin-right: 1rem;
  color: #666;
}
</style>