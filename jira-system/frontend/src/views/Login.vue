<template>
  <div class="login-container">
    <Card class="login-card">
      <template #title>JIRA System</template>
      <template #subtitle>Sign in to your account</template>
      <template #content>
        <div class="form-field">
          <label for="username">Username</label>
          <InputText id="username" v-model="username" class="w-full" />
        </div>
        <div class="form-field">
          <label for="password">Password</label>
          <Password id="password" v-model="password" class="w-full" :feedback="false" toggleMask />
        </div>
        <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
      </template>
      <template #footer>
        <div class="actions">
          <Button label="Sign In" icon="pi pi-sign-in" @click="handleLogin" :loading="loading" class="w-full" />
        </div>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
  if (!username.value || !password.value) {
    error.value = 'Please enter username and password'
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    await authStore.login(username.value, password.value)
    router.push('/projects')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f5f7fa;
}

.login-card {
  width: 400px;
}

.form-field {
  margin-bottom: 1rem;
}

.form-field label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.w-full {
  width: 100%;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>