<template>
  <div class="page">
    <h2>知识资产AI · 企业知识问答</h2>
    <p class="desc">基于企业合同与知识库的自然语言问答，回答将尽量引用真实合同内容。</p>
    <ChatPanel module="qa" title="企业知识问答" subtitle="支持多轮对话 · 引用溯源" :examples="examples" />
    <div class="kb-links">
      <RouterLink to="/cms/ledger">合同库</RouterLink>
      <RouterLink to="/performance/suppliers">供应商库</RouterLink>
      <RouterLink to="/performance/customers">客户库</RouterLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import ChatPanel from '@/components/ChatPanel.vue'
import { fetchWorkbenchRecommendations } from '@/api/prd'

const examples = ref([
  '公司以前签过类似的软件采购合同吗？',
  '我们通常如何约定知识产权归属？',
  '去年采购合同共有多少份？',
])

onMounted(async () => {
  try {
    const rec = await fetchWorkbenchRecommendations()
    if (rec.questions?.length) examples.value = rec.questions
  } catch {
    /* keep defaults */
  }
})
</script>

<style scoped>
.page {
  padding: 24px;
  max-width: 960px;
}
.desc {
  color: #64748b;
  font-size: 14px;
  margin: 0 0 16px;
}
.kb-links {
  margin-top: 20px;
  display: flex;
  gap: 16px;
}
.kb-links a {
  color: #0f766e;
  font-size: 13px;
}
</style>
