<template>
  <div class="theme-toggle" :title="isDark ? '切换到亮色模式' : '切换到暗色模式'">
    <el-button
      :icon="isDark ? Sunny : Moon"
      circle
      @click="toggleTheme"
      class="theme-button"
      :aria-label="isDark ? '切换到亮色模式' : '切换到暗色模式'"
    />
  </div>
</template>

<script setup>
import { Sunny, Moon } from '@element-plus/icons-vue'
import { useTheme } from '@/composables/useTheme'

const { isDark, toggleTheme } = useTheme()
</script>

<style scoped>
.theme-toggle {
  display: flex;
  align-items: center;
}

.theme-button {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  transition: all var(--transition-base);
}

.theme-button:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
  transform: rotate(180deg);
}

.theme-button:active {
  transform: rotate(180deg) scale(0.95);
}

/* 暗色模式下的样式 */
[data-theme="dark"] .theme-button {
  background: rgba(0, 0, 0, 0.2);
  border-color: rgba(255, 255, 255, 0.1);
}

[data-theme="dark"] .theme-button:hover {
  background: rgba(0, 0, 0, 0.3);
  border-color: rgba(255, 255, 255, 0.2);
}
</style>
