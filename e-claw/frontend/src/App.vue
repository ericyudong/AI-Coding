<template>
  <div id="app">
    <el-container v-if="isLoggedIn" class="layout-container">
      <!-- Sidebar -->
      <el-aside width="220px">
        <div class="logo">
          <h3>E-Claw</h3>
        </div>
        <el-menu
          :default-active="activeMenu"
          router
          class="sidebar-menu"
          background-color="#304156"
          text-color="#bfcbd9"
          active-text-color="#409eff"
        >
          <!-- 员工：显示仪表盘、任务管理、知识库、实例管理 -->
          <template v-if="authStore.isEmployee">
            <el-menu-item index="/dashboard">
              <el-icon><HomeFilled /></el-icon>
              <span>仪表盘</span>
            </el-menu-item>
            <el-menu-item index="/tasks">
              <el-icon><Operation /></el-icon>
              <span>任务管理</span>
            </el-menu-item>
            <el-menu-item index="/knowledge">
              <el-icon><Document /></el-icon>
              <span>知识库</span>
            </el-menu-item>
            <el-menu-item index="/instances">
              <el-icon><Monitor /></el-icon>
              <span>实例管理</span>
            </el-menu-item>
          </template>

          <!-- 部门管理员：显示除租户管理外的所有功能 -->
          <template v-else-if="authStore.isDeptAdmin">
            <el-menu-item index="/dashboard">
              <el-icon><HomeFilled /></el-icon>
              <span>仪表盘</span>
            </el-menu-item>
            <el-menu-item index="/tasks">
              <el-icon><Operation /></el-icon>
              <span>任务管理</span>
            </el-menu-item>
            <el-menu-item index="/knowledge">
              <el-icon><Document /></el-icon>
              <span>知识库</span>
            </el-menu-item>
            <el-menu-item index="/instances">
              <el-icon><Monitor /></el-icon>
              <span>实例管理</span>
            </el-menu-item>
            <el-menu-item index="/ai-gateway">
              <el-icon><Connection /></el-icon>
              <span>AI Gateway</span>
            </el-menu-item>
            <el-menu-item index="/users">
              <el-icon><User /></el-icon>
              <span>用户管理</span>
            </el-menu-item>
            <el-menu-item index="/audit">
              <el-icon><List /></el-icon>
              <span>审计日志</span>
            </el-menu-item>
            <el-menu-item index="/ops">
              <el-icon><Setting /></el-icon>
              <span>系统配置</span>
            </el-menu-item>
          </template>

          <!-- 超级管理员：显示所有功能 -->
          <template v-else-if="authStore.isSuperAdmin">
            <el-menu-item index="/dashboard">
              <el-icon><HomeFilled /></el-icon>
              <span>仪表盘</span>
            </el-menu-item>
            <el-menu-item index="/tasks">
              <el-icon><Operation /></el-icon>
              <span>任务管理</span>
            </el-menu-item>
            <el-menu-item index="/knowledge">
              <el-icon><Document /></el-icon>
              <span>知识库</span>
            </el-menu-item>
            <el-menu-item index="/instances">
              <el-icon><Monitor /></el-icon>
              <span>实例管理</span>
            </el-menu-item>
            <el-menu-item index="/ai-gateway">
              <el-icon><Connection /></el-icon>
              <span>AI Gateway</span>
            </el-menu-item>
            <el-menu-item index="/users">
              <el-icon><User /></el-icon>
              <span>用户管理</span>
            </el-menu-item>
            <el-menu-item index="/tenants">
              <el-icon><OfficeBuilding /></el-icon>
              <span>租户管理</span>
            </el-menu-item>
            <el-menu-item index="/audit">
              <el-icon><List /></el-icon>
              <span>审计日志</span>
            </el-menu-item>
            <el-menu-item index="/ops">
              <el-icon><Setting /></el-icon>
              <span>系统配置</span>
            </el-menu-item>
          </template>

          <!-- 运维人员：显示系统配置相关功能 -->
          <template v-else-if="authStore.isOps">
            <el-menu-item index="/dashboard">
              <el-icon><HomeFilled /></el-icon>
              <span>仪表盘</span>
            </el-menu-item>
            <el-menu-item index="/ops">
              <el-icon><Setting /></el-icon>
              <span>系统配置</span>
            </el-menu-item>
          </template>

          <!-- 默认：显示基础功能 -->
          <template v-else>
            <el-menu-item index="/dashboard">
              <el-icon><HomeFilled /></el-icon>
              <span>仪表盘</span>
            </el-menu-item>
            <el-menu-item index="/tasks">
              <el-icon><Operation /></el-icon>
              <span>任务管理</span>
            </el-menu-item>
            <el-menu-item index="/knowledge">
              <el-icon><Document /></el-icon>
              <span>知识库</span>
            </el-menu-item>
          </template>
        </el-menu>
      </el-aside>

      <!-- Main Content -->
      <el-container>
        <el-header>
          <div class="header-content">
            <div class="header-left">
              <span class="page-title">{{ pageTitle }}</span>
            </div>
            <div class="header-right">
              <el-dropdown @command="handleCommand">
                <span class="user-info">
                  <el-icon><User /></el-icon>
                  <span>{{ authStore.user?.full_name || authStore.user?.username }}</span>
                </span>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                    <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </el-header>
        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
    
    <!-- Login page doesn't have sidebar -->
    <router-view v-else />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api'
import { ElMessage } from 'element-plus'
import { 
  HomeFilled, 
  Operation, 
  Document, 
  User, 
  OfficeBuilding, 
  List, 
  Setting,
  Monitor,
  Connection
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const isLoggedIn = computed(() => {
  return !!localStorage.getItem('token')
})

const activeMenu = computed(() => {
  return route.path
})

const pageTitle = computed(() => {
  const titleMap: Record<string, string> = {
    '/dashboard': '仪表盘',
    '/tasks': '任务管理',
    '/knowledge': '知识库',
    '/tenants': '租户管理',
    '/users': '用户管理',
    '/audit': '审计日志',
    '/ops': '系统配置',
    '/ops/service-config': '服务配置'
  }
  return titleMap[route.path] || 'E-Claw'
})

const handleCommand = async (command: string) => {
  if (command === 'logout') {
    try {
      await authApi.logout()
    } catch (error) {
      // Ignore logout API errors
    }
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    ElMessage.success('已退出登录')
    // 使用 window.location 强制刷新页面，确保完全退出到登录页
    window.location.href = '/login'
  } else if (command === 'profile') {
    ElMessage.info('个人中心功能开发中')
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  min-height: 100vh;
}

.layout-container {
  min-height: 100vh;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #2b3a4a;
}

.logo h3 {
  color: #fff;
  font-size: 20px;
}

.sidebar-menu {
  border-right: none;
  height: calc(100vh - 60px);
}

.el-header {
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  padding: 0 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.page-title {
  font-size: 18px;
  font-weight: 500;
  color: #303133;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 4px;
  transition: background 0.3s;
}

.user-info:hover {
  background: #f5f7fa;
}

.el-main {
  background: #f5f7fa;
  padding: 20px;
}
</style>