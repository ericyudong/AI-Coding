<template>
  <el-dropdown trigger="click" @command="onProductCommand">
    <span class="header-link">产品菜单</span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item v-for="item in PRODUCT_MENU" :key="item.label" :command="item.route">
          {{ item.label }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
  <el-dropdown trigger="click" @command="onHelpCommand">
    <span class="header-link">帮助</span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="manual">用户手册</el-dropdown-item>
        <el-dropdown-item command="contact">联系益慧</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { CONTACT_INFO, PRODUCT_MENU, USER_MANUAL_URL } from '@/constants/headerNav'

const router = useRouter()

function onProductCommand(route: string) {
  router.push(route)
}

function onHelpCommand(command: string) {
  if (command === 'manual') {
    window.open(USER_MANUAL_URL, '_blank')
    return
  }
  if (command === 'contact') {
    ElMessageBox.alert(
      `公司：${CONTACT_INFO.company}\n邮箱：${CONTACT_INFO.email}\n电话：${CONTACT_INFO.phone}`,
      '联系益慧',
      { confirmButtonText: '知道了' },
    )
  }
}
</script>

<style scoped>
.header-link {
  cursor: pointer;
  font-size: 13px;
  color: var(--brand-muted);
}

.header-link:hover {
  color: var(--brand-primary);
}
</style>
