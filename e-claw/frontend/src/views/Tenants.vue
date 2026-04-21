<template>
  <div class="tenants-page">
    <!-- Header -->
    <div class="page-header">
      <h2>租户管理</h2>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>创建租户
      </el-button>
    </div>

    <!-- Filters -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="全部" value="" />
            <el-option label="活跃" value="active" />
            <el-option label="禁用" value="disabled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTenants">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Tenant List -->
    <el-card class="table-card">
      <el-table :data="tenants" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="code" label="代码" width="120" />
        <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '活跃' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_quota" label="总配额" width="100">
          <template #default="{ row }">
            {{ formatNumber(row.total_quota) }}
          </template>
        </el-table-column>
        <el-table-column prop="used_quota" label="已用配额" width="100">
          <template #default="{ row }">
            {{ formatNumber(row.used_quota) }}
          </template>
        </el-table-column>
        <el-table-column prop="user_count" label="用户数" width="80" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewTenant(row)">详情</el-button>
            <el-button type="warning" link @click="editTenant(row)">编辑</el-button>
            <el-button 
              :type="row.status === 'active' ? 'danger' : 'success'" 
              link 
              @click="toggleStatus(row)"
            >
              {{ row.status === 'active' ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadTenants"
          @current-change="loadTenants"
        />
      </div>
    </el-card>

    <!-- Create/Edit Tenant Dialog -->
    <el-dialog v-model="showCreateDialog" :title="isEdit ? '编辑租户' : '创建租户'" width="500px">
      <el-form :model="tenantForm" :rules="tenantRules" ref="tenantFormRef" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="tenantForm.name" placeholder="请输入租户名称" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="代码" prop="code">
          <el-input v-model="tenantForm.code" placeholder="请输入租户代码" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="tenantForm.description" type="textarea" rows="3" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="总配额" prop="total_quota">
          <el-input-number v-model="tenantForm.total_quota" :min="0" :step="100000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态" v-if="isEdit">
          <el-radio-group v-model="tenantForm.status">
            <el-radio value="active">活跃</el-radio>
            <el-radio value="disabled">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveTenant">保存</el-button>
      </template>
    </el-dialog>

    <!-- Tenant Detail Dialog -->
    <el-dialog v-model="showDetailDialog" title="租户详情" width="600px">
      <el-descriptions :column="2" border v-if="currentTenant">
        <el-descriptions-item label="名称">{{ currentTenant.name }}</el-descriptions-item>
        <el-descriptions-item label="代码">{{ currentTenant.code }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="currentTenant.status === 'active' ? 'success' : 'info'">
            {{ currentTenant.status === 'active' ? '活跃' : '禁用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="用户数">{{ currentTenant.user_count }}</el-descriptions-item>
        <el-descriptions-item label="总配额">{{ formatNumber(currentTenant.total_quota) }}</el-descriptions-item>
        <el-descriptions-item label="已用配额">{{ formatNumber(currentTenant.used_quota) }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(currentTenant.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ currentTenant.description || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { adminApi } from '@/api'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

const loading = ref(false)
const submitting = ref(false)
const tenants = ref<any[]>([])
const total = ref(0)
const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const isEdit = ref(false)
const currentTenant = ref<any>(null)
const tenantFormRef = ref<FormInstance>()

const filters = reactive({
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20
})

const tenantForm = reactive({
  name: '',
  code: '',
  description: '',
  total_quota: 1000000,
  status: 'active'
})

const tenantRules = {
  name: [{ required: true, message: '请输入租户名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入租户代码', trigger: 'blur' }],
  total_quota: [{ required: true, message: '请输入总配额', trigger: 'blur' }]
}

const formatNumber = (num: number) => {
  if (!num) return '0'
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toString()
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const loadTenants = async () => {
  loading.value = true
  try {
    const data = await adminApi.listTenants({
      status: filters.status || undefined,
      page: pagination.page,
      page_size: pagination.pageSize
    })
    tenants.value = data
    total.value = data.length
  } catch (error) {
    console.error('Failed to load tenants:', error)
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.status = ''
  pagination.page = 1
  loadTenants()
}

const viewTenant = async (row: any) => {
  try {
    const data = await adminApi.getTenant(row.id)
    currentTenant.value = data
    showDetailDialog.value = true
  } catch (error) {
    ElMessage.error('获取租户详情失败')
  }
}

const editTenant = (row: any) => {
  isEdit.value = true
  tenantForm.name = row.name
  tenantForm.code = row.code
  tenantForm.description = row.description || ''
  tenantForm.total_quota = row.total_quota
  tenantForm.status = row.status
  currentTenant.value = row
  showCreateDialog.value = true
}

const saveTenant = async () => {
  if (!tenantFormRef.value) return
  
  await tenantFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    submitting.value = true
    try {
      if (isEdit.value) {
        await adminApi.updateTenant(currentTenant.value.id, {
          name: tenantForm.name,
          description: tenantForm.description,
          total_quota: tenantForm.total_quota,
          status: tenantForm.status
        })
        ElMessage.success('租户更新成功')
      } else {
        await adminApi.createTenant(tenantForm)
        ElMessage.success('租户创建成功')
      }
      showCreateDialog.value = false
      resetTenantForm()
      loadTenants()
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || '操作失败')
    } finally {
      submitting.value = false
    }
  })
}

const resetTenantForm = () => {
  tenantForm.name = ''
  tenantForm.code = ''
  tenantForm.description = ''
  tenantForm.total_quota = 1000000
  tenantForm.status = 'active'
  isEdit.value = false
  currentTenant.value = null
}

const toggleStatus = async (row: any) => {
  const action = row.status === 'active' ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确认要${action}该租户吗?`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const newStatus = row.status === 'active' ? 'disabled' : 'active'
    await adminApi.updateTenant(row.id, { status: newStatus })
    ElMessage.success(`租户已${action}`)
    loadTenants()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '操作失败')
    }
  }
}

onMounted(() => {
  loadTenants()
})
</script>

<style scoped>
.tenants-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  color: #303133;
}

.filter-card {
  margin-bottom: 20px;
}

.table-card {
  margin-bottom: 20px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>