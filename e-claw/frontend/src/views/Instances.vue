<template>
  <div class="instances-container">
    <el-card class="header-card">
      <div class="header-actions">
        <h2>OpenCLAW 实例管理</h2>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          创建实例
        </el-button>
      </div>
    </el-card>

    <!-- 镜像模板选择 -->
    <el-card class="templates-card">
      <template #header>
        <span>可用镜像模板</span>
      </template>
      <el-row :gutter="16">
        <el-col :span="6" v-for="template in imageTemplates" :key="template.id">
          <el-card class="template-card" :class="{ 'template-disabled': !template.is_enabled }">
            <template #header>
              <div class="template-header">
                <span>{{ template.name }}</span>
                <el-tag :type="template.is_enabled ? 'success' : 'info'" size="small">
                  {{ template.is_enabled ? '可用' : '禁用' }}
                </el-tag>
              </div>
            </template>
            <p class="template-desc">{{ template.description }}</p>
            <p class="template-image">{{ template.image }}</p>
            <p class="template-port">端口: {{ template.default_port }}</p>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <!-- 实例列表 -->
    <el-card class="instances-card">
      <template #header>
        <div class="card-header">
          <span>我的实例</span>
          <el-input
            v-model="searchKeyword"
            placeholder="搜索实例名称"
            style="width: 200px"
            clearable
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </template>
      
      <el-table :data="filteredInstances" v-loading="loading">
        <el-table-column prop="name" label="实例名称" min-width="150" />
        <el-table-column prop="instance_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ getInstanceTypeName(row.instance_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="docker_url" label="访问地址" min-width="180" />
        <el-table-column prop="docker_port" label="端口" width="80" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button 
              v-if="row.status === 'stopped' || row.status === 'pending'"
              type="success" 
              size="small" 
              @click="handleStart(row)"
            >
              启动
            </el-button>
            <el-button 
              v-if="row.status === 'running'"
              type="warning" 
              size="small" 
              @click="handleStop(row)"
            >
              停止
            </el-button>
            <el-button 
              type="danger" 
              size="small" 
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>

    <!-- 创建实例对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建 OpenCLAW 实例"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="createForm" label-width="120px" ref="createFormRef">
        <el-form-item label="实例名称" prop="name" required>
          <el-input v-model="createForm.name" placeholder="输入实例名称" />
        </el-form-item>
        
        <el-form-item label="描述" prop="description">
          <el-input v-model="createForm.description" type="textarea" rows="2" />
        </el-form-item>
        
        <el-form-item label="实例类型" prop="instance_type" required>
          <el-select v-model="createForm.instance_type" placeholder="选择实例类型">
            <el-option
              v-for="t in enabledTemplates"
              :key="t.id"
              :label="t.name"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="CPU核心数" prop="cpu_cores">
              <el-input-number v-model="createForm.cpu_cores" :min="1" :max="32" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="内存(GB)" prop="memory_gb">
              <el-input-number v-model="createForm.memory_gb" :min="1" :max="128" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="磁盘(GB)" prop="disk_gb">
              <el-input-number v-model="createForm.disk_gb" :min="10" :max="1000" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="GPU数量" prop="gpu_count">
              <el-input-number v-model="createForm.gpu_count" :min="0" :max="4" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="启用GPU" prop="gpu_enabled">
          <el-switch v-model="createForm.gpu_enabled" />
        </el-form-item>
        
        <el-form-item label="自定义镜像" prop="image_registry">
          <el-input v-model="createForm.image_registry" placeholder="可选：自定义镜像仓库地址" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { instancesApi } from '@/api'

// 数据
const loading = ref(false)
const creating = ref(false)
const instances = ref<any[]>([])
const imageTemplates = ref<any[]>([])
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showCreateDialog = ref(false)

// 创建表单
const createForm = ref({
  name: '',
  description: '',
  instance_type: 'openclaw',
  cpu_cores: 2,
  memory_gb: 4,
  disk_gb: 20,
  gpu_enabled: false,
  gpu_count: 0,
  image_registry: ''
})

// 计算属性
const filteredInstances = computed(() => {
  if (!searchKeyword.value) return instances.value
  return instances.value.filter(i => 
    i.name.toLowerCase().includes(searchKeyword.value.toLowerCase())
  )
})

const enabledTemplates = computed(() => {
  return imageTemplates.value.filter(t => t.is_enabled)
})

// 方法
const getInstanceTypeName = (type: string) => {
  const names: Record<string, string> = {
    openclaw: 'OpenCLAW',
    ubuntu: 'Ubuntu',
    webtop: 'Webtop',
    debian: 'Debian',
    centos: 'CentOS',
    custom: '自定义'
  }
  return names[type] || type
}

const getStatusType = (status: string) => {
  const types: Record<string, string> = {
    running: 'success',
    creating: 'warning',
    stopped: 'info',
    pending: 'info',
    failed: 'danger'
  }
  return types[status] || 'info'
}

const getStatusName = (status: string) => {
  const names: Record<string, string> = {
    running: '运行中',
    creating: '创建中',
    stopped: '已停止',
    pending: '排队中',
    failed: '失败'
  }
  return names[status] || status
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const loadInstances = async () => {
  loading.value = true
  try {
    const res = await instancesApi.list({
      page: currentPage.value,
      page_size: pageSize.value
    })
    instances.value = res.items || []
    total.value = res.total || 0
  } catch (e) {
    console.error('Failed to load instances:', e)
  } finally {
    loading.value = false
  }
}

const loadImageTemplates = async () => {
  try {
    const res = await instancesApi.getImageTemplates()
    imageTemplates.value = res || []
  } catch (e) {
    console.error('Failed to load image templates:', e)
  }
}

const handleCreate = async () => {
  if (!createForm.value.name) {
    ElMessage.warning('请输入实例名称')
    return
  }
  
  creating.value = true
  try {
    await instancesApi.create(createForm.value)
    ElMessage.success('实例创建成功')
    showCreateDialog.value = false
    loadInstances()
    
    // 重置表单
    createForm.value = {
      name: '',
      description: '',
      instance_type: 'openclaw',
      cpu_cores: 2,
      memory_gb: 4,
      disk_gb: 20,
      gpu_enabled: false,
      gpu_count: 0,
      image_registry: ''
    }
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

const handleStart = async (row: any) => {
  try {
    await instancesApi.start(row.id)
    ElMessage.success('实例已启动')
    loadInstances()
  } catch (e: any) {
    ElMessage.error(e.message || '启动失败')
  }
}

const handleStop = async (row: any) => {
  try {
    await instancesApi.stop(row.id)
    ElMessage.success('实例已停止')
    loadInstances()
  } catch (e: any) {
    ElMessage.error(e.message || '停止失败')
  }
}

const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm('确定要删除此实例吗？', '警告', {
      type: 'warning'
    })
    
    await instancesApi.delete(row.id)
    ElMessage.success('实例已删除')
    loadInstances()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  loadInstances()
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  loadInstances()
}

// 生命周期
onMounted(() => {
  loadInstances()
  loadImageTemplates()
})
</script>

<style scoped>
.instances-container {
  padding: 20px;
}

.header-card {
  margin-bottom: 20px;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions h2 {
  margin: 0;
}

.templates-card {
  margin-bottom: 20px;
}

.template-card {
  margin-bottom: 16px;
}

.template-card.template-disabled {
  opacity: 0.6;
}

.template-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.template-desc {
  font-size: 12px;
  color: #666;
  margin: 8px 0;
}

.template-image {
  font-size: 11px;
  color: #999;
  word-break: break-all;
}

.template-port {
  font-size: 12px;
  color: #666;
  margin-top: 8px;
}

.instances-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>