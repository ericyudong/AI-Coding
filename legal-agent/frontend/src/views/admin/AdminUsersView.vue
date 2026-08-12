<template>
  <div class="page">
    <div class="head">
      <h2>用户管理</h2>
      <el-button type="primary" @click="showCreate = true">新增用户</el-button>
    </div>

    <el-table v-loading="loading" :data="users" stripe>
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="display_name" label="姓名" width="120" />
      <el-table-column prop="email" label="邮箱" min-width="160" />
      <el-table-column label="角色" width="120">
        <template #default="{ row }">{{ roleLabel(row.role) }}</template>
      </el-table-column>
      <el-table-column prop="department_name" label="部门" width="120" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="toggleActive(row)">
            {{ row.is_active ? '禁用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" title="新增用户" width="480px">
      <el-form label-width="90px">
        <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" type="password" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.display_name" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width: 100%">
            <el-option v-for="r in roles" :key="r.id" :label="r.label" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门">
          <el-select v-model="form.department_id" clearable style="width: 100%">
            <el-option v-for="d in depts" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createAdminUser,
  fetchAdminUsers,
  fetchDepartments,
  fetchRoles,
  updateAdminUser,
  type AdminUser,
} from '@/api/prd'

const loading = ref(false)
const users = ref<AdminUser[]>([])
const roles = ref<Array<{ id: string; label: string }>>([])
const depts = ref<Array<{ id: number; name: string }>>([])
const showCreate = ref(false)
const form = reactive({
  username: '',
  password: '',
  display_name: '',
  role: 'legal',
  department_id: undefined as number | undefined,
})

function roleLabel(id: string) {
  return roles.value.find((r) => r.id === id)?.label || id
}

async function load() {
  loading.value = true
  try {
    ;[users.value, roles.value, depts.value] = await Promise.all([
      fetchAdminUsers(),
      fetchRoles(),
      fetchDepartments(),
    ])
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '无权限或加载失败')
  } finally {
    loading.value = false
  }
}

async function create() {
  try {
    await createAdminUser({ ...form })
    ElMessage.success('已创建')
    showCreate.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  }
}

async function toggleActive(row: AdminUser) {
  await updateAdminUser(row.id, { is_active: !row.is_active })
  await load()
}

onMounted(load)
</script>

<style scoped>
.page { padding: 24px; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
</style>
