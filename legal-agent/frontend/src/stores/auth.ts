import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchMe, login as apiLogin, type UserInfo } from '@/api/legal'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('legal_agent_token') || '')
  const user = ref<UserInfo | null>(null)
  const loading = ref(false)

  async function login(username: string, password: string) {
    loading.value = true
    try {
      const data = await apiLogin(username, password)
      token.value = data.access_token
      localStorage.setItem('legal_agent_token', data.access_token)
      user.value = await fetchMe()
    } finally {
      loading.value = false
    }
  }

  async function loadUser() {
    if (!token.value) return
    try {
      user.value = await fetchMe()
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('legal_agent_token')
  }

  return { token, user, loading, login, loadUser, logout }
})
