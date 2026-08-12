<template>
  <div class="page">
    <h2>供应商中心</h2>
    <p class="desc">自动归集供应商合作金额、次数与风险标记，支持画像浏览。</p>
    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="name" label="供应商" min-width="180" />
      <el-table-column prop="industry" label="行业" width="120" />
      <el-table-column prop="contract_count" label="合同数" width="90" />
      <el-table-column label="合作金额" width="140">
        <template #default="{ row }">{{ formatAmount(row.total_amount) }}</template>
      </el-table-column>
      <el-table-column prop="delay_count" label="延期次数" width="100" />
      <el-table-column prop="risk_level" label="风险" width="90" />
      <el-table-column prop="contact" label="联系方式" min-width="120" />
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchSuppliers, type Supplier } from '@/api/prd'

const loading = ref(false)
const rows = ref<Supplier[]>([])

function formatAmount(n: number) {
  if (n >= 100000000) return `${(n / 100000000).toFixed(2)}亿`
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return String(n)
}

onMounted(async () => {
  loading.value = true
  try {
    rows.value = await fetchSuppliers()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page { padding: 24px; }
.desc { color: #64748b; font-size: 14px; margin-bottom: 16px; }
</style>
