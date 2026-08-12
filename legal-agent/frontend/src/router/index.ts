import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { requiresAuth: true, layout: 'home' },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: 'knowledge',
          name: 'knowledge',
          component: () => import('@/views/KnowledgeView.vue'),
        },
        {
          path: 'business-model',
          name: 'business-model',
          component: () => import('@/views/BusinessModelView.vue'),
        },
        {
          path: 'performance',
          name: 'performance',
          component: () => import('@/views/performance/PerformanceOverviewView.vue'),
        },
        {
          path: 'performance/assistant',
          name: 'performance-assistant',
          component: () => import('@/views/performance/PerformanceAssistantView.vue'),
        },
        {
          path: 'performance/suppliers',
          name: 'suppliers',
          component: () => import('@/views/performance/SupplierCenterView.vue'),
        },
        {
          path: 'performance/customers',
          name: 'customers',
          component: () => import('@/views/performance/CustomerCenterView.vue'),
        },
        {
          path: 'performance/orders',
          name: 'orders-sync',
          component: () => import('@/views/performance/OrdersSyncView.vue'),
        },
        {
          path: 'admin/users',
          name: 'admin-users',
          component: () => import('@/views/admin/AdminUsersView.vue'),
        },
        {
          path: 'admin/roles',
          name: 'admin-roles',
          component: () => import('@/views/admin/AdminRolesView.vue'),
        },
        {
          path: 'admin/tags',
          name: 'admin-tags',
          component: () => import('@/views/admin/AdminTagsView.vue'),
        },
        // β预留：起草审核仍可访问，但不在主菜单突出
        {
          path: 'search',
          name: 'search',
          component: () => import('@/views/LegalSearchView.vue'),
        },
        {
          path: 'contract/review',
          name: 'contract-review',
          component: () => import('@/views/ContractReviewView.vue'),
        },
        {
          path: 'contract/draft',
          name: 'contract-draft',
          component: () => import('@/views/ContractDraftView.vue'),
        },
        {
          path: 'contract/compare',
          name: 'contract-compare',
          component: () => import('@/views/ContractCompareView.vue'),
        },
        {
          path: 'qa/labor',
          name: 'qa-labor',
          component: () => import('@/views/LaborLawView.vue'),
        },
        {
          path: 'qa/financial',
          name: 'qa-financial',
          component: () => import('@/views/QaView.vue'),
          props: { module: 'financial', title: '金融合规' },
        },
        {
          path: 'qa/overseas',
          name: 'qa-overseas',
          component: () => import('@/views/QaView.vue'),
          props: { module: 'overseas', title: '企业出海' },
        },
      ],
    },
    {
      path: '/cms',
      component: () => import('@/layouts/CmsLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/cms/ledger' },
        { path: 'ledger', name: 'cms-ledger', component: () => import('@/views/cms/CmsLedgerView.vue') },
        { path: 'import', name: 'cms-import', component: () => import('@/views/cms/CmsImportView.vue') },
        { path: 'search', name: 'cms-search', component: () => import('@/views/cms/CmsSearchView.vue') },
        { path: 'compare', name: 'cms-compare', component: () => import('@/views/cms/CmsCompareView.vue') },
        { path: 'contracts/:id', name: 'cms-detail', component: () => import('@/views/cms/CmsDetailView.vue') },
      ],
    },
  ],
})

router.beforeEach(async (to, _from, next) => {
  const auth = useAuthStore()
  if (to.meta.public) {
    if (auth.token && to.path === '/login') {
      next({ name: 'home' })
      return
    }
    next()
    return
  }
  if (to.meta.requiresAuth && !auth.token) {
    next({ name: 'login', query: { redirect: to.fullPath } })
    return
  }
  if (auth.token && !auth.user) {
    await auth.loadUser()
  }
  next()
})

export default router
