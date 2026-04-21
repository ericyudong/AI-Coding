<template>
  <div class="service-config">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- Services Tab -->
      <el-tab-pane label="服务配置" name="services">
        <div class="toolbar">
          <el-button type="primary" @click="showServiceDialog = true">
            <el-icon><Plus /></el-icon>添加服务
          </el-button>
        </div>
        
        <el-table :data="services" style="width: 100%" v-loading="servicesLoading">
          <el-table-column prop="name" label="服务名称" width="180" />
          <el-table-column prop="service_type" label="服务类型" width="150" />
          <el-table-column prop="description" label="描述" />
          <el-table-column prop="enabled" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'">
                {{ row.enabled ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="editService(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteService(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- LLM Config Tab -->
      <el-tab-pane label="LLM配置" name="llm">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>LLM大语言模型配置</span>
              <el-button type="primary" @click="saveLLMConfig" :loading="llmLoading">保存配置</el-button>
            </div>
          </template>
          <el-form :model="llmConfig" label-width="120px">
            <el-form-item label="服务提供商">
              <el-select v-model="llmConfig.provider" placeholder="请选择">
                <el-option label="OpenAI" value="openai" />
                <el-option label="Anthropic (Claude)" value="anthropic" />
                <el-option label="Azure OpenAI" value="azure" />
                <el-option label="本地模型" value="local" />
                <el-option label="自定义" value="custom" />
              </el-select>
            </el-form-item>
            <el-form-item label="模型名称">
              <el-input v-model="llmConfig.model" placeholder="如: gpt-4, claude-3-opus" />
            </el-form-item>
            <el-form-item label="API Key">
              <el-input v-model="llmConfig.api_key" type="password" show-password placeholder="请输入API Key" />
            </el-form-item>
            <el-form-item label="Base URL">
              <el-input v-model="llmConfig.base_url" placeholder="自定义API地址" />
            </el-form-item>
            <el-form-item label="Temperature">
              <el-slider v-model="llmConfig.temperature" :min="0" :max="2" :step="0.1" show-stops />
              <span class="slider-value">{{ llmConfig.temperature }}</span>
            </el-form-item>
            <el-form-item label="Max Tokens">
              <el-input-number v-model="llmConfig.max_tokens" :min="100" :max="100000" :step="100" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- RAG Config Tab -->
      <el-tab-pane label="RAG配置" name="rag">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>RAG检索增强配置</span>
              <el-button type="primary" @click="saveRAGConfig" :loading="ragLoading">保存配置</el-button>
            </div>
          </template>
          <el-form :model="ragConfig" label-width="150px">
            <el-form-item label="文档分块大小">
              <el-input-number v-model="ragConfig.chunk_size" :min="100" :max="10000" :step="100" />
            </el-form-item>
            <el-form-item label="分块重叠大小">
              <el-input-number v-model="ragConfig.chunk_overlap" :min="0" :max="5000" :step="50" />
            </el-form-item>
            <el-form-item label="检索Top K">
              <el-input-number v-model="ragConfig.top_k" :min="1" :max="100" />
            </el-form-item>
            <el-form-item label="向量数据库类型">
              <el-select v-model="ragConfig.vector_store_type">
                <el-option label="FAISS" value="faiss" />
                <el-option label="Chroma" value="chroma" />
                <el-option label="Milvus" value="milvus" />
                <el-option label="Pinecone" value="pinecone" />
              </el-select>
            </el-form-item>
            <el-form-item label="Embedding模型">
              <el-input v-model="ragConfig.embedding_model" placeholder="如: sentence-transformers/all-MiniLM-L6-v2" />
            </el-form-item>
            <el-form-item label="向量维度">
              <el-input-number v-model="ragConfig.embedding_dim" :min="128" :max="4096" :step="64" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <!-- MCP Config Tab -->
      <el-tab-pane label="MCP配置" name="mcp">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>MCP服务配置</span>
              <el-button type="primary" @click="saveMCPConfig" :loading="mcpLoading">保存配置</el-button>
            </div>
          </template>
          <el-form :model="mcpConfig" label-width="120px">
            <el-form-item label="启用MCP">
              <el-switch v-model="mcpConfig.enabled" />
            </el-form-item>
          </el-form>
          
          <div class="mcp-servers">
            <div class="server-header">
              <span>MCP服务器列表</span>
              <el-button type="primary" size="small" @click="showMCPServerDialog = true">
                <el-icon><Plus /></el-icon>添加服务器
              </el-button>
            </div>
            <el-table :data="mcpConfig.servers" style="width: 100%" v-if="mcpConfig.servers.length > 0">
              <el-table-column prop="name" label="服务器名称" width="150" />
              <el-table-column prop="type" label="类型" width="120" />
              <el-table-column prop="command" label="命令" />
              <el-table-column label="操作" width="120" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" type="danger" @click="deleteMCPServer(row.id)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="暂无MCP服务器配置" />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- Service Dialog -->
    <el-dialog v-model="showServiceDialog" :title="editingService ? '编辑服务' : '添加服务'" width="600px">
      <el-form :model="serviceForm" label-width="100px">
        <el-form-item label="服务名称" required>
          <el-input v-model="serviceForm.name" placeholder="请输入服务名称" />
        </el-form-item>
        <el-form-item label="服务类型" required>
          <el-select v-model="serviceForm.service_type" placeholder="请选择服务类型">
            <el-option label="数据源" value="datasource" />
            <el-option label="API" value="api" />
            <el-option label="工具" value="tool" />
            <el-option label="存储" value="storage" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="serviceForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="serviceForm.enabled" />
        </el-form-item>
        <el-form-item label="配置参数">
          <el-input v-model="serviceForm.configJson" type="textarea" :rows="5" placeholder="JSON格式配置" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showServiceDialog = false">取消</el-button>
        <el-button type="primary" @click="saveService" :loading="serviceLoading">保存</el-button>
      </template>
    </el-dialog>

    <!-- MCP Server Dialog -->
    <el-dialog v-model="showMCPServerDialog" title="添加MCP服务器" width="500px">
      <el-form :model="mcpServerForm" label-width="100px">
        <el-form-item label="服务器名称" required>
          <el-input v-model="mcpServerForm.name" placeholder="请输入服务器名称" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="mcpServerForm.type" placeholder="请选择类型">
            <el-option label="StdIO" value="stdio" />
            <el-option label="SSE" value="sse" />
          </el-select>
        </el-form-item>
        <el-form-item label="命令" required>
          <el-input v-model="mcpServerForm.command" placeholder="如: npx" />
        </el-form-item>
        <el-form-item label="参数">
          <el-input v-model="mcpServerForm.args" placeholder="如: -y @modelcontextprotocol/server-filesystem /path/to/files" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMCPServerDialog = false">取消</el-button>
        <el-button type="primary" @click="addMCPServer">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { systemApi } from '@/api'
import { Plus } from '@element-plus/icons-vue'

const activeTab = ref('services')

// Services
const services = ref([])
const servicesLoading = ref(false)
const showServiceDialog = ref(false)
const serviceLoading = ref(false)
const editingService = ref<any>(null)
const serviceForm = ref({
  name: '',
  service_type: '',
  description: '',
  enabled: true,
  configJson: '{}'
})

// LLM Config
const llmConfig = ref({
  provider: 'openai',
  model: 'gpt-4',
  api_key: '',
  base_url: '',
  temperature: 0.7,
  max_tokens: 2000
})
const llmLoading = ref(false)

// RAG Config
const ragConfig = ref({
  chunk_size: 1000,
  chunk_overlap: 200,
  top_k: 5,
  vector_store_type: 'faiss',
  embedding_model: 'sentence-transformers',
  embedding_dim: 768
})
const ragLoading = ref(false)

// MCP Config
const mcpConfig = ref({
  enabled: true,
  servers: [] as any[]
})
const mcpLoading = ref(false)
const showMCPServerDialog = ref(false)
const mcpServerForm = ref({
  name: '',
  type: 'stdio',
  command: '',
  args: ''
})

// Load data
const loadServices = async () => {
  servicesLoading.value = true
  try {
    services.value = await systemApi.listServices()
  } catch (e) {
    console.error('Failed to load services:', e)
  } finally {
    servicesLoading.value = false
  }
}

const loadLLMConfig = async () => {
  try {
    const data = await systemApi.getLLMConfig()
    llmConfig.value = { ...llmConfig.value, ...data }
  } catch (e) {
    console.error('Failed to load LLM config:', e)
  }
}

const loadRAGConfig = async () => {
  try {
    const data = await systemApi.getRAGConfig()
    ragConfig.value = { ...ragConfig.value, ...data }
  } catch (e) {
    console.error('Failed to load RAG config:', e)
  }
}

const loadMCPConfig = async () => {
  try {
    const data = await systemApi.getMCPConfig()
    mcpConfig.value = { ...mcpConfig.value, ...data }
  } catch (e) {
    console.error('Failed to load MCP config:', e)
  }
}

// Save config
const saveLLMConfig = async () => {
  llmLoading.value = true
  try {
    await systemApi.updateLLMConfig(llmConfig.value)
    ElMessage.success('LLM配置保存成功')
  } catch (e) {
    console.error('Failed to save LLM config:', e)
  } finally {
    llmLoading.value = false
  }
}

const saveRAGConfig = async () => {
  ragLoading.value = true
  try {
    await systemApi.updateRAGConfig(ragConfig.value)
    ElMessage.success('RAG配置保存成功')
  } catch (e) {
    console.error('Failed to save RAG config:', e)
  } finally {
    ragLoading.value = false
  }
}

const saveMCPConfig = async () => {
  mcpLoading.value = true
  try {
    await systemApi.updateMCPConfig(mcpConfig.value)
    ElMessage.success('MCP配置保存成功')
  } catch (e) {
    console.error('Failed to save MCP config:', e)
  } finally {
    mcpLoading.value = false
  }
}

// Service operations
const editService = (service: any) => {
  editingService.value = service
  serviceForm.value = {
    name: service.name,
    service_type: service.service_type,
    description: service.description,
    enabled: service.enabled,
    configJson: JSON.stringify(service.config, null, 2)
  }
  showServiceDialog.value = true
}

const saveService = async () => {
  serviceLoading.value = true
  try {
    let config = {}
    try {
      config = JSON.parse(serviceForm.value.configJson)
    } catch {
      ElMessage.error('配置参数必须是有效的JSON格式')
      return
    }
    
    const data = {
      name: serviceForm.value.name,
      service_type: serviceForm.value.service_type,
      description: serviceForm.value.description,
      enabled: serviceForm.value.enabled,
      config
    }
    
    if (editingService.value) {
      await systemApi.updateService(editingService.value.id, data)
      ElMessage.success('服务更新成功')
    } else {
      await systemApi.createService(data)
      ElMessage.success('服务创建成功')
    }
    
    showServiceDialog.value = false
    editingService.value = null
    serviceForm.value = {
      name: '',
      service_type: '',
      description: '',
      enabled: true,
      configJson: '{}'
    }
    loadServices()
  } catch (e) {
    console.error('Failed to save service:', e)
  } finally {
    serviceLoading.value = false
  }
}

const deleteService = async (id: string) => {
  try {
    await ElMessageBox.confirm('确定要删除这个服务吗?', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await systemApi.deleteService(id)
    ElMessage.success('服务删除成功')
    loadServices()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('Failed to delete service:', e)
    }
  }
}

// MCP Server operations
const addMCPServer = async () => {
  try {
    const server = {
      name: mcpServerForm.value.name,
      type: mcpServerForm.value.type,
      command: mcpServerForm.value.command,
      args: mcpServerForm.value.args.split(' ').filter((a: string) => a)
    }
    
    await systemApi.addMCPServer(server)
    ElMessage.success('MCP服务器添加成功')
    showMCPServerDialog.value = false
    mcpServerForm.value = { name: '', type: 'stdio', command: '', args: '' }
    loadMCPConfig()
  } catch (e) {
    console.error('Failed to add MCP server:', e)
  }
}

const deleteMCPServer = async (serverId: string) => {
  try {
    await ElMessageBox.confirm('确定要删除这个MCP服务器吗?', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await systemApi.deleteMCPServer(serverId)
    ElMessage.success('MCP服务器删除成功')
    loadMCPConfig()
  } catch (e) {
    if (e !== 'cancel') {
      console.error('Failed to delete MCP server:', e)
    }
  }
}

onMounted(() => {
  loadServices()
  loadLLMConfig()
  loadRAGConfig()
  loadMCPConfig()
})
</script>

<style scoped>
.service-config {
  padding: 20px;
}

.toolbar {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.slider-value {
  margin-left: 10px;
  color: #409eff;
}

.mcp-servers {
  margin-top: 20px;
}

.server-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}
</style>