<template>
  <div class="knowledge-page">
    <!-- Header -->
    <div class="page-header">
      <h2>知识库管理</h2>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>创建知识库
      </el-button>
    </div>

    <!-- Tabs for KB Types -->
    <el-tabs v-model="activeTab" @tab-change="loadKnowledgeBases">
      <el-tab-pane label="我的知识库" name="personal" />
      <el-tab-pane label="部门共享" name="dept_shared" />
      <el-tab-pane label="全部" name="all" />
    </el-tabs>

    <!-- Knowledge Base List -->
    <el-card class="table-card">
      <el-table :data="knowledgeBases" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.type === 'personal' ? 'success' : 'warning'">
              {{ row.type === 'personal' ? '个人' : '部门共享' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="review_status" label="审核状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getReviewStatusType(row.review_status)">
              {{ getReviewStatusLabel(row.review_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="doc_count" label="文档数" width="80" />
        <el-table-column prop="total_size" label="大小" width="100">
          <template #default="{ row }">
            {{ formatSize(row.total_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewKB(row)">详情</el-button>
            <el-button type="primary" link @click="viewDocuments(row)">文档</el-button>
            <el-button type="success" link @click="showSearchDialog(row)">检索</el-button>
            <el-button type="danger" link @click="deleteKB(row)" v-if="canModify(row)">删除</el-button>
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
          @size-change="loadKnowledgeBases"
          @current-change="loadKnowledgeBases"
        />
      </div>
    </el-card>

    <!-- Create KB Dialog -->
    <el-dialog v-model="showCreateDialog" title="创建知识库" width="500px">
      <el-form :model="kbForm" :rules="kbRules" ref="kbFormRef" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="kbForm.name" placeholder="请输入知识库名称" />
        </el-form-item>
        <el-form-item label="类型" prop="kb_type">
          <el-radio-group v-model="kbForm.kb_type" :disabled="!canCreateDeptKB">
            <el-radio value="personal">个人知识库</el-radio>
            <el-radio value="dept_shared" :disabled="!canCreateDeptKB">部门共享</el-radio>
          </el-radio-group>
          <div class="form-tip" v-if="!canCreateDeptKB">
            只有部门管理员或超级管理员可以创建部门共享知识库
          </div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="kbForm.description" type="textarea" rows="3" placeholder="请输入知识库描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createKB">创建</el-button>
      </template>
    </el-dialog>

    <!-- KB Detail / Documents Dialog -->
    <el-dialog v-model="showDocDialog" :title="currentKB?.name + ' - 文档管理'" width="900px">
      <!-- Upload Document -->
      <div class="upload-section" v-if="canModify(currentKB!)">
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :limit="10"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          drag
          multiple
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽文件到此处或<em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">支持PDF、Word、TXT、MD等文件</div>
          </template>
        </el-upload>
        <el-button type="primary" :loading="uploading" @click="uploadDocuments" style="margin-top: 10px">
          上传文档
        </el-button>
      </div>

      <!-- Documents Table -->
      <el-table :data="documents" v-loading="docsLoading" style="width: 100%; margin-top: 20px">
        <el-table-column prop="filename" label="文件名" min-width="200" />
        <el-table-column prop="file_type" label="类型" width="100" />
        <el-table-column prop="file_size" label="大小" width="100">
          <template #default="{ row }">
            {{ formatSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getDocStatusType(row.status)">
              {{ getDocStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="分块数" width="80" />
        <el-table-column prop="created_at" label="上传时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" v-if="canModify(currentKB!)">
          <template #default="{ row }">
            <el-button type="danger" link @click="deleteDocument(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- Search Dialog -->
    <el-dialog v-model="showSearchDialog" title="知识检索" width="800px">
      <el-form :inline="true" :model="searchForm">
        <el-form-item label="检索内容">
          <el-input v-model="searchForm.query" placeholder="请输入检索关键词" style="width: 400px" />
        </el-form-item>
        <el-form-item label="Top K">
          <el-input-number v-model="searchForm.top_k" :min="1" :max="20" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="searching" @click="doSearch">检索</el-button>
        </el-form-item>
      </el-form>

      <!-- Search Results -->
      <div class="search-results" v-if="searchResults.length > 0">
        <el-card v-for="(result, index) in searchResults" :key="index" class="result-item">
          <template #header>
            <div class="result-header">
              <span class="filename">{{ result.filename }}</span>
              <el-tag type="success">相似度: {{ (result.score * 100).toFixed(1) }}%</el-tag>
            </div>
          </template>
          <div class="result-content">{{ result.content }}</div>
        </el-card>
      </div>
      <el-empty v-else-if="!searching" description="请输入检索关键词" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { knowledgeApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox, type FormInstance, type UploadFiles } from 'element-plus'
import { Plus, UploadFilled } from '@element-plus/icons-vue'

const authStore = useAuthStore()

const loading = ref(false)
const uploading = ref(false)
const searching = ref(false)
const submitting = ref(false)
const knowledgeBases = ref<any[]>([])
const documents = ref<any[]>([])
const searchResults = ref<any[]>([])
const total = ref(0)
const activeTab = ref('personal')
const showCreateDialog = ref(false)
const showDocDialog = ref(false)
const showSearchDialog = ref(false)
const currentKB = ref<any>(null)
const kbFormRef = ref<FormInstance>()
const uploadRef = ref()
const uploadedFiles = ref<File[]>([])

const pagination = reactive({
  page: 1,
  pageSize: 20
})

const kbForm = reactive({
  name: '',
  description: '',
  kb_type: 'personal'
})

const searchForm = reactive({
  query: '',
  top_k: 5,
  knowledge_base_id: ''
})

const kbRules = {
  name: [{ required: true, message: '请输入知识库名称', trigger: 'blur' }],
  kb_type: [{ required: true, message: '请选择知识库类型', trigger: 'change' }]
}

const canCreateDeptKB = computed(() => {
  return authStore.isAdmin
})

const canModify = (kb: any) => {
  if (authStore.isSuperAdmin) return true
  if (kb.owner_id === authStore.user?.id) return true
  if (kb.type === 'dept_shared' && authStore.user?.role === 'dept_admin') return true
  return false
}

const getReviewStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    'pending': 'warning',
    'approved': 'success',
    'rejected': 'danger'
  }
  return typeMap[status] || 'info'
}

const getReviewStatusLabel = (status: string) => {
  const labelMap: Record<string, string> = {
    'pending': '待审核',
    'approved': '已通过',
    'rejected': '已拒绝'
  }
  return labelMap[status] || status
}

const getDocStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    'pending': 'warning',
    'processing': 'primary',
    'completed': 'success',
    'failed': 'danger'
  }
  return typeMap[status] || 'info'
}

const getDocStatusLabel = (status: string) => {
  const labelMap: Record<string, string> = {
    'pending': '等待处理',
    'processing': '处理中',
    'completed': '已完成',
    'failed': '失败'
  }
  return labelMap[status] || status
}

const formatSize = (bytes: number) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let index = 0
  let size = bytes
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index++
  }
  return size.toFixed(1) + ' ' + units[index]
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const loadKnowledgeBases = async () => {
  loading.value = true
  try {
    const kbType = activeTab.value === 'all' ? undefined : activeTab.value
    const data = await knowledgeApi.list({
      kb_type: kbType,
      page: pagination.page,
      page_size: pagination.pageSize
    })
    // 支持新格式 {items, total, page, page_size} 和旧格式数组
    knowledgeBases.value = data.items || data
    total.value = data.total || data.length || 0
  } catch (error) {
    console.error('Failed to load knowledge bases:', error)
  } finally {
    loading.value = false
  }
}

const createKB = async () => {
  if (!kbFormRef.value) return
  
  await kbFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    submitting.value = true
    try {
      await knowledgeApi.create(kbForm)
      ElMessage.success('知识库创建成功')
      showCreateDialog.value = false
      resetKBForm()
      loadKnowledgeBases()
    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || '创建失败')
    } finally {
      submitting.value = false
    }
  })
}

const resetKBForm = () => {
  kbForm.name = ''
  kbForm.description = ''
  kbForm.kb_type = 'personal'
}

const viewKB = async (row: any) => {
  try {
    const data = await knowledgeApi.get(row.id)
    currentKB.value = data
    // Could show detail dialog here
  } catch (error) {
    ElMessage.error('获取知识库详情失败')
  }
}

const viewDocuments = async (row: any) => {
  currentKB.value = row
  showDocDialog.value = true
  await loadDocuments(row.id)
}

const loadDocuments = async (kbId: string) => {
  docsLoading.value = true
  try {
    const data = await knowledgeApi.listDocuments(kbId)
    documents.value = data
  } catch (error) {
    console.error('Failed to load documents:', error)
  } finally {
    docsLoading.value = false
  }
}

const handleFileChange = (file: any, files: UploadFiles) => {
  uploadedFiles.value = files.map(f => f.raw as File)
}

const handleFileRemove = (file: any, files: UploadFiles) => {
  uploadedFiles.value = files.map(f => f.raw as File)
}

const uploadDocuments = async () => {
  if (!currentKB.value || uploadedFiles.value.length === 0) return
  
  uploading.value = true
  try {
    for (const file of uploadedFiles.value) {
      await knowledgeApi.uploadDocument(currentKB.value.id, file)
    }
    ElMessage.success('文档上传成功')
    uploadedFiles.value = []
    if (uploadRef.value) {
      uploadRef.value.clearFiles()
    }
    loadDocuments(currentKB.value.id)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

const deleteDocument = async (doc: any) => {
  try {
    await ElMessageBox.confirm('确认要删除该文档吗?', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await knowledgeApi.deleteDocument(currentKB.value.id, doc.id)
    ElMessage.success('文档删除成功')
    loadDocuments(currentKB.value.id)
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

const deleteKB = async (row: any) => {
  try {
    await ElMessageBox.confirm('确认要删除该知识库吗? 删除后无法恢复。', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'error'
    })
    await knowledgeApi.delete(row.id)
    ElMessage.success('知识库删除成功')
    loadKnowledgeBases()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

const openSearchDialog = (row: any) => {
  currentKB.value = row
  searchForm.knowledge_base_id = row.id
  searchForm.query = ''
  searchResults.value = []
  showSearchDialog.value = true
}

const doSearch = async () => {
  if (!searchForm.query) return
  
  searching.value = true
  try {
    const data = await knowledgeApi.search({
      query: searchForm.query,
      knowledge_base_id: searchForm.knowledge_base_id,
      top_k: searchForm.top_k
    })
    searchResults.value = data
  } catch (error) {
    ElMessage.error('检索失败')
  } finally {
    searching.value = false
  }
}

const canModifyKB = (kb: any): boolean => {
  if (!kb) return false
  if (authStore.isSuperAdmin) return true
  if (kb.owner_id === authStore.user?.id) return true
  if (kb.type === 'dept_shared' && authStore.user?.role === 'dept_admin') return true
  return false
}

onMounted(() => {
  loadKnowledgeBases()
})

const docsLoading = ref(false)
</script>

<style scoped>
.knowledge-page {
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

.table-card {
  margin-bottom: 20px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.upload-section {
  margin-bottom: 20px;
}

.search-results {
  max-height: 500px;
  overflow-y: auto;
}

.result-item {
  margin-bottom: 15px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filename {
  font-weight: 500;
}

.result-content {
  max-height: 150px;
  overflow-y: auto;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
