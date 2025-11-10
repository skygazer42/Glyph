<template>
  <div class="empty-state" role="status">
    <div class="empty-icon">
      <el-icon :size="64">
        <component :is="iconComponent" />
      </el-icon>
    </div>
    <h3 class="empty-title">{{ title }}</h3>
    <p class="empty-description">{{ description }}</p>
    <div v-if="$slots.action" class="empty-action">
      <slot name="action"></slot>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  Box,
  Document,
  Search,
  Warning,
  ChatDotRound
} from '@element-plus/icons-vue'

const props = defineProps({
  type: {
    type: String,
    default: 'default', // default, search, document, warning, chat
    validator: (value) => ['default', 'search', 'document', 'warning', 'chat'].includes(value)
  },
  title: {
    type: String,
    default: '暂无数据'
  },
  description: {
    type: String,
    default: '当前没有可显示的内容'
  }
})

const iconComponent = computed(() => {
  const icons = {
    default: Box,
    search: Search,
    document: Document,
    warning: Warning,
    chat: ChatDotRound
  }
  return icons[props.type] || Box
})
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-2xl) var(--spacing-xl);
  text-align: center;
  min-height: 300px;
}

.empty-icon {
  width: 120px;
  height: 120px;
  border-radius: var(--radius-full);
  background: linear-gradient(135deg, rgba(0, 82, 217, 0.1) 0%, rgba(200, 35, 44, 0.1) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--spacing-lg);
  color: var(--primary-color);
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}

.empty-title {
  margin: 0 0 var(--spacing-md) 0;
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
}

.empty-description {
  margin: 0 0 var(--spacing-lg) 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  max-width: 400px;
  line-height: 1.6;
}

.empty-action {
  margin-top: var(--spacing-md);
}

/* 暗色模式 */
[data-theme="dark"] .empty-icon {
  background: linear-gradient(135deg, rgba(61, 127, 255, 0.15) 0%, rgba(227, 77, 89, 0.15) 100%);
}
</style>
