<template>
  <div class="ops-dashboard">
    <el-row :gutter="20">
      <el-col :span="24">
        <h1>运维管理</h1>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" class="ops-cards">
      <el-col :span="8">
        <el-card class="ops-card" @click="$router.push('/ops/service-config')">
          <div class="card-content">
            <el-icon :size="48" color="#409eff"><Setting /></el-icon>
            <h3>服务配置</h3>
            <p>配置LLM、RAG、MCP等服务参数</p>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="ops-card" @click="$router.push('/ops/monitor')">
          <div class="card-content">
            <el-icon :size="48" color="#67c23a"><Monitor /></el-icon>
            <h3>系统监控</h3>
            <p>监控系统运行状态和资源使用</p>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="ops-card" @click="$router.push('/ops/logs')">
          <div class="card-content">
            <el-icon :size="48" color="#e6a23c"><Document /></el-icon>
            <h3>日志查看</h3>
            <p>查看系统运行日志</p>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { Setting, Monitor, Document } from '@element-plus/icons-vue'
</script>

<style scoped>
.ops-dashboard {
  padding: 20px;
}

h1 {
  margin-bottom: 30px;
  color: #303133;
}

.ops-cards {
  margin-top: 20px;
}

.ops-card {
  cursor: pointer;
  transition: all 0.3s;
}

.ops-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.card-content {
  text-align: center;
  padding: 20px;
}

.card-content h3 {
  margin: 15px 0 10px;
  color: #303133;
}

.card-content p {
  color: #909399;
  font-size: 14px;
}
</style>