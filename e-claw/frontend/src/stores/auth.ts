import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface User {
  id: string
  username: string
  email: string
  full_name: string
  role: string
  tenant_id?: string
  personal_quota: number
  personal_used: number
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string>('')

  // Initialize from localStorage
  const initAuth = () => {
    const storedToken = localStorage.getItem('token')
    const storedUser = localStorage.getItem('user')
    if (storedToken && storedUser) {
      token.value = storedToken
      user.value = JSON.parse(storedUser)
    }
  }

  const setAuth = (newToken: string, newUser: User) => {
    token.value = newToken
    user.value = newUser
    localStorage.setItem('token', newToken)
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  const clearAuth = () => {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  const isAdmin = computed(() => {
    return user.value?.role === 'super_admin' || user.value?.role === 'dept_admin'
  })

  const isSuperAdmin = computed(() => {
    return user.value?.role === 'super_admin'
  })

  const isDeptAdmin = computed(() => {
    return user.value?.role === 'dept_admin'
  })

  const isEmployee = computed(() => {
    return user.value?.role === 'employee'
  })

  const isOps = computed(() => {
    return user.value?.role === 'ops'
  })

  const availableQuota = computed(() => {
    if (!user.value) return 0
    return user.value.personal_quota - user.value.personal_used
  })

  // Initialize on store creation
  initAuth()

  return {
    user,
    token,
    setAuth,
    clearAuth,
    isAdmin,
    isSuperAdmin,
    isDeptAdmin,
    isEmployee,
    isOps,
    availableQuota
  }
})