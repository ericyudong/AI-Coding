<template>
  <div class="cms-page">
    <div class="page-header">
      <div>
        <h1>合同台账</h1>
        <p class="subtitle">管理所有合同信息，支持多维筛选与批量操作</p>
      </div>
      <div class="actions">
        <el-button @click="$router.push('/cms/search')">🔍 搜索</el-button>
        <el-button @click="onExport">📥 导出</el-button>
        <el-button type="primary" @click="showCreate = true">➕ 新建合同</el-button>
      </div>
    </div>

    <div class="cms-stat-grid">
      <div v-for="s in statCards" :key="s.label" class="cms-stat-card">
        <div class="cms-stat-label">{{ s.label }}</div>
        <div class="cms-stat-number" :style="s.color ? { color: s.color } : undefined">{{ s.value }}</div>
        <div v-if="s.hint" class="stat-hint">{{ s.hint }}</div>
      </div>
    </div>

    <div class="cms-card">
      <div class="cms-card-body">
        <div class="toolbar">
          <el-input v-model="query" placeholder="搜索合同名称、编号、签约主体..." clearable @keyup.enter="load" @clear="load">
            <template #prefix>🔍</template>
          </el-input>
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button label="table">表格</el-radio-button>
            <el-radio-button label="card">卡片</el-radio-button>
          </el-radio-group>
        </div>

        <div class="filter-bar">
          <button
            v-for="f in filters"
            :key="f.key"
            type="button"
            class="cms-filter-chip"
            :class="{ active: statusFilter === f.key }"
            @click="statusFilter = f.key; load()"
          >
            {{ f.label }} <span class="badge">{{ f.count }}</span>
          </button>
        </div>

        <div v-if="selectedRows.length" class="batch-bar">
          <span class="batch-hint">已选 {{ selectedRows.length }} 条</span>
          <el-select v-model="batchStatus" placeholder="修改为..." style="width: 140px" clearable>
            <el-option v-for="(label, key) in STATUS_MAP" :key="key" :label="label" :value="key" />
          </el-select>
          <el-button type="primary" :disabled="!batchStatus" :loading="batching" @click="onBatchStatus">
            批量修改状态
          </el-button>
          <el-button link @click="clearSelection">取消选择</el-button>
        </div>

        <el-table
          v-if="viewMode === 'table'"
          ref="tableRef"
          v-loading="loading"
          :data="contracts"
          @row-click="onRowClick"
          @selection-change="onSelectionChange"
        >
          <el-table-column type="selection" width="40" />
          <el-table-column prop="name" label="合同名称" min-width="160">
            <template #default="{ row }"><strong>{{ row.name }}</strong></template>
          </el-table-column>
          <el-table-column prop="code" label="编号" width="130" />
          <el-table-column label="类型" width="100">
            <template #default="{ row }"><span class="cms-tag cms-tag-blue">{{ TYPE_MAP[row.contract_type] }}</span></template>
          </el-table-column>
          <el-table-column label="金额" width="120">
            <template #default="{ row }">{{ formatAmount(row.amount) }}</template>
          </el-table-column>
          <el-table-column prop="party_b" label="签约主体" min-width="140" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <span class="cms-status" :class="statusClass(row.status)"><span class="dot" />{{ STATUS_MAP[row.status] }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="expire_date" label="到期日" width="110" />
          <el-table-column label="标签" min-width="160">
            <template #default="{ row }">
              <span v-for="t in row.tags.slice(0, 2)" :key="t" class="cms-tag" :class="tagClass(t)">{{ t }}</span>
              <span v-if="row.tags.length > 2" class="cms-tag cms-tag-gray">+{{ row.tags.length - 2 }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="goDetail(row)">详情</el-button>
              <el-button link @click.stop="onDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-else class="card-grid">
          <div v-for="c in contracts" :key="c.id" class="contract-card" @click="goDetail(c)">
            <div class="card-title">
              <span>{{ c.name }}</span>
              <span class="cms-status" :class="statusClass(c.status)"><span class="dot" />{{ STATUS_MAP[c.status] }}</span>
            </div>
            <div class="card-meta">
              <span>📄 {{ c.code }}</span>
              <span>💰 {{ formatAmount(c.amount) }}</span>
              <span>🤝 {{ c.party_b }}</span>
              <span>📅 {{ c.expire_date || '-' }}</span>
            </div>
            <div class="card-tags">
              <span v-for="t in c.tags" :key="t" class="cms-tag" :class="tagClass(t)">{{ t }}</span>
            </div>
          </div>
        </div>

        <div class="pagination">
          <span>共 {{ total }} 条</span>
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="prev, pager, next"
            @current-change="load"
          />
        </div>
      </div>
    </div>

    <el-dialog v-model="showCreate" title="新建合同" width="640px">
      <el-form label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="合同名称" required><el-input v-model="form.name" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="合同类型">
              <el-select v-model="form.contract_type" style="width:100%">
                <el-option v-for="(label, key) in TYPE_MAP" :key="key" :label="label" :value="key" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="甲方"><el-input v-model="form.party_a" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="乙方"><el-input v-model="form.party_b" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="合同金额"><el-input-number v-model="form.amount" :min="0" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="负责人"><el-input v-model="form.owner" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="签署日期"><el-date-picker v-model="form.sign_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="生效日期"><el-date-picker v-model="form.effective_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="到期日期"><el-date-picker v-model="form.expire_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="onCreate">创建合同</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { TableInstance } from 'element-plus'
import {
  batchUpdateContracts,
  createContract,
  deleteContract,
  exportContractsCsv,
  fetchCmsStats,
  fetchContracts,
  formatAmount,
  STATUS_MAP,
  TYPE_MAP,
  type ContractItem,
  type ContractStats,
} from '@/api/cms'
import { statusClass, tagClass } from '@/utils/cmsHelpers'

const router = useRouter()
const loading = ref(false)
const contracts = ref<ContractItem[]>([])
const stats = ref<ContractStats | null>(null)
const query = ref('')
const statusFilter = ref('')
const viewMode = ref<'table' | 'card'>('table')
const page = ref(1)
const pageSize = 10
const total = ref(0)
const showCreate = ref(false)
const tableRef = ref<TableInstance>()
const selectedRows = ref<ContractItem[]>([])
const batchStatus = ref('')
const batching = ref(false)
const form = reactive({
  name: '',
  contract_type: 'purchase',
  party_a: '益慧科技有限公司',
  party_b: '',
  amount: 0,
  owner: '',
  sign_date: '',
  effective_date: '',
  expire_date: '',
})

const statCards = computed(() => {
  const s = stats.value
  if (!s) return []
  return [
    { label: '📄 合同总数', value: s.total, hint: '↑ 本月新增' },
    { label: '📌 履行中', value: s.active, hint: '↑ 较上月' },
    { label: '⚠️ 即将到期 (30天内)', value: s.expiring_soon, hint: '🔔 需关注', color: '#f59e0b' },
    { label: '🔴 高风险', value: s.high_risk, hint: '建议优先审查', color: '#ef4444' },
  ]
})

const filters = computed(() => {
  const s = stats.value
  return [
    { key: '', label: '全部', count: s?.total || 0 },
    { key: 'active', label: '履行中', count: s?.active || 0 },
    { key: 'pending_sign', label: '待签署', count: s?.pending_sign || 0 },
    { key: 'expired', label: '已到期', count: s?.expired || 0 },
    { key: 'archived', label: '已归档', count: s?.archived || 0 },
  ]
})

onMounted(async () => {
  stats.value = await fetchCmsStats()
  await load()
})

async function load() {
  loading.value = true
  try {
    const data = await fetchContracts({
      q: query.value,
      status: statusFilter.value,
      page: page.value,
      page_size: pageSize,
    })
    contracts.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function goDetail(row: ContractItem) {
  router.push(`/cms/contracts/${row.id}`)
}

function onRowClick(row: ContractItem, _column: unknown, event: MouseEvent) {
  if ((event.target as HTMLElement).closest('.el-checkbox')) return
  goDetail(row)
}

function onSelectionChange(rows: ContractItem[]) {
  selectedRows.value = rows
  if (!rows.length) batchStatus.value = ''
}

function clearSelection() {
  tableRef.value?.clearSelection()
  batchStatus.value = ''
}

async function onBatchStatus() {
  if (!batchStatus.value || !selectedRows.value.length) return
  const count = selectedRows.value.length
  const label = STATUS_MAP[batchStatus.value] || batchStatus.value
  await ElMessageBox.confirm(`将选中的 ${count} 份合同状态修改为「${label}」？`, '批量修改状态')
  batching.value = true
  try {
    const res = await batchUpdateContracts({
      ids: selectedRows.value.map((r) => r.id),
      status: batchStatus.value,
    })
    ElMessage.success(`已更新 ${res.updated} 份合同`)
    clearSelection()
    stats.value = await fetchCmsStats()
    await load()
  } catch {
    /* 用户取消或请求失败 */
  } finally {
    batching.value = false
  }
}

async function onCreate() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入合同名称')
    return
  }
  await createContract({ ...form })
  showCreate.value = false
  ElMessage.success('合同已创建')
  stats.value = await fetchCmsStats()
  await load()
}

async function onDelete(row: ContractItem) {
  await ElMessageBox.confirm(`确定删除「${row.name}」？`, '确认')
  await deleteContract(row.id)
  ElMessage.success('已删除')
  stats.value = await fetchCmsStats()
  await load()
}

async function onExport() {
  const { blob, filename } = await exportContractsCsv()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0;
  font-size: 26px;
  color: #1e1b4b;
}

.subtitle {
  margin: 4px 0 0;
  color: var(--cms-muted);
  font-size: 14px;
}

.actions {
  display: flex;
  gap: 8px;
}

.stat-hint {
  font-size: 13px;
  color: var(--cms-muted);
  margin-top: 6px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.filter-bar .badge {
  background: rgba(79, 70, 229, 0.1);
  padding: 0 6px;
  border-radius: 10px;
  font-size: 11px;
}

.batch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 10px 14px;
  background: #eef2ff;
  border-radius: 8px;
  border: 1px solid rgba(79, 70, 229, 0.2);
}

.batch-hint {
  font-size: 13px;
  font-weight: 500;
  color: #4338ca;
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  font-size: 13px;
  color: var(--cms-muted);
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.contract-card {
  border: 1px solid var(--cms-border);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.contract-card:hover {
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
}

.card-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  margin-bottom: 8px;
}

.card-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--cms-muted);
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 10px;
}
</style>
