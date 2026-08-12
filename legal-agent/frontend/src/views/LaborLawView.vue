<template>
  <ChatPanel
    module="labor_law"
    title="劳动法"
    subtitle="一键直达精准答案，支持真实数据溯源"
    :examples="examples"
  />
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import ChatPanel from '@/components/ChatPanel.vue'
import { fetchLaborExamples } from '@/api/legal'

const examples = ref<string[]>([])

onMounted(async () => {
  examples.value = await fetchLaborExamples()
})
</script>
