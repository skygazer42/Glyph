<template>
  <nav
    class="breadcrumb-nav"
    aria-label="面包屑导航"
  >
    <el-breadcrumb separator="/">
      <el-breadcrumb-item :to="{ path: '/' }">
        <el-icon><HomeFilled /></el-icon>
        <span>首页</span>
      </el-breadcrumb-item>
      <el-breadcrumb-item
        v-for="(item, index) in breadcrumbs"
        :key="index"
        :to="item.path ? { path: item.path } : undefined"
      >
        <el-icon v-if="item.icon"><component :is="item.icon" /></el-icon>
        <span>{{ item.title }}</span>
      </el-breadcrumb-item>
    </el-breadcrumb>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { HomeFilled, ChatDotRound, Document, Collection } from '@element-plus/icons-vue'

const route = useRoute()

const routeMap = {
  '/agent': { title: 'AI问答', icon: ChatDotRound },
  '/dsl': { title: 'DSL生成', icon: Document },
  '/knowledge': { title: '知识库管理', icon: Collection }
}

const breadcrumbs = computed(() => {
  const path = route.path

  const crumbs = []

  if (routeMap[path]) {
    const { title, icon } = routeMap[path]
    crumbs.push({
      title,
      icon,
      path: null // 当前页面不可点击
    })
  }

  return crumbs
})
</script>

<style scoped>
.breadcrumb-nav {
  padding: var(--spacing-md) 0;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-lg);
}

.breadcrumb-nav :deep(.el-breadcrumb) {
  padding: 0 var(--spacing-lg);
  font-size: var(--text-sm);
}

.breadcrumb-nav :deep(.el-breadcrumb__item) {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.breadcrumb-nav :deep(.el-breadcrumb__inner) {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  color: var(--text-secondary);
  transition: color var(--transition-base);
}

.breadcrumb-nav :deep(.el-breadcrumb__inner:hover) {
  color: var(--primary-color);
}

.breadcrumb-nav :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  color: var(--text-primary);
  font-weight: 500;
}

/* 无障碍优化 */
.breadcrumb-nav:focus-within {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}
</style>
