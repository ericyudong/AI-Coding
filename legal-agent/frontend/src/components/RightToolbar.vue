<template>
  <aside class="right-toolbar">
    <button v-for="item in items" :key="item.label" type="button" class="tool-item" :title="item.label">
      <span class="tool-icon">{{ item.icon }}</span>
      <span class="tool-label">{{ item.label }}</span>
    </button>
  </aside>
</template>

<script setup lang="ts">
const items = [
  { label: '推送', icon: '↗' },
  { label: '客服', icon: '💬' },
  { label: '反馈', icon: '✎' },
  { label: '分享', icon: '⎘' },
  { label: 'APP', icon: '📱' },
  { label: 'TOP', icon: '↑' },
]
</script>

<style scoped>
.right-toolbar {
  position: fixed;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 50;
}

.tool-item {
  width: 44px;
  padding: 8px 4px;
  border: none;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  color: var(--brand-muted);
  font-size: 10px;
}

.tool-item:hover {
  color: var(--brand-primary);
}

.tool-icon {
  font-size: 14px;
}
</style>
