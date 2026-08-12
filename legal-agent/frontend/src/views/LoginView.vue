<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <span class="logo">益</span>
        <h1>{{ PRODUCT_NAME }}</h1>
        <p>智能法务 Agent 平台</p>
      </div>
      <el-form @submit.prevent="onSubmit">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" size="large" show-password />
        </el-form-item>
        <el-button type="primary" native-type="submit" size="large" class="submit-btn" :loading="auth.loading">
          登录
        </el-button>
      </el-form>
      <p class="hint">默认账号：admin / admin123</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { PRODUCT_NAME } from '@/constants/brand'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const username = ref('admin')
const password = ref('admin123')

async function onSubmit() {
  try {
    await auth.login(username.value, password.value)
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch {
    ElMessage.error('登录失败，请检查用户名和密码')
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #006064 0%, #00838f 50%, #26a69a 100%);
}

.login-card {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.login-brand {
  text-align: center;
  margin-bottom: 32px;
}

.logo {
  display: inline-flex;
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
  color: #fff;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 12px;
}

.login-brand h1 {
  margin: 0 0 8px;
  font-size: 20px;
}

.login-brand p {
  margin: 0;
  color: var(--brand-muted);
  font-size: 14px;
}

.submit-btn {
  width: 100%;
  background: var(--brand-primary);
  border-color: var(--brand-primary);
}

.hint {
  margin-top: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--brand-muted);
}
</style>
