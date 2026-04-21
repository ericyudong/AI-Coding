<template>
  <div class="monitor-page">
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="page-header">
          <h2>系统监控</h2>
          <div class="header-actions">
            <el-button @click="loadMetrics" :loading="loading">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
            <el-select v-model="refreshInterval" style="width: 120px" @change="handleIntervalChange">
              <el-option label="5秒" :value="5000" />
              <el-option label="10秒" :value="10000" />
              <el-option label="30秒" :value="30000" />
              <el-option label="1分钟" :value="60000" />
              <el-option label="关闭" :value="0" />
            </el-select>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- CPU & Memory Cards -->
    <el-row :gutter="20" class="metrics-row">
      <el-col :span="8">
        <el-card class="metric-card">
          <template #header>
            <div class="card-header">
              <el-icon color="#409eff" :size="24"><Cpu /></el-icon>
              <span>CPU 使用率</span>
            </div>
          </template>
          <div class="metric-content">
            <el-progress 
              type="circle" 
              :percentage="metrics.cpu.percent" 
              :color="getCpuColor(metrics.cpu.percent)"
              :width="120"
            />
            <div class="metric-detail">
              <p><span>核心数:</span> {{ metrics.cpu.cores }}</p>
              <p><span>速度:</span> {{ metrics.cpu.speed }} GHz</p>
              <p><span>负载:</span> {{ metrics.cpu.load }}</p>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="metric-card">
          <template #header>
            <div class="card-header">
              <el-icon color="#67c23a" :size="24"><Monitor /></el-icon>
              <span>内存使用</span>
            </div>
          </template>
          <div class="metric-content">
            <el-progress 
              type="circle" 
              :percentage="metrics.memory.percent" 
              :color="getMemoryColor(metrics.memory.percent)"
              :width="120"
            />
            <div class="metric-detail">
              <p><span>总计:</span> {{ formatBytes(metrics.memory.total) }}</p>
              <p><span>已用:</span> {{ formatBytes(metrics.memory.used) }}</p>
              <p><span>可用:</span> {{ formatBytes(metrics.memory.available) }}</p>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="metric-card">
          <template #header>
            <div class="card-header">
              <el-icon color="#e6a23c" :size="24"><Coin /></el-icon>
              <span>磁盘使用</span>
            </div>
          </template>
          <div class="metric-content">
            <el-progress 
              type="circle" 
              :percentage="metrics.disk.percent" 
              :color="getDiskColor(metrics.disk.percent)"
              :width="120"
            />
            <div class="metric-detail">
              <p><span>总计:</span> {{ formatBytes(metrics.disk.total) }}</p>
              <p><span>已用:</span> {{ formatBytes(metrics.disk.used) }}</p>
              <p><span>可用:</span> {{ formatBytes(metrics.disk.free) }}</p>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Network & Process Info -->
    <el-row :gutter="20" class="metrics-row">
      <el-col :span="12">
        <el-card class="metric-card">
          <template #header>
            <div class="card-header">
              <el-icon color="#909399" :size="24"><Connection /></el-icon>
              <span>网络状态</span>
            </div>
          </template>
          <div class="network-stats">
            <div class="network-item">
              <span class="label">发送:</span>
              <span class="value">{{ formatBytes(metrics.network.bytes_sent) }}</span>
              <el-tag size="small" type="success">↑</el-tag>
            </div>
            <div class="network-item">
              <span class="label">接收:</span>
              <span class="value">{{ formatBytes(metrics.network.bytes_recv) }}</span>
              <el-tag size="small" type="primary">↓</el-tag>
            </div>
            <div class="network-item">
              <span class="label">数据包发送:</span>
              <span class="value">{{ formatNumber(metrics.network.packets_sent) }}</span>
            </div>
            <div class="network-item">
              <span class="label">数据包接收:</span>
              <span class="value">{{ formatNumber(metrics.network.packets_recv) }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card class="metric-card">
          <template #header>
            <div class="card-header">
              <el-icon color="#f56c6c" :size="24"><Tickets /></el-icon>
              <span>系统信息</span>
            </div>
          </template>
          <div class="system-info">
            <div class="info-item">
              <span class="label">主机名:</span>
              <span class="value">{{ metrics.system.hostname }}</span>
            </div>
            <div class="info-item">
              <span class="label">操作系统:</span>
              <span class="value">{{ metrics.system.os }}</span>
            </div>
            <div class="info-item">
              <span class="label">运行时间:</span>
              <span class="value">{{ metrics.system.uptime }}</span>
            </div>
            <div class="info-item">
              <span class="label">Python版本:</span>
              <span class="value">{{ metrics.system.python_version }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- CPU History Chart -->
    <el-row :gutter="20" class="metrics-row">
      <el-col :span="24">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>CPU 使用率趋势</span>
            </div>
          </template>
          <div class="chart-container" ref="cpuChartRef"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Memory History Chart -->
    <el-row :gutter="20" class="metrics-row">
      <el-col :span="24">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>内存使用趋势</span>
            </div>
          </template>
          <div class="chart-container" ref="memoryChartRef"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Docker Containers Status -->
    <el-row :gutter="20" class="metrics-row">
      <el-col :span="24">
        <el-card class="metric-card">
          <template #header>
            <div class="card-header">
              <el-icon color="#0099ff" :size="24"><Box /></el-icon>
              <span>Docker 容器状态</span>
              <el-button type="primary" size="small" style="margin-left: auto" @click="loadDockerStats">
                <el-icon><Refresh /></el-icon>刷新
              </el-button>
            </div>
          </template>
          <el-table :data="dockerStats" v-loading="dockerLoading" style="width: 100%">
            <el-table-column prop="name" label="容器名称" min-width="150" />
            <el-table-column prop="image" label="镜像" min-width="150" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getDockerStatusType(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="cpu_percent" label="CPU%" width="80">
              <template #default="{ row }">
                {{ row.cpu_percent?.toFixed(2) }}%
              </template>
            </el-table-column>
            <el-table-column prop="memory_percent" label="内存%" width="80">
              <template #default="{ row }">
                {{ row.memory_percent?.toFixed(2) }}%
              </template>
            </el-table-column>
            <el-table-column prop="created" label="创建时间" width="180" />
          </el-table>
          <el-empty v-if="!dockerLoading && dockerStats.length === 0" description="暂无容器运行" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Kubernetes Cluster Status -->
    <el-row :gutter="20" class="metrics-row">
      <el-col :span="24">
        <el-card class="metric-card">
          <template #header>
            <div class="card-header">
              <el-icon color="#326ce5" :size="24"><Box /></el-icon>
              <span>Kubernetes 集群状态</span>
              <el-button type="primary" size="small" style="margin-left: auto" @click="loadK8sStats">
                <el-icon><Refresh /></el-icon>刷新
              </el-button>
            </div>
          </template>
          
          <!-- Cluster Overview -->
          <div v-if="k8sCluster" class="k8s-overview">
            <el-row :gutter="20">
              <el-col :span="6">
                <div class="k8s-stat">
                  <div class="k8s-stat-value">{{ k8sCluster.total_nodes }}</div>
                  <div class="k8s-stat-label">节点数</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="k8s-stat">
                  <div class="k8s-stat-value">{{ k8sCluster.ready_nodes }}</div>
                  <div class="k8s-stat-label">就绪节点</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="k8s-stat">
                  <div class="k8s-stat-value">{{ k8sCluster.running_pods }}</div>
                  <div class="k8s-stat-label">运行Pod</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="k8s-stat">
                  <div class="k8s-stat-value">{{ k8sCluster.total_namespaces }}</div>
                  <div class="k8s-stat-label">命名空间</div>
                </div>
              </el-col>
            </el-row>
            <el-row :gutter="20" style="margin-top: 10px">
              <el-col :span="12">
                <div class="k8s-info-item">
                  <span class="label">集群版本:</span>
                  <span class="value">{{ k8sCluster.version }}</span>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="k8s-info-item">
                  <span class="label">CPU容量:</span>
                  <span class="value">{{ k8sCluster.cpu_capacity }}</span>
                </div>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <div class="k8s-info-item">
                  <span class="label">内存容量:</span>
                  <span class="value">{{ k8sCluster.memory_capacity }}</span>
                </div>
              </el-col>
              <el-col :span="12">
                <div class="k8s-info-item">
                  <span class="label">资源使用:</span>
                  <span class="value">{{ k8sCluster.cpu_used }} / {{ k8sCluster.memory_used }}</span>
                </div>
              </el-col>
            </el-row>
          </div>
          
          <!-- K8s Pods Table -->
          <el-divider>Pod 列表</el-divider>
          <el-table :data="k8sPods" v-loading="k8sLoading" style="width: 100%">
            <el-table-column prop="name" label="Pod名称" min-width="180" />
            <el-table-column prop="namespace" label="命名空间" width="120" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getK8sStatusType(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="node_name" label="节点" width="140" />
            <el-table-column prop="pod_ip" label="Pod IP" width="120" />
            <el-table-column prop="cpu_request" label="CPU请求" width="100" />
            <el-table-column prop="memory_request" label="内存请求" width="100" />
          </el-table>
          <el-empty v-if="!k8sLoading && k8sPods.length === 0" description="暂无Pod运行" />
        </el-card>
      </el-col>
    </el-row>

    <!-- GPU Status -->
    <el-row :gutter="20" class="metrics-row">
      <el-col :span="24">
        <el-card class="metric-card">
          <template #header>
            <div class="card-header">
              <el-icon color="#00d9ff" :size="24"><Monitor /></el-icon>
              <span>GPU 资源状态</span>
              <el-button type="primary" size="small" style="margin-left: auto" @click="loadGpuStats">
                <el-icon><Refresh /></el-icon>刷新
              </el-button>
            </div>
          </template>
          
          <!-- GPU Overview -->
          <div v-if="gpuInfo" class="gpu-overview">
            <el-row :gutter="20">
              <el-col :span="4">
                <div class="gpu-stat">
                  <div class="gpu-stat-value">{{ gpuInfo.total_gpus }}</div>
                  <div class="gpu-stat-label">GPU总数</div>
                </div>
              </el-col>
              <el-col :span="4">
                <div class="gpu-stat">
                  <div class="gpu-stat-value">{{ gpuInfo.used_gpus }}</div>
                  <div class="gpu-stat-label">使用中</div>
                </div>
              </el-col>
              <el-col :span="4">
                <div class="gpu-stat">
                  <div class="gpu-stat-value">{{ gpuInfo.available_gpus }}</div>
                  <div class="gpu-stat-label">可用</div>
                </div>
              </el-col>
              <el-col :span="4">
                <div class="gpu-stat">
                  <div class="gpu-stat-value">{{ gpuInfo.average_utilization }}%</div>
                  <div class="gpu-stat-label">平均利用率</div>
                </div>
              </el-col>
              <el-col :span="4">
                <div class="gpu-stat">
                  <div class="gpu-stat-value">{{ gpuInfo.average_temperature }}°C</div>
                  <div class="gpu-stat-label">平均温度</div>
                </div>
              </el-col>
              <el-col :span="4">
                <div class="gpu-stat">
                  <div class="gpu-stat-value">{{ gpuInfo.used_memory }} / {{ gpuInfo.total_memory }}</div>
                  <div class="gpu-stat-label">内存使用</div>
                </div>
              </el-col>
            </el-row>
          </div>
          
          <!-- GPU Cards -->
          <div v-if="gpuInfo && gpuInfo.gpu_list && gpuInfo.gpu_list.length > 0" class="gpu-cards">
            <el-row :gutter="20">
              <el-col :span="6" v-for="gpu in gpuInfo.gpu_list" :key="gpu.index">
                <div class="gpu-card">
                  <div class="gpu-card-header">
                    <span class="gpu-name">{{ gpu.name }}</span>
                    <el-tag size="small" :type="gpu.utilization > 80 ? 'danger' : gpu.utilization > 50 ? 'warning' : 'success'">
                      GPU {{ gpu.index }}
                    </el-tag>
                  </div>
                  <div class="gpu-card-body">
                    <el-progress 
                      type="circle" 
                      :percentage="gpu.memory_percent" 
                      :color="getGpuMemoryColor(gpu.memory_percent)"
                      :width="80"
                    >
                      <template #default="{ percentage }">
                        <div class="gpu-progress-text">
                          <span class="value">{{ percentage }}%</span>
                          <span class="label">显存</span>
                        </div>
                      </template>
                    </el-progress>
                    <div class="gpu-details">
                      <div class="gpu-detail-item">
                        <span class="label">利用率:</span>
                        <span class="value">{{ gpu.utilization }}%</span>
                      </div>
                      <div class="gpu-detail-item">
                        <span class="label">显存:</span>
                        <span class="value">{{ formatBytes(gpu.memory_used) }} / {{ formatBytes(gpu.memory_total) }}</span>
                      </div>
                      <div class="gpu-detail-item">
                        <span class="label">温度:</span>
                        <span class="value" :style="{ color: gpu.temperature > 80 ? '#f56c6c' : gpu.temperature > 60 ? '#e6a23c' : '#67c23a' }">
                          {{ gpu.temperature }}°C
                        </span>
                      </div>
                      <div class="gpu-detail-item">
                        <span class="label">功耗:</span>
                        <span class="value">{{ gpu.power_draw }}W / {{ gpu.power_limit }}W</span>
                      </div>
                      <div class="gpu-detail-item">
                        <span class="label">风扇:</span>
                        <span class="value">{{ gpu.fan_speed }}%</span>
                      </div>
                    </div>
                  </div>
                </div>
              </el-col>
            </el-row>
          </div>
          <el-empty v-if="!gpuLoading && (!gpuInfo || !gpuInfo.gpu_list || gpuInfo.gpu_list.length === 0)" description="未检测到GPU设备" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { Cpu, Monitor, Coin, Connection, Tickets, Box, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import * as echarts from 'echarts'

const loading = ref(false)
const dockerLoading = ref(false)
const refreshInterval = ref(10000)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const cpuChartRef = ref<HTMLElement>()
const memoryChartRef = ref<HTMLElement>()
let cpuChart: echarts.ECharts | null = null
let memoryChart: echarts.ECharts | null = null

const metrics = reactive({
  cpu: {
    percent: 0,
    cores: 0,
    speed: 0,
    load: ''
  },
  memory: {
    total: 0,
    used: 0,
    available: 0,
    percent: 0
  },
  disk: {
    total: 0,
    used: 0,
    free: 0,
    percent: 0
  },
  network: {
    bytes_sent: 0,
    bytes_recv: 0,
    packets_sent: 0,
    packets_recv: 0
  },
  system: {
    hostname: '',
    os: '',
    uptime: '',
    python_version: ''
  }
})

const dockerStats = ref<any[]>([])

// CPU history data
const cpuHistory = ref<{time: string, value: number}[]>([])
const memoryHistory = ref<{time: string, value: number}[]>([])

// Format bytes to human readable
const formatBytes = (bytes: number) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let index = 0
  let size = bytes
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index++
  }
  return size.toFixed(2) + ' ' + units[index]
}

// Format number with commas
const formatNumber = (num: number) => {
  if (!num) return '0'
  return num.toLocaleString()
}

// Get color based on percentage
const getCpuColor = (percent: number) => {
  if (percent < 50) return '#67c23a'
  if (percent < 80) return '#e6a23c'
  return '#f56c6c'
}

const getMemoryColor = (percent: number) => {
  if (percent < 60) return '#67c23a'
  if (percent < 85) return '#e6a23c'
  return '#f56c6c'
}

const getDiskColor = (percent: number) => {
  if (percent < 70) return '#67c23a'
  if (percent < 90) return '#e6a23c'
  return '#f56c6c'
}

const getDockerStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    'running': 'success',
    'exited': 'info',
    'paused': 'warning',
    'restarting': 'warning'
  }
  return typeMap[status] || 'info'
}

// Load system metrics
const loadMetrics = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/v1/system/monitor/metrics')
    const data = response.data
    
    // Update metrics
    metrics.cpu = data.cpu
    metrics.memory = data.memory
    metrics.disk = data.disk
    metrics.network = data.network
    metrics.system = data.system
    
    // Update history
    const now = new Date().toLocaleTimeString()
    cpuHistory.value.push({ time: now, value: data.cpu.percent })
    memoryHistory.value.push({ time: now, value: data.memory.percent })
    
    // Keep only last 30 data points
    if (cpuHistory.value.length > 30) {
      cpuHistory.value.shift()
    }
    if (memoryHistory.value.length > 30) {
      memoryHistory.value.shift()
    }
    
    // Update charts
    updateCharts()
    
  } catch (error) {
    console.error('Failed to load metrics:', error)
    // Use mock data for demo
    metrics.cpu = {
      percent: Math.floor(Math.random() * 40) + 20,
      cores: 8,
      speed: 3.6,
      load: '0.5, 0.8, 0.6'
    }
    metrics.memory = {
      total: 32 * 1024 * 1024 * 1024,
      used: 16 * 1024 * 1024 * 1024,
      available: 16 * 1024 * 1024 * 1024,
      percent: 50
    }
    metrics.disk = {
      total: 500 * 1024 * 1024 * 1024,
      used: 200 * 1024 * 1024 * 1024,
      free: 300 * 1024 * 1024 * 1024,
      percent: 40
    }
    metrics.network = {
      bytes_sent: 1024 * 1024 * 100,
      bytes_recv: 1024 * 1024 * 500,
      packets_sent: 10000,
      packets_recv: 15000
    }
    metrics.system = {
      hostname: 'e-claw-server',
      os: 'Linux 5.15.0',
      uptime: '5天 12小时 30分钟',
      python_version: '3.11.0'
    }
  } finally {
    loading.value = false
  }
}

// Load Docker stats
const loadDockerStats = async () => {
  dockerLoading.value = true
  try {
    const response = await axios.get('/api/v1/system/monitor/docker')
    dockerStats.value = response.data
  } catch (error) {
    console.error('Failed to load docker stats:', error)
    // Demo data
    dockerStats.value = [
      {
        name: 'e-claw-backend',
        image: 'e-claw/backend:latest',
        status: 'running',
        cpu_percent: 5.2,
        memory_percent: 12.5,
        created: '2024-01-15 10:00:00'
      },
      {
        name: 'e-claw-frontend',
        image: 'e-claw/frontend:latest',
        status: 'running',
        cpu_percent: 2.1,
        memory_percent: 8.3,
        created: '2024-01-15 10:00:00'
      }
    ]
  } finally {
    dockerLoading.value = false
  }
}

// K8s data
const k8sLoading = ref(false)
const k8sCluster = ref<any>(null)
const k8sPods = ref<any[]>([])

// GPU data
const gpuLoading = ref(false)
const gpuInfo = ref<any>(null)

// Get GPU memory color
const getGpuMemoryColor = (percent: number) => {
  if (percent < 50) return '#67c23a'
  if (percent < 80) return '#e6a23c'
  return '#f56c6c'
}

// Load GPU stats
const loadGpuStats = async () => {
  gpuLoading.value = true
  try {
    const response = await axios.get('/api/v1/system/monitor/gpu')
    gpuInfo.value = response.data
  } catch (error) {
    console.error('Failed to load GPU stats:', error)
    // Demo data
    gpuInfo.value = {
      total_gpus: 4,
      available_gpus: 2,
      used_gpus: 2,
      total_memory: '64 GiB',
      used_memory: '32 GiB',
      available_memory: '32 GiB',
      average_utilization: 45.5,
      average_temperature: 55.0,
      gpu_list: [
        {
          index: 0,
          name: 'NVIDIA A100-SXM4-40GB',
          uuid: 'GPU-12345678-1234-1234-1234-1234567890ab',
          memory_total: 42949672960,
          memory_used: 21474836480,
          memory_free: 21474836480,
          memory_percent: 50.0,
          utilization: 65.0,
          temperature: 58,
          power_draw: 180.5,
          power_limit: 400.0,
          fan_speed: 45,
          driver_version: '535.129.03',
          cuda_version: '12.2'
        },
        {
          index: 1,
          name: 'NVIDIA A100-SXM4-40GB',
          uuid: 'GPU-12345678-1234-1234-1234-1234567890ac',
          memory_total: 42949672960,
          memory_used: 17179869184,
          memory_free: 25769803776,
          memory_percent: 40.0,
          utilization: 35.0,
          temperature: 52,
          power_draw: 150.2,
          power_limit: 400.0,
          fan_speed: 40,
          driver_version: '535.129.03',
          cuda_version: '12.2'
        },
        {
          index: 2,
          name: 'NVIDIA A100-SXM4-40GB',
          uuid: 'GPU-12345678-1234-1234-1234-1234567890ad',
          memory_total: 42949672960,
          memory_used: 4294967296,
          memory_free: 38654705664,
          memory_percent: 10.0,
          utilization: 15.0,
          temperature: 48,
          power_draw: 80.0,
          power_limit: 400.0,
          fan_speed: 30,
          driver_version: '535.129.03',
          cuda_version: '12.2'
        },
        {
          index: 3,
          name: 'NVIDIA A100-SXM4-40GB',
          uuid: 'GPU-12345678-1234-1234-1234-1234567890ae',
          memory_total: 42949672960,
          memory_used: 0,
          memory_free: 42949672960,
          memory_percent: 0.0,
          utilization: 0.0,
          temperature: 45,
          power_draw: 35.0,
          power_limit: 400.0,
          fan_speed: 25,
          driver_version: '535.129.03',
          cuda_version: '12.2'
        }
      ]
    }
  } finally {
    gpuLoading.value = false
  }
}

// Get K8s status type
const getK8sStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    'Running': 'success',
    'Pending': 'warning',
    'Succeeded': 'success',
    'Failed': 'danger',
    'Unknown': 'info'
  }
  return typeMap[status] || 'info'
}

// Load K8s stats
const loadK8sStats = async () => {
  k8sLoading.value = true
  try {
    // Load cluster info
    const clusterResponse = await axios.get('/api/v1/system/monitor/k8s/cluster')
    k8sCluster.value = clusterResponse.data
    
    // Load pods
    const podsResponse = await axios.get('/api/v1/system/monitor/k8s/pods')
    k8sPods.value = podsResponse.data
  } catch (error) {
    console.error('Failed to load K8s stats:', error)
    // Demo data
    k8sCluster.value = {
      cluster_name: 'e-claw-cluster',
      version: 'v1.28.0',
      total_nodes: 3,
      ready_nodes: 3,
      running_pods: 12,
      total_namespaces: 8,
      cpu_capacity: '24 cores',
      memory_capacity: '64 Gi',
      cpu_used: '8 cores (33%)',
      memory_used: '32 Gi (50%)'
    }
    k8sPods.value = [
      {
        name: 'eclaw-openclaw-abc123',
        namespace: 'e-claw-system',
        status: 'Running',
        node_name: 'worker-node-1',
        pod_ip: '10.244.1.15',
        cpu_request: '500m',
        memory_request: '1Gi'
      },
      {
        name: 'eclaw-linux-def456',
        namespace: 'e-claw-system',
        status: 'Pending',
        node_name: 'worker-node-2',
        pod_ip: null,
        cpu_request: '1000m',
        memory_request: '2Gi'
      }
    ]
  } finally {
    k8sLoading.value = false
  }
}

// Handle interval change
const handleIntervalChange = (value: number) => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
  
  if (value > 0) {
    refreshTimer = setInterval(() => {
      loadMetrics()
      loadDockerStats()
    }, value)
  }
}

// Initialize charts
const initCharts = () => {
  // Initialize CPU chart
  if (cpuChartRef.value) {
    cpuChart = echarts.init(cpuChartRef.value)
    cpuChart.setOption({
      tooltip: {
        trigger: 'axis'
      },
      xAxis: {
        type: 'category',
        data: [],
        boundaryGap: false
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        axisLabel: {
          formatter: '{value}%'
        }
      },
      series: [{
        name: 'CPU使用率',
        type: 'line',
        smooth: true,
        data: [],
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.5)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.1)' }
          ])
        },
        lineStyle: {
          color: '#409eff',
          width: 2
        },
        itemStyle: {
          color: '#409eff'
        }
      }]
    })
  }
  
  // Initialize Memory chart
  if (memoryChartRef.value) {
    memoryChart = echarts.init(memoryChartRef.value)
    memoryChart.setOption({
      tooltip: {
        trigger: 'axis'
      },
      xAxis: {
        type: 'category',
        data: [],
        boundaryGap: false
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        axisLabel: {
          formatter: '{value}%'
        }
      },
      series: [{
        name: '内存使用率',
        type: 'line',
        smooth: true,
        data: [],
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(103, 194, 58, 0.5)' },
            { offset: 1, color: 'rgba(103, 194, 58, 0.1)' }
          ])
        },
        lineStyle: {
          color: '#67c23a',
          width: 2
        },
        itemStyle: {
          color: '#67c23a'
        }
      }]
    })
  }
}

// Update charts
const updateCharts = () => {
  if (cpuChart && cpuHistory.value.length > 0) {
    cpuChart.setOption({
      xAxis: {
        data: cpuHistory.value.map(item => item.time)
      },
      series: [{
        data: cpuHistory.value.map(item => item.value)
      }]
    })
  }
  
  if (memoryChart && memoryHistory.value.length > 0) {
    memoryChart.setOption({
      xAxis: {
        data: memoryHistory.value.map(item => item.time)
      },
      series: [{
        data: memoryHistory.value.map(item => item.value)
      }]
    })
  }
}

// Initialize
onMounted(() => {
  // Wait for DOM to be ready
  nextTick(() => {
    initCharts()
  })
  
  loadMetrics()
  loadDockerStats()
  loadK8sStats()
  loadGpuStats()
  
  // Set auto refresh
  if (refreshInterval.value > 0) {
    refreshTimer = setInterval(() => {
      loadMetrics()
      loadDockerStats()
      loadK8sStats()
      loadGpuStats()
    }, refreshInterval.value)
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.monitor-page {
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
  align-items: center;
}

.metrics-row {
  margin-bottom: 20px;
}

.metric-card {
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.card-header span {
  font-weight: 500;
}

.metric-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 0;
}

.metric-detail {
  margin-top: 20px;
  width: 100%;
  text-align: left;
}

.metric-detail p {
  margin: 8px 0;
  display: flex;
  justify-content: space-between;
}

.metric-detail span {
  color: #909399;
}

.network-stats, .system-info {
  padding: 10px 0;
}

.network-item, .info-item {
  display: flex;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}

.network-item:last-child, .info-item:last-child {
  border-bottom: none;
}

.network-item .label, .info-item .label {
  width: 120px;
  color: #909399;
}

.network-item .value, .info-item .value {
  flex: 1;
  font-weight: 500;
}

.chart-card {
  min-height: 250px;
}

.chart-container {
  height: 200px;
}

/* K8s styles */
.k8s-overview {
  padding: 10px 0;
}

.k8s-stat {
  text-align: center;
  padding: 15px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  color: white;
}

.k8s-stat-value {
  font-size: 28px;
  font-weight: bold;
}

.k8s-stat-label {
  font-size: 12px;
  margin-top: 5px;
  opacity: 0.9;
}

.k8s-info-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.k8s-info-item:last-child {
  border-bottom: none;
}

.k8s-info-item .label {
  width: 100px;
  color: #909399;
}

.k8s-info-item .value {
  flex: 1;
  font-weight: 500;
}

/* GPU styles */
.gpu-overview {
  padding: 10px 0;
}

.gpu-stat {
  text-align: center;
  padding: 15px;
  background: linear-gradient(135deg, #00d9ff 0%, #00ff9d 100%);
  border-radius: 8px;
  color: white;
}

.gpu-stat-value {
  font-size: 24px;
  font-weight: bold;
}

.gpu-stat-label {
  font-size: 12px;
  margin-top: 5px;
  opacity: 0.9;
}

.gpu-cards {
  margin-top: 20px;
}

.gpu-card {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e8eb 100%);
  border-radius: 12px;
  padding: 15px;
  margin-bottom: 10px;
  border: 1px solid #e0e0e0;
}

.gpu-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e0e0e0;
}

.gpu-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
}

.gpu-card-body {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.gpu-progress-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1.2;
}

.gpu-progress-text .value {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.gpu-progress-text .label {
  font-size: 10px;
  color: #909399;
}

.gpu-details {
  width: 100%;
  margin-top: 15px;
}

.gpu-detail-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 12px;
}

.gpu-detail-item .label {
  color: #909399;
}

.gpu-detail-item .value {
  font-weight: 500;
  color: #303133;
}
</style>
