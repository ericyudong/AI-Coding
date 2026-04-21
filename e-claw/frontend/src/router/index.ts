import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('@/views/Tasks.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('@/views/Knowledge.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/tenants',
    name: 'Tenants',
    component: () => import('@/views/Tenants.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/users',
    name: 'Users',
    component: () => import('@/views/Users.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/audit',
    name: 'Audit',
    component: () => import('@/views/Audit.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/ops',
    name: 'Ops',
    component: () => import('@/views/ops/Ops.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/ops/service-config',
    name: 'ServiceConfig',
    component: () => import('@/views/ops/ServiceConfig.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/ops/monitor',
    name: 'Monitor',
    component: () => import('@/views/ops/Monitor.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/ops/logs',
    name: 'Logs',
    component: () => import('@/views/ops/Logs.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/ai-gateway',
    name: 'AIGateway',
    component: () => import('@/views/AIGateway.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/instances',
    name: 'Instances',
    component: () => import('@/views/Instances.vue'),
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const userStr = localStorage.getItem('user')
  const user = userStr ? JSON.parse(userStr) : null
  
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.meta.requiresAdmin && user) {
    // 只有超级管理员和部门管理员可以访问admin页面
    if (user.role !== 'super_admin' && user.role !== 'dept_admin') {
      next('/dashboard')
    } else {
      next()
    }
  } else if (to.meta.requiresSuperAdmin && user) {
    // 只有超级管理员可以访问
    if (user.role !== 'super_admin') {
      next('/dashboard')
    } else {
      next()
    }
  } else if (to.meta.requiresDeptAdmin && user) {
    // 部门管理员和超级管理员可以访问
    if (user.role !== 'super_admin' && user.role !== 'dept_admin') {
      next('/dashboard')
    } else {
      next()
    }
  } else if (to.meta.requiresOps && user) {
    // 只有运维人员可以访问
    if (user.role !== 'ops' && user.role !== 'super_admin') {
      next('/dashboard')
    } else {
      next()
    }
  } else if (to.path === '/login' && token) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router