<template>
  <div class="users-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <div class="header-actions">
            <el-button type="success" @click="showImportDialog = true">
              <el-icon><Upload /></el-icon>CSV导入
            </el-button>
            <el-button type="primary" @click="handleAdd">新增用户</el-button>
          </div>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" class="search-form">
        <el-form-item label="用户名">
          <el-input v-model="searchForm.username" placeholder="请输入用户名" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadUsers">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 用户列表 -->
      <el-table :data="users" v-loading="loading" border>
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="full_name" label="姓名" width="120" />
        <el-table-column prop="email" label="邮箱" width="180" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="getRoleType(row.role)">{{ getRoleName(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'danger'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="personal_quota" label="配额" width="100" />
        <el-table-column prop="personal_used" label="已用" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="primary" link @click="handleQuota(row)">配额</el-button>
            <el-button 
              v-if="row.status === 'active'" 
              type="danger" 
              link 
              @click="handleDisable(row)"
            >禁用</el-button>
            <el-button 
              v-else 
              type="success" 
              link 
              @click="handleEnable(row)"
            >启用</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadUsers"
          @current-change="loadUsers"
        />
      </div>
    </el-card>

    <!-- 用户编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="userForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="userForm.username" :disabled="!!userForm.id" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="userForm.full_name" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" />
        </el-form-item>
        <el-form-item v-if="!userForm.id" label="密码">
          <el-input v-model="userForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role">
            <el-option label="员工" value="employee" />
            <el-option label="部门管理员" value="dept_admin" />
            <el-option label="超级管理员" value="super_admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 配额编辑对话框 -->
    <el-dialog v-model="quotaDialogVisible" title="调整配额" width="400px">
      <el-form :model="quotaForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="quotaForm.username" disabled />
        </el-form-item>
        <el-form-item label="配额">
          <el-input-number v-model="quotaForm.personal_quota" :min="0" :max="99999999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="quotaDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitQuota">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usersApi, adminApi } from '../api'

interface User {
  id: string
  username: string
  full_name: string
  email: string
  role: string
  status: string
  personal_quota: number
  personal_used: number
  created_at: string
}

const loading = ref(false)
const users = ref<User[]>([])
const dialogVisible = ref(false)
const quotaDialogVisible = ref(false)
const dialogTitle = ref('')

const searchForm = reactive({
  username: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const userForm = reactive({
  id: '',
  username: '',
  full_name: '',
  email: '',
  password: '',
  role: 'employee'
})

const quotaForm = reactive({
  userId: '',
  username: '',
  personal_quota: 0
})

const getRoleName = (role: string) => {
  const roleMap: Record<string, string> = {
    super_admin: '超级管理员',
    dept_admin: '部门管理员',
    employee: '员工'
  }
  return roleMap[role] || role
}

const getRoleType = (role: string) => {
  const typeMap: Record<string, string> = {
    super_admin: 'danger',
    dept_admin: 'warning',
    employee: 'info'
  }
  return typeMap[role] || 'info'
}

const loadUsers = async () => {
  loading.value = true
  try {
    const res: any = await usersApi.list({
      page: pagination.page,
      page_size: pagination.pageSize
    })
    users.value = res || []
    pagination.total = (res || []).length
  } catch (error: any) {
    ElMessage.error(error.message || '加载用户列表失败')
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.username = ''
  loadUsers()
}

const handleAdd = () => {
  dialogTitle.value = '新增用户'
  Object.assign(userForm, {
    id: '',
    username: '',
    full_name: '',
    email: '',
    password: '',
    role: 'employee'
  })
  dialogVisible.value = true
}

const handleEdit = (row: User) => {
  dialogTitle.value = '编辑用户'
  Object.assign(userForm, {
    id: row.id,
    username: row.username,
    full_name: row.full_name,
    email: row.email,
    password: '',
    role: row.role
  })
  dialogVisible.value = true
}

const handleQuota = (row: User) => {
  quotaForm.userId = row.id
  quotaForm.username = row.username
  quotaForm.personal_quota = row.personal_quota
  quotaDialogVisible.value = true
}

const submitForm = async () => {
  try {
    if (userForm.id) {
      await usersApi.update(userForm.id, {
        full_name: userForm.full_name,
        email: userForm.email
      })
      ElMessage.success('更新成功')
    } else {
      await adminApi.createUser({
        username: userForm.username,
        email: userForm.email,
        password: userForm.password,
        full_name: userForm.full_name,
        role: userForm.role
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadUsers()
  } catch (error: any) {
    ElMessage.error(error.message || '操作失败')
  }
}

const submitQuota = async () => {
  try {
    await usersApi.updateQuota(quotaForm.userId, {
      personal_quota: quotaForm.personal_quota
    })
    ElMessage.success('配额更新成功')
    quotaDialogVisible.value = false
    loadUsers()
  } catch (error: any) {
    ElMessage.error(error.message || '操作失败')
  }
}

const handleDisable = async (row: User) => {
  try {
    await ElMessageBox.confirm('确定要禁用该用户吗？', '提示', {
      type: 'warning'
    })
    await usersApi.disable(row.id)
    ElMessage.success('禁用成功')
    loadUsers()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '操作失败')
    }
  }
}

const handleEnable = async (row: User) => {
  try {
    await usersApi.enable(row.id)
    ElMessage.success('启用成功')
    loadUsers()
  } catch (error: any) {
    ElMessage.error(error.message || '操作失败')
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.users-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>