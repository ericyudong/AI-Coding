<template>
  <div class="project-page">
    <div class="header">
      <div>
        <Button icon="pi pi-arrow-left" text @click="$router.push('/projects')" />
        <h1>{{ project?.name }}</h1>
      </div>
      <Button label="Create Issue" icon="pi pi-plus" @click="showCreateDialog = true" />
    </div>
    
    <TabView>
      <TabPanel header="Board">
        <div class="board">
          <div v-for="status in statuses" :key="status" class="column">
            <h3>{{ statusLabels[status] }}</h3>
            <div class="column-content">
              <Card v-for="issue in getIssuesByStatus(status)" :key="issue.id" class="issue-card">
                <template #title>
                  <div class="issue-title-row">
                    <span @click="goToIssue(issue.id)" class="issue-key">{{ issue.key }}</span>
                    <Button icon="pi pi-trash" text rounded severity="danger" size="small" @click="confirmDeleteIssue(issue)" />
                  </div>
                </template>
                <template #content>
                  <p @click="goToIssue(issue.id)">{{ issue.title }}</p>
                  <div class="issue-meta">
                    <Tag :value="issue.priority" :severity="getPrioritySeverity(issue.priority)" />
                    <Tag :value="issue.issue_type" />
                  </div>
                </template>
              </Card>
            </div>
          </div>
        </div>
      </TabPanel>
      <TabPanel header="List">
        <DataTable :value="issues" tableStyle="min-width: 50rem">
          <Column field="key" header="Key" />
          <Column field="title" header="Title" />
          <Column field="status" header="Status">
            <template #body="{ data }">
              <Dropdown v-model="data.status" :options="statuses" @change="updateIssueStatus(data)" class="status-dropdown" />
            </template>
          </Column>
          <Column field="priority" header="Priority">
            <template #body="{ data }">
              <Tag :value="data.priority" :severity="getPrioritySeverity(data.priority)" />
            </template>
          </Column>
          <Column field="assignee" header="Assignee">
            <template #body="{ data }">
              {{ data.assignee?.username || 'Unassigned' }}
            </template>
          </Column>
          <Column header="Actions">
            <template #body="{ data }">
              <Button icon="pi pi-trash" text rounded severity="danger" @click="confirmDeleteIssue(data)" />
            </template>
          </Column>
        </DataTable>
      </TabPanel>
      <TabPanel header="Settings">
        <p>Project settings coming soon...</p>
      </TabPanel>
    </TabView>
    
    <Dialog v-model:visible="showCreateDialog" header="Create Issue" :style="{ width: '500px' }">
      <div class="form-field">
        <label>Title</label>
        <InputText v-model="newIssue.title" class="w-full" />
      </div>
      <div class="form-field">
        <label>Description</label>
        <Textarea v-model="newIssue.description" class="w-full" rows="4" />
      </div>
      <div class="form-row">
        <div class="form-field">
          <label>Type</label>
          <Dropdown v-model="newIssue.issue_type" :options="issueTypes" class="w-full" />
        </div>
        <div class="form-field">
          <label>Priority</label>
          <Dropdown v-model="newIssue.priority" :options="priorities" class="w-full" />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" text @click="showCreateDialog = false" />
        <Button label="Create" @click="createIssue" :loading="creating" />
      </template>
    </Dialog>
    
    <Dialog v-model:visible="showDeleteDialog" header="Delete Issue" :style="{ width: '400px' }">
      <p>Are you sure you want to delete issue <strong>{{ issueToDelete?.key }}</strong>?</p>
      <p>{{ issueToDelete?.title }}</p>
      <template #footer>
        <Button label="Cancel" text @click="showDeleteDialog = false" />
        <Button label="Delete" severity="danger" @click="deleteIssue" :loading="deleting" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Dropdown from 'primevue/dropdown'

const route = useRoute()

const project = ref<any>(null)
const issues = ref<any[]>([])
const showCreateDialog = ref(false)
const creating = ref(false)
const newIssue = ref({ title: '', description: '', issue_type: 'task', priority: 'medium' })

// Delete issue state
const showDeleteDialog = ref(false)
const issueToDelete = ref<any>(null)
const deleting = ref(false)

const statuses = ['todo', 'in_progress', 'in_review', 'done']
const statusLabels: Record<string, string> = {
  todo: 'To Do',
  in_progress: 'In Progress',
  in_review: 'In Review',
  done: 'Done'
}

const issueTypes = ['task', 'bug', 'story', 'epic']
const priorities = ['low', 'medium', 'high', 'critical']

const fetchProject = async () => {
  const response = await api.get(`/projects/${route.params.id}`)
  project.value = response.data
}

const fetchIssues = async () => {
  const response = await api.get(`/projects/${route.params.id}/issues`)
  issues.value = response.data
}

const getIssuesByStatus = (status: string) => {
  return issues.value.filter(i => i.status === status)
}

const getPrioritySeverity = (priority: string) => {
  const map: Record<string, string> = {
    low: 'info',
    medium: 'warning',
    high: 'danger',
    critical: 'danger'
  }
  return map[priority] || 'info'
}

const createIssue = async () => {
  if (!newIssue.value.title) return
  
  creating.value = true
  try {
    await api.post(`/projects/${route.params.id}/issues`, newIssue.value)
    showCreateDialog.value = false
    newIssue.value = { title: '', description: '', issue_type: 'task', priority: 'medium' }
    await fetchIssues()
  } finally {
    creating.value = false
  }
}

const goToIssue = (id: string) => {
  // Navigate to issue detail
}

const confirmDeleteIssue = (issue: any) => {
  issueToDelete.value = issue
  showDeleteDialog.value = true
}

const deleteIssue = async () => {
  if (!issueToDelete.value) return
  
  deleting.value = true
  try {
    await api.delete(`/issues/${issueToDelete.value.id}`)
    showDeleteDialog.value = false
    issueToDelete.value = null
    await fetchIssues()
  } finally {
    deleting.value = false
  }
}

const updateIssueStatus = async (issue: any) => {
  await api.patch(`/issues/${issue.id}`, { status: issue.status })
  await fetchIssues()
}

onMounted(() => {
  fetchProject()
  fetchIssues()
})
</script>

<style scoped>
.project-page {
  padding: 1rem;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.header > div {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.board {
  display: flex;
  gap: 1rem;
  overflow-x: auto;
  padding: 1rem 0;
}

.column {
  min-width: 250px;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 1rem;
}

.column h3 {
  margin-bottom: 1rem;
  font-size: 0.9rem;
  color: #666;
}

.column-content {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.issue-card {
  cursor: pointer;
}

.issue-meta {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.form-field {
  margin-bottom: 1rem;
}

.form-field label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.form-row {
  display: flex;
  gap: 1rem;
}

.form-row .form-field {
  flex: 1;
}

.w-full {
  width: 100%;
}

.issue-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.issue-key {
  cursor: pointer;
  color: #2563eb;
}

.issue-key:hover {
  text-decoration: underline;
}

.issue-card :deep(.p-card-content) {
  cursor: pointer;
}

.status-dropdown {
  min-width: 120px;
}
</style>
