<template>
  <div class="page">
    <h2>角色权限</h2>
    <p class="desc">α版本采用角色 + 部门双维度权限模型。下表为各角色功能权限概览。</p>
    <el-table :data="matrix" stripe border>
      <el-table-column prop="feature" label="功能" width="160" fixed />
      <el-table-column v-for="r in roles" :key="r.id" :label="r.label" min-width="100" align="center">
        <template #default="{ row }">
          <span>{{ row[r.id] || '—' }}</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchRoles } from '@/api/prd'

const roles = ref<Array<{ id: string; label: string }>>([])

const matrix = [
  {
    feature: '工作台',
    system_admin: '✅',
    legal: '✅',
    business: '✅',
    sales: '✅',
    procurement: '✅',
    finance: '✅',
    manager: '✅',
  },
  {
    feature: '合同导入',
    system_admin: '✅',
    legal: '✅',
    business: '❌',
    sales: '❌',
    procurement: '❌',
    finance: '❌',
    manager: '看',
  },
  {
    feature: '合同搜索',
    system_admin: '✅',
    legal: '✅',
    business: '本部门',
    sales: '本部门',
    procurement: '✅',
    finance: '全量',
    manager: '✅',
  },
  {
    feature: '客户中心',
    system_admin: '✅',
    legal: '✅',
    business: '看本',
    sales: '✅',
    procurement: '看',
    finance: '看',
    manager: '看',
  },
  {
    feature: '供应商中心',
    system_admin: '✅',
    legal: '✅',
    business: '看本',
    sales: '❌',
    procurement: '✅',
    finance: '看',
    manager: '看',
  },
  {
    feature: '履约助手',
    system_admin: '✅',
    legal: '全量',
    business: '仅自己',
    sales: '仅自己',
    procurement: '本部门',
    finance: '全量',
    manager: '全量',
  },
  {
    feature: '系统管理',
    system_admin: '✅',
    legal: '❌',
    business: '❌',
    sales: '❌',
    procurement: '❌',
    finance: '❌',
    manager: '❌',
  },
]

onMounted(async () => {
  roles.value = await fetchRoles()
})
</script>

<style scoped>
.page { padding: 24px; }
.desc { color: #64748b; font-size: 14px; margin-bottom: 16px; }
</style>
