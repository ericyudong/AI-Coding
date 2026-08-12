<template>
  <ChatPanel :module="module" :title="title" :examples="defaultExamples" />
</template>

<script setup lang="ts">
import ChatPanel from '@/components/ChatPanel.vue'

defineProps<{
  module: string
  title: string
}>()

const defaultExamples = [
  '企业对外担保需要经过哪些内部决策程序？',
  '跨境电商业务涉及哪些主要合规风险？',
  '境外子公司设立需要关注哪些法律问题？',
]
</script>
