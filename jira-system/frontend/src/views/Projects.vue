<template>
  <div class="projects-page">
    <div class="header">
      <h1>Projects</h1>
      <Button label="New Project" icon="pi pi-plus" @click="showCreateDialog = true" />
    </div>
    
    <div class="projects-grid">
      <Card v-for="project in projects" :key="project.id" class="project-card" @click="goToProject(project.id)">
        <template #title>{{ project.name }}</template>
        <template #subtitle>{{ project.key }}</template>
        <template #content>
          <p>{{ project.description || 'No description' }}</p>
        </template>
      </Card>
    </div>
    
    <Dialog v-model:visible="showCreateDialog" header="Create Project" :style="{ width: '400px' }">
      <div class="form-field">
        <label>Name</label>
        <InputText v-model="newProject.name" class="w-full" />
      </div>
      <div class="form-field">
        <label>Key</label>
        <InputText v-model="newProject.key" class="w-full" placeholder="e.g., PROJ" />
      </div>
      <div class="form-field">
        <label>Description</label>
        <Textarea v-model="newProject.description" class="w-full" rows="3" />
      </div>
      <template #footer>
        <Button label="Cancel" text @click="showCreateDialog = false" />
        <Button label="Create" @click="createProject" :loading="creating" />
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'

const router = useRouter()

const projects = ref<any[]>([])
const showCreateDialog = ref(false)
const creating = ref(false)
const newProject = ref({ name: '', key: '', description: '' })

const fetchProjects = async () => {
  const response = await api.get('/projects')
  projects.value = response.data
}

const createProject = async () => {
  if (!newProject.value.name || !newProject.value.key) return
  
  creating.value = true
  try {
    await api.post('/projects', newProject.value)
    showCreateDialog.value = false
    newProject.value = { name: '', key: '', description: '' }
    await fetchProjects()
  } finally {
    creating.value = false
  }
}

const goToProject = (id: string) => {
  router.push(`/projects/${id}`)
}

onMounted(fetchProjects)
</script>

<style scoped>
.projects-page {
  padding: 1rem;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.project-card {
  cursor: pointer;
  transition: transform 0.2s;
}

.project-card:hover {
  transform: translateY(-2px);
}

.form-field {
  margin-bottom: 1rem;
}

.form-field label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.w-full {
  width: 100%;
}
</style>