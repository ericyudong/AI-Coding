<template>
  <div class="docker-control">
    <!-- Kubernetes环境按钮 -->
    <div v-if="!task.docker_container_name" class="docker-actions">
      <el-button 
        type="success" 
        size="small" 
        :loading="creating"
        @click="createDocker"
      >
        <el-icon><Box /></el-icon>
        创建Kubernetes环境
      </el-button>
    </div>
    
    <!-- Kubernetes环境已创建 -->
    <div v-else class="docker-info">
      <div class="docker-status-row">
        <el-tag :type="dockerStatusType" size="small">
          <el-icon v-if="dockerStatus === 'running'"><Loading /></el-icon>
          {{ dockerStatusLabel }}
        </el-tag>
        <el-link 
          v-if="task.docker_url && dockerStatus === 'running'" 
          :href="task.docker_url" 
          target="_blank"
          type="primary"
          class="docker-link"
        >
          <el-icon><Link /></el-icon>
          访问OpenClaw
        </el-link>
      </div>
      
      <div class="docker-actions-row">
        <el-button 
          v-if="dockerStatus === 'stopped' || dockerStatus === 'not_found' || dockerStatus === 'Pending'"
          type="primary" 
          size="small" 
          :loading="starting"
          @click="startDocker"
        >
          启动
        </el-button>
        <el-button 
          v-if="dockerStatus === 'running'"
          type="warning" 
          size="small" 
          :loading="stopping"
          @click="stopDocker"
        >
          停止
        </el-button>
        <el-button 
          type="danger" 
          size="small" 
          :loading="removing"
          @click="removeDocker"
        >
          删除
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { tasksApi } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Box, Link, Loading } from '@element-plus/icons-vue'

const props = defineProps<{
  task: any
}>()

const emit = defineEmits(['refresh'])

const creating = ref(false)
const starting = ref(false)
const stopping = ref(false)
const removing = ref(false)
const dockerStatus = ref<string>('')

const dockerStatusType = computed(() => {
  const statusMap: Record<string, string> = {
    'running': 'success',
    'Running': 'success',
    'stopped': 'warning',
    'Stopped': 'warning',
    'not_found': 'info',
    'error': 'danger',
    'Pending': 'warning',
    'Succeeded': 'success',
    'Failed': 'danger'
  }
  return statusMap[dockerStatus.value] || 'info'
})

const dockerStatusLabel = computed(() => {
  const labelMap: Record<string, string> = {
    'running': '运行中',
    'Running': '运行中',
    'stopped': '已停止',
    'Stopped': '已停止',
    'not_found': '未创建',
    'error': '错误',
    'Pending': '等待中',
    'Succeeded': '已完成',
    'Failed': '失败'
  }
  return labelMap[dockerStatus.value] || dockerStatus.value || '未知'
})

// 监听任务变化时获取Docker状态
watch(() => props.task, async (newTask) => {
  if (newTask?.docker_container_name) {
    await fetchDockerStatus()
  }
}, { immediate: true })

const fetchDockerStatus = async () => {
  if (!props.task?.id) return
  
  try {
    const data = await tasksApi.getDockerStatus(props.task.id)
    dockerStatus.value = data.docker_status || 'not_found'
  } catch (error) {
    dockerStatus.value = 'error'
  }
}

const createDocker = async () => {
  try {
    await ElMessageBox.confirm(
      '将为该任务创建一个OpenClaw Kubernetes环境，创建后可通过链接访问。是否继续?',
      '创建Kubernetes环境',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )
    
    creating.value = true
    const result = await tasksApi.createDocker(props.task.id)
    
    ElMessage.success('Kubernetes环境创建成功')
    await fetchDockerStatus()
    emit('refresh')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '创建Kubernetes环境失败')
    }
  } finally {
    creating.value = false
  }
}

const startDocker = async () => {
  try {
    starting.value = true
    await tasksApi.startDocker(props.task.id)
    ElMessage.success('Kubernetes环境已启动')
    await fetchDockerStatus()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '启动失败')
  } finally {
    starting.value = false
  }
}

const stopDocker = async () => {
  try {
    stopping.value = true
    await tasksApi.stopDocker(props.task.id)
    ElMessage.success('Kubernetes环境已停止')
    await fetchDockerStatus()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '停止失败')
  } finally {
    stopping.value = false
  }
}

const removeDocker = async () => {
  try {
    await ElMessageBox.confirm(
      '删除后将无法恢复Kubernetes环境，是否继续?',
      '删除Kubernetes环境',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    removing.value = true
    await tasksApi.removeDocker(props.task.id)
    ElMessage.success('Kubernetes环境已删除')
    dockerStatus.value = ''
    emit('refresh')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  } finally {
    removing.value = false
  }
}
</script>

<style scoped>
.docker-control {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.docker-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.docker-status-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.docker-link {
  font-size: 12px;
}

.docker-actions-row {
  display: flex;
  gap: 5px;
}
</style>