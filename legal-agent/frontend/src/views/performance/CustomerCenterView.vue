<template>
  <div class="page">
    <div class="head">
      <div>
        <h2>客户中心</h2>
        <p class="desc">客户画像、销售额汇总；支持关联公司合并归集视图。</p>
      </div>
      <el-radio-group v-model="merged" @change="load">
        <el-radio-button :value="false">独立视图</el-radio-button>
        <el-radio-button :value="true">合并视图</el-radio-button>
      </el-radio-group>
    </div>

    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="name" label="客户" min-width="180" />
      <el-table-column prop="industry" label="行业" width="120" />
      <el-table-column prop="contract_count" label="合同" width="80" />
      <el-table-column prop="order_count" label="订单" width="80" />
      <el-table-column label="累计销售额" width="140">
        <template #default="{ row }">{{ formatAmount(row.total_sales) }}</template>
      </el-table-column>
      <el-table-column prop="payment_delay_count" label="回款延迟" width="100" />
      <el-table-column prop="risk_level" label="风险" width="80" />
      <el-table-column label="关联公司" min-width="160">
        <template #default="{ row }">
          <span v-if="!row.related?.length">—</span>
          <el-tag v-for="r in row.related" :key="r.id" size="small" style="margin: 2px">{{ r.name }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button link type="primary" @click="relate(row)">添加关联</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { addCustomerRelation, fetchCustomers, type Customer } from '@/api/prd'

const loading = ref(false)
const merged = ref(false)
const rows = ref<Customer[]>([])

function formatAmount(n: number) {
  if (n >= 100000000) return `${(n / 100000000).toFixed(2)}亿`
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return String(n)
}

async function load() {
  loading.value = true
  try {
    rows.value = await fetchCustomers(merged.value)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function relate(row: Customer) {
  const others = rows.value.filter((r) => r.id !== row.id)
  if (!others.length) {
    ElMessage.warning('暂无其他客户可关联')
    return
  }
  try {
    const { value } = await ElMessageBox.prompt(
      `输入要关联的客户 ID（可选：${others.map((o) => `${o.id}:${o.name}`).join('；')}）`,
      '添加关联公司',
    )
    const relatedId = Number(value)
    if (!relatedId) return
    await addCustomerRelation(row.id, relatedId, 'sibling', 1)
    ElMessage.success('关联成功')
    await load()
  } catch {
    /* cancel */
  }
}

onMounted(load)
</script>

<style scoped>
.page { padding: 24px; }
.head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; gap: 16px; }
.desc { color: #64748b; font-size: 14px; margin: 4px 0 0; }
</style>
