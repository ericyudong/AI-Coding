<template>
  <div class="page">
    <div class="head">
      <h2>ERP / 订单同步</h2>
      <div class="actions">
        <el-upload :show-file-list="false" accept=".csv" :http-request="onImport">
          <el-button type="primary" :loading="importing">导入 CSV</el-button>
        </el-upload>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>
    <p class="desc">
      当前模式：CSV 定期导入（可配置 ERP_SYNC_MODE=api 预留实时对接）。表头支持：
      order_no / customer_name / contract_code / product_name / qty / unit_price / amount / order_date
    </p>

    <h3>最近同步任务</h3>
    <el-table :data="jobs" size="small" style="margin-bottom: 20px">
      <el-table-column prop="filename" label="文件" min-width="140" />
      <el-table-column prop="status" label="状态" width="90" />
      <el-table-column prop="row_count" label="行数" width="80" />
      <el-table-column prop="linked_count" label="已关联" width="80" />
      <el-table-column prop="created_at" label="时间" width="170">
        <template #default="{ row }">{{ row.created_at?.slice(0, 19) }}</template>
      </el-table-column>
    </el-table>

    <h3>订单列表</h3>
    <div class="filters">
      <el-select v-model="linkFilter" clearable placeholder="关联状态" style="width: 140px" @change="loadOrders">
        <el-option label="已关联" value="linked" />
        <el-option label="待关联" value="pending" />
        <el-option label="人工关联" value="manual" />
      </el-select>
    </div>
    <el-table v-loading="loading" :data="orders" stripe>
      <el-table-column prop="order_no" label="订单号" width="120" />
      <el-table-column prop="customer_name" label="客户" min-width="120" />
      <el-table-column prop="contract_code" label="合同编号" width="120" />
      <el-table-column prop="product_name" label="产品" min-width="120" />
      <el-table-column prop="amount" label="金额" width="100" />
      <el-table-column prop="link_status" label="关联" width="90" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="manualLink(row)">人工关联</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadRequestOptions } from 'element-plus'
import {
  fetchErpOrders,
  fetchErpSyncJobs,
  importErpOrders,
  linkErpOrder,
  type ErpOrder,
} from '@/api/prd'

const loading = ref(false)
const importing = ref(false)
const orders = ref<ErpOrder[]>([])
const jobs = ref<Array<{ id: number; filename: string; status: string; row_count: number; linked_count: number; created_at: string | null }>>([])
const linkFilter = ref<string | undefined>()

async function loadOrders() {
  loading.value = true
  try {
    orders.value = await fetchErpOrders({ link_status: linkFilter.value })
  } finally {
    loading.value = false
  }
}

async function load() {
  jobs.value = await fetchErpSyncJobs().catch(() => [])
  await loadOrders()
}

async function onImport(opt: UploadRequestOptions) {
  importing.value = true
  try {
    const res = await importErpOrders(opt.file as File)
    ElMessage.success(`导入 ${res.row_count} 行，自动关联 ${res.linked_count}`)
    if (res.errors?.length) ElMessage.warning(res.errors[0])
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导入失败')
  } finally {
    importing.value = false
  }
}

async function manualLink(row: ErpOrder) {
  try {
    const { value: cid } = await ElMessageBox.prompt('客户 ID（可留空）', '人工关联', {
      inputValue: row.customer_id ? String(row.customer_id) : '',
    })
    const { value: ctid } = await ElMessageBox.prompt('合同 ID（可留空）', '人工关联', {
      inputValue: row.contract_id ? String(row.contract_id) : '',
    })
    await linkErpOrder(row.id, {
      customer_id: cid ? Number(cid) : null,
      contract_id: ctid ? Number(ctid) : null,
    })
    ElMessage.success('已更新关联')
    await loadOrders()
  } catch {
    /* cancel */
  }
}

onMounted(load)
</script>

<style scoped>
.page { padding: 24px; }
.head { display: flex; justify-content: space-between; align-items: center; }
.actions { display: flex; gap: 8px; }
.desc { color: #64748b; font-size: 13px; margin: 8px 0 16px; }
.filters { margin-bottom: 10px; }
</style>
