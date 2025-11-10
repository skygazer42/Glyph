<template>
  <div class="skeleton-loader" :aria-busy="true" aria-label="加载中">
    <!-- 卡片骨架 -->
    <div v-if="type === 'card'" class="skeleton-card">
      <div class="skeleton-header">
        <div class="skeleton-avatar"></div>
        <div class="skeleton-lines">
          <div class="skeleton-line short"></div>
          <div class="skeleton-line"></div>
        </div>
      </div>
      <div class="skeleton-content">
        <div class="skeleton-line"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line short"></div>
      </div>
    </div>

    <!-- 列表骨架 -->
    <div v-else-if="type === 'list'" class="skeleton-list">
      <div v-for="i in count" :key="i" class="skeleton-list-item">
        <div class="skeleton-avatar small"></div>
        <div class="skeleton-lines flex-1">
          <div class="skeleton-line"></div>
          <div class="skeleton-line short"></div>
        </div>
      </div>
    </div>

    <!-- 表格骨架 -->
    <div v-else-if="type === 'table'" class="skeleton-table">
      <div class="skeleton-table-header">
        <div class="skeleton-line"></div>
      </div>
      <div v-for="i in count" :key="i" class="skeleton-table-row">
        <div class="skeleton-line"></div>
        <div class="skeleton-line short"></div>
        <div class="skeleton-line medium"></div>
      </div>
    </div>

    <!-- 文本骨架 -->
    <div v-else class="skeleton-text">
      <div v-for="i in count" :key="i" class="skeleton-line" :class="{ short: i === count }"></div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  type: {
    type: String,
    default: 'text', // text, card, list, table
    validator: (value) => ['text', 'card', 'list', 'table'].includes(value)
  },
  count: {
    type: Number,
    default: 3
  }
})
</script>

<style scoped>
.skeleton-loader {
  width: 100%;
}

/* 基础骨架元素 */
.skeleton-line,
.skeleton-avatar {
  background: linear-gradient(
    90deg,
    var(--bg-secondary) 25%,
    #f0f0f0 50%,
    var(--bg-secondary) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s ease-in-out infinite;
  border-radius: var(--radius-sm);
}

.skeleton-line {
  height: 16px;
  margin-bottom: var(--spacing-sm);
}

.skeleton-line.short {
  width: 60%;
}

.skeleton-line.medium {
  width: 80%;
}

.skeleton-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.skeleton-avatar.small {
  width: 32px;
  height: 32px;
}

/* 卡片骨架 */
.skeleton-card {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-sm);
}

.skeleton-header {
  display: flex;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.skeleton-lines {
  flex: 1;
}

.skeleton-lines.flex-1 {
  flex: 1;
}

.skeleton-content {
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

/* 列表骨架 */
.skeleton-list-item {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-sm);
}

/* 表格骨架 */
.skeleton-table {
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
}

.skeleton-table-header {
  padding-bottom: var(--spacing-md);
  border-bottom: 2px solid var(--border-color);
  margin-bottom: var(--spacing-md);
}

.skeleton-table-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1.5fr;
  gap: var(--spacing-md);
  padding: var(--spacing-md) 0;
  border-bottom: 1px solid var(--border-color);
}

/* 文本骨架 */
.skeleton-text {
  padding: var(--spacing-md);
}

/* 加载动画 */
@keyframes skeleton-loading {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

/* 暗色模式 */
[data-theme="dark"] .skeleton-line,
[data-theme="dark"] .skeleton-avatar {
  background: linear-gradient(
    90deg,
    var(--bg-secondary) 25%,
    #2a2d35 50%,
    var(--bg-secondary) 75%
  );
  background-size: 200% 100%;
}

[data-theme="dark"] .skeleton-card,
[data-theme="dark"] .skeleton-list-item,
[data-theme="dark"] .skeleton-table {
  background: var(--card-bg);
}
</style>
