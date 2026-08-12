<template>
  <div class="page">
    <div class="head">
      <h2>标签体系</h2>
      <el-button type="primary" @click="openCreate(1)">新增一级标签</el-button>
    </div>
    <p class="desc">配置合同智能标签的一/二/三级字典；合同详情编辑时将校验一级、二级是否在体系内。</p>

    <el-table v-loading="loading" :data="flatRows" row-key="id" border default-expand-all>
      <el-table-column prop="name" label="名称" min-width="200">
        <template #default="{ row }">
          <span :style="{ paddingLeft: `${(row.level - 1) * 16}px` }">{{ row.name }}</span>
          <el-tag size="small" style="margin-left: 8px">L{{ row.level }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column prop="sort_order" label="排序" width="80" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active === false ? 'info' : 'success'" size="small">
            {{ row.is_active === false ? '停用' : '启用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <el-button v-if="row.level < 3" link type="primary" @click="openCreate(row.level + 1, row.id)">子级</el-button>
          <el-button link @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="onDelete(row.id)">停用</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑标签' : '新建标签'" width="420px">
      <el-form label-width="80px">
        <el-form-item label="层级">
          <el-input-number v-model="form.level" :min="1" :max="3" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="编码">
          <el-input v-model="form.code" placeholder="可选" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createAdminTag,
  deleteAdminTag,
  fetchAdminTags,
  updateAdminTag,
  type TagTaxonomyNode,
} from '@/api/cms'

const loading = ref(false)
const saving = ref(false)
const flatRows = ref<TagTaxonomyNode[]>([])
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = ref({ level: 1, name: '', code: '', parent_id: null as number | null, sort_order: 0 })

function flatten(nodes: TagTaxonomyNode[], out: TagTaxonomyNode[] = []) {
  for (const n of nodes) {
    out.push(n)
    if (n.children?.length) flatten(n.children, out)
  }
  return out
}

async function load() {
  loading.value = true
  try {
    const tree = await fetchAdminTags({ tree: true, all: true })
    flatRows.value = flatten(tree)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate(level: number, parentId: number | null = null) {
  editingId.value = null
  form.value = { level, name: '', code: '', parent_id: parentId, sort_order: 0 }
  dialogVisible.value = true
}

function openEdit(row: TagTaxonomyNode) {
  editingId.value = row.id
  form.value = {
    level: row.level,
    name: row.name,
    code: row.code,
    parent_id: row.parent_id,
    sort_order: row.sort_order,
  }
  dialogVisible.value = true
}

async function save() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateAdminTag(editingId.value, {
        name: form.value.name,
        code: form.value.code,
        sort_order: form.value.sort_order,
      })
    } else {
      await createAdminTag(form.value)
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function onDelete(id: number) {
  await ElMessageBox.confirm('确认停用该标签及其子级？', '提示')
  await deleteAdminTag(id)
  ElMessage.success('已停用')
  await load()
}

onMounted(load)
</script>

<style scoped>
.page { padding: 24px; }
.head { display: flex; justify-content: space-between; align-items: center; }
.desc { color: #64748b; font-size: 13px; margin: 8px 0 16px; }
</style>
