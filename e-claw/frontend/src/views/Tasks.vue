<template>
  <div class="tasks-page">
    <!-- Header -->
    <div class="page-header">
      <h2>任务管理</h2>
      <div class="header-actions">
        <el-button 
          type="danger" 
          :disabled="!selectedTasks.length"
          @click="batchCancelTasks"
        >
          批量取消
        </el-button>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>提交任务
        </el-button>
      </div>
    </div>

    <!-- Filters -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="全部" value="" />
            <el-option label="等待中" value="pending" />
            <el-option label="运行中" value="running" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTasks">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Task List -->
    <el-card class="table-card">
      <el-table 
        :data="tasks" 
        v-loading="loading" 
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="name" label="任务名称" min-width="150" />
        <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
        <el-table-column prop="task_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ getTaskTypeLabel(row.task_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)">{{ getPriorityLabel(row.priority) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :color="getProgressColor(row.status)" />
          </template>
        </el-table-column>
        <el-table-column prop="input_tokens" label="输入Token" width="100">
          <template #default="{ row }">
            {{ formatNumber(row.input_tokens) }}
          </template>
        </el-table-column>
        <el-table-column prop="output_tokens" label="输出Token" width="100">
          <template #default="{ row }">
            {{ formatNumber(row.output_tokens) }}
          </template>
        </el-table-column>
        <el-table-column prop="submit_time" label="提交时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.submit_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewTask(row)">详情</el-button>
            <el-button 
              type="success" 
              link 
              @click="resumeTask(row)" 
              v-if="row.status === 'failed' && row.checkpoint_data"
            >续跑</el-button>
            <el-button 
              type="danger" 
              link 
              @click="cancelTask(row)" 
              v-if="canCancel(row.status)"
            >取消</el-button>
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
          @size-change="loadTasks"
          @current-change="loadTasks"
        />
      </div>
    </el-card>

    <!-- Create Task Dialog -->
    <el-dialog v-model="showCreateDialog" title="提交任务" width="600px">
      <el-form :model="taskForm" :rules="taskRules" ref="taskFormRef" label-width="100px">
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="taskForm.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="任务类型" prop="task_type">
          <el-select v-model="taskForm.task_type" placeholder="请选择任务类型" style="width: 100%">
            <el-option label="通用任务" value="general" />
            <el-option label="文档处理" value="document_process" />
            <el-option label="数据分析" value="data_analysis" />
            <el-option label="文本生成" value="text_generation" />
            <el-option label="问答系统" value="qa_system" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-radio-group v-model="taskForm.priority">
            <el-radio value="low">低</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="high">高</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="taskForm.description" type="textarea" rows="3" placeholder="请输入任务描述" />
        </el-form-item>
        <el-form-item label="输入内容">
          <el-input v-model="taskForm.input_text" type="textarea" rows="5" placeholder="请输入任务输入内容" />
        </el-form-item>
        <el-form-item label="上传文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="5"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            drag
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文件到此处或<em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">支持PDF、Word、TXT等文件，单个文件不超过10MB</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitTask">提交</el-button>
      </template>
    </el-dialog>

    <!-- Task Detail Dialog -->
    <el-dialog v-model="showDetailDialog" title="任务详情" width="700px">
      <el-descriptions :column="2" border v-if="currentTask">
        <el-descriptions-item label="任务名称">{{ currentTask.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentTask.status)">{{ getStatusLabel(currentTask.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="任务类型">{{ getTaskTypeLabel(currentTask.task_type) }}</el-descriptions-item>
        <el-descriptions-item label="优先级">
          <el-tag :type="getPriorityType(currentTask.priority)">{{ getPriorityLabel(currentTask.priority) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="进度">
          <el-progress :percentage="currentTask.progress" :color="getProgressColor(currentTask.status)" />
        </el-descriptions-item>
        <el-descriptions-item label="输入Tokens">{{ formatNumber(currentTask.input_tokens) }}</el-descriptions-item>
        <el-descriptions-item label="输出Tokens">{{ formatNumber(currentTask.output_tokens) }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ formatTime(currentTask.submit_time) }}</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ currentTask.start_time ? formatTime(currentTask.start_time) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ currentTask.end_time ? formatTime(currentTask.end_time) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ currentTask.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="输入内容" :span="2">
          <div class="content-box">{{ currentTask.input_text || '-' }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="执行结果" :span="2">
          <div class="content-box result">{{ currentTask.result || '-' }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="错误信息" :span="2" v-if="currentTask.error_message">
          <div class="content-box error">{{ currentTask.error_message }}</div>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { tasksApi } from '@/api'
import { ElMessage, ElMessageBox, type FormInstance, type UploadFiles } from 'element-plus'
import { Plus, UploadFilled } from '@element-plus/icons-vue'

const loading = ref(false)
const submitting = ref(false)
const tasks = ref<any[]>([])
const total = ref(0)
const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const currentTask = ref<any>(null)
const taskFormRef = ref<FormInstance>()
const uploadRef = ref()
const uploadedFiles = ref<File[]>([])
const selectedTasks = ref<any[]>([])

const filters = reactive({
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20
})

const taskForm = reactive({
  name: '',
  description: '',
  task_type: 'general',
  input_text: '',
  priority: 'medium'
})

const taskRules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  task_type: [{ required: true, message: '请选择任务类型', trigger: 'change' }]
}

const getTaskTypeLabel = (type: string) => {
  const typeMap: Record<string, string> = {
    'general': '通用任务',
    'document_process': '文档处理',
    'data_analysis': '数据分析',
    'text_generation': '文本生成',
    'qa_system': '问答系统'
  }
  return typeMap[type] || type
}

const getStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    'pending': 'info',
    'running': 'primary',
    'completed': 'success',
    'failed': 'danger',
    'cancelled': 'warning'
  }
  return typeMap[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const labelMap: Record<string, string> = {
    'pending': '等待中',
    'running': '运行中',
    'completed': '已完成',
    'failed': '失败',
    'cancelled': '已取消'
  }
  return labelMap[status] || status
}

const getPriorityType = (priority: string) => {
  const typeMap: Record<string, string> = {
    'low': 'info',
    'medium': 'warning',
    'high': 'danger'
  }
  return typeMap[priority] || 'info'
}

const getPriorityLabel = (priority: string) => {
  const labelMap: Record<string, string> = {
    'low': '低',
    'medium': '中',
    'high': '高'
  }
  return labelMap[priority] || priority
}

const getProgressColor = (status: string) => {
  if (status === 'completed') return '#67c23a'
  if (status === 'failed') return '#f56c6c'
  if (status === 'running') return '#409eff'
  return '#909399'
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

const canCancel = (status: string) => {
  return ['pending', 'running'].includes(status)
}

const loadTasks = async () => {
  loading.value = true
  try {
    const response = await tasksApi.list({
      status: filters.status || undefined,
      page: pagination.page,
      page_size: pagination.pageSize
    })
    // 支持新格式 {items, total, page, page_size} 和旧格式数组
    tasks.value = response.items || response
    total.value = response.total || response.length
  } catch (error) {
    console.error('Failed to load tasks:', error)
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.status = ''
  pagination.page = 1
  loadTasks()
}

const handleSelectionChange = (selection: any[]) => {
  selectedTasks.value = selection
}

const handleFileChange = (file: any, files: UploadFiles) => {
  uploadedFiles.value = files.map(f => f.raw as File)
}

const handleFileRemove = (file: any, files: UploadFiles) => {
  uploadedFiles.value = files.map(f => f.raw as File)
}

const submitTask = async () => {
  if (!taskFormRef.value) return
  
  await taskFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    submitting.value = true
    try {
      // Create FormData for file upload
      const formData = new FormData()
      formData.append('name', taskForm.name)
      formData.append('description', taskForm.description)
      formData.append('task_type', taskForm.task_type)
      formData.append('input_text', taskForm.input_text)
      formData.append('priority', taskForm.priority)
      
      uploadedFiles.value.forEach(file => {
        formData.append('files', file)
      })
      
      await tasksApi.create(formData)
      ElMessage.success('任务提交成功')
      showCreateDialog.value = false
      resetTaskForm()
      loadTasks()
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || '任务提交失败')
    } finally {
      submitting.value = false
    }
  })
}

const resetTaskForm = () => {
  taskForm.name = ''
  taskForm.description = ''
  taskForm.task_type = 'general'
  taskForm.input_text = ''
  taskForm.priority = 'medium'
  uploadedFiles.value = []
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

const viewTask = async (row: any) => {
  try {
    const data = await tasksApi.get(row.id)
    currentTask.value = data
    showDetailDialog.value = true
  } catch (error) {
    ElMessage.error('获取任务详情失败')
  }
}

const resumeTask = async (row: any) => {
  try {
    await ElMessageBox.confirm('确认要从断点恢复该任务吗?', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'info'
    })
    await tasksApi.resume(row.id)
    ElMessage.success('任务已恢复')
    loadTasks()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '恢复任务失败')
    }
  }
}

const cancelTask = async (row: any) => {
  try {
    await ElMessageBox.confirm('确认要取消该任务吗?', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await tasksApi.cancel(row.id)
    ElMessage.success('任务已取消')
    loadTasks()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '取消任务失败')
    }
  }
}

const batchCancelTasks = async () => {
  if (!selectedTasks.value.length) return
  
  try {
    await ElMessageBox.confirm(
      `确认要取消选中的 ${selectedTasks.value.length} 个任务吗?`, 
      '批量取消', 
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const ids = selectedTasks.value.map(t => t.id)
    await tasksApi.batchCancel(ids)
    ElMessage.success('批量取消成功')
    selectedTasks.value = []
    loadTasks()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '批量取消失败')
    }
  }
}

onMounted(() => {
  loadTasks()
})
</script>

<style scoped>
.tasks-page {
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

.header-actions {
  display: flex;
  gap: 10px;
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

.content-box {
  max-height: 150px;
  overflow-y: auto;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}

.content-box.result {
  background: #f0f9ff;
}

.content-box.error {
  background: #fef0f0;
  color: #f56c6c;
}

.template-desc {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}
</style>
