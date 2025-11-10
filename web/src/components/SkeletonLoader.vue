<template>
  <div class="skeleton-loader" :class="{ 'animated': animated }">
    <!-- 卡片骨架屏 -->
    <div v-if="type === 'card'" class="skeleton-card">
      <div class="skeleton-header">
        <div class="skeleton-avatar"></div>
        <div class="skeleton-title"></div>
      </div>
      <div class="skeleton-content">
        <div class="skeleton-line" v-for="i in rows" :key="i"></div>
      </div>
    </div>

    <!-- 表格骨架屏 -->
    <div v-else-if="type === 'table'" class="skeleton-table">
      <div class="skeleton-table-header">
        <div class="skeleton-cell" v-for="i in columns" :key="`header-${i}`"></div>
      </div>
      <div class="skeleton-table-row" v-for="i in rows" :key="`row-${i}`">
        <div class="skeleton-cell" v-for="j in columns" :key="`cell-${i}-${j}`"></div>
      </div>
    </div>

    <!-- 列表骨架屏 -->
    <div v-else-if="type === 'list'" class="skeleton-list">
      <div class="skeleton-list-item" v-for="i in rows" :key="i">
        <div class="skeleton-avatar"></div>
        <div class="skeleton-content">
          <div class="skeleton-title"></div>
          <div class="skeleton-subtitle"></div>
        </div>
      </div>
    </div>

    <!-- 文本骨架屏 -->
    <div v-else-if="type === 'text'" class="skeleton-text">
      <div class="skeleton-line" v-for="i in rows" :key="i" :style="getLineStyle(i)"></div>
    </div>

    <!-- 图片骨架屏 -->
    <div v-else-if="type === 'image'" class="skeleton-image" :style="imageStyle"></div>

    <!-- 自定义骨架屏 -->
    <div v-else class="skeleton-custom">
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: {
    type: String,
    default: 'text', // text, card, table, list, image, custom
    validator: (value) => ['text', 'card', 'table', 'list', 'image', 'custom'].includes(value)
  },
  rows: {
    type: Number,
    default: 3
  },
  columns: {
    type: Number,
    default: 4
  },
  animated: {
    type: Boolean,
    default: true
  },
  width: {
    type: String,
    default: '100%'
  },
  height: {
    type: String,
    default: '200px'
  }
})

const imageStyle = computed(() => ({
  width: props.width,
  height: props.height
}))

const getLineStyle = (index) => {
  // 最后一行宽度随机，模拟真实文本
  if (index === props.rows) {
    return { width: `${60 + Math.random() * 30}%` }
  }
  return {}
}
</script>

<style scoped>
.skeleton-loader {
  width: 100%;
}

/* 骨架屏基础样式 */
.skeleton-avatar,
.skeleton-title,
.skeleton-subtitle,
.skeleton-line,
.skeleton-cell,
.skeleton-image {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  border-radius: var(--radius-small);
}

.skeleton-loader.animated .skeleton-avatar,
.skeleton-loader.animated .skeleton-title,
.skeleton-loader.animated .skeleton-subtitle,
.skeleton-loader.animated .skeleton-line,
.skeleton-loader.animated .skeleton-cell,
.skeleton-loader.animated .skeleton-image {
  animation: shimmer 1.5s infinite;
}

/* 卡片骨架屏 */
.skeleton-card {
  padding: var(--spacing-lg);
  background: var(--bg-primary);
  border-radius: var(--radius-base);
  border: 1px solid var(--border-light);
}

.skeleton-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.skeleton-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  flex-shrink: 0;
}

.skeleton-title {
  height: 20px;
  flex: 1;
}

.skeleton-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.skeleton-line {
  height: 16px;
  width: 100%;
}

.skeleton-line:last-child {
  width: 70%;
}

/* 表格骨架屏 */
.skeleton-table {
  background: var(--bg-primary);
  border-radius: var(--radius-base);
  overflow: hidden;
  border: 1px solid var(--border-light);
}

.skeleton-table-header,
.skeleton-table-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg);
}

.skeleton-table-header {
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-light);
}

.skeleton-table-row {
  border-bottom: 1px solid var(--border-lighter);
}

.skeleton-table-row:last-child {
  border-bottom: none;
}

.skeleton-cell {
  height: 20px;
}

/* 列表骨架屏 */
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.skeleton-list-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-primary);
  border-radius: var(--radius-base);
  border: 1px solid var(--border-light);
}

.skeleton-list-item .skeleton-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.skeleton-subtitle {
  height: 14px;
  width: 60%;
}

/* 文本骨架屏 */
.skeleton-text {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

/* 图片骨架屏 */
.skeleton-image {
  width: 100%;
  height: 200px;
}

/* 动画 */
@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

/* 深色模式 */
@media (prefers-color-scheme: dark) {
  .skeleton-avatar,
  .skeleton-title,
  .skeleton-subtitle,
  .skeleton-line,
  .skeleton-cell,
  .skeleton-image {
    background: linear-gradient(90deg, #2a2a2a 25%, #333333 50%, #2a2a2a 75%);
    background-size: 200% 100%;
  }
}

/* 响应式 */
@media (max-width: 768px) {
  .skeleton-table-header,
  .skeleton-table-row {
    grid-template-columns: 1fr;
  }
}
</style>
