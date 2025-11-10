<template>
  <transition name="slide-down">
    <div
      v-if="visible && announcement"
      class="system-announcement"
      role="alert"
      aria-live="polite"
    >
      <div class="announcement-content">
        <el-icon class="announcement-icon" :size="20">
          <BellFilled />
        </el-icon>
        <div class="announcement-text">
          <span class="announcement-title">系统公告：</span>
          <span>{{ announcement.message }}</span>
        </div>
        <el-button
          link
          :icon="Close"
          @click="closeAnnouncement"
          class="close-btn"
          aria-label="关闭公告"
        />
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { BellFilled, Close } from '@element-plus/icons-vue'

const visible = ref(false)
const announcement = ref(null)

// 模拟从后端获取公告
const fetchAnnouncement = () => {
  // 这里可以替换为实际的API调用
  announcement.value = {
    id: '1',
    message: '欢迎使用政府政策智能分析平台，如有问题请联系技术支持。',
    type: 'info',
    dismissible: true
  }

  // 检查用户是否已关闭过此公告
  const dismissedId = localStorage.getItem('dismissed-announcement')
  if (dismissedId !== announcement.value.id) {
    visible.value = true
  }
}

const closeAnnouncement = () => {
  visible.value = false
  if (announcement.value?.dismissible) {
    localStorage.setItem('dismissed-announcement', announcement.value.id)
  }
}

onMounted(() => {
  fetchAnnouncement()
})
</script>

<style scoped>
.system-announcement {
  background: linear-gradient(135deg, rgba(0, 82, 217, 0.1) 0%, rgba(200, 35, 44, 0.1) 100%);
  border: 1px solid rgba(0, 82, 217, 0.2);
  border-left: 4px solid var(--primary-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  box-shadow: var(--shadow-sm);
}

.announcement-content {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.announcement-icon {
  color: var(--primary-color);
  flex-shrink: 0;
}

.announcement-text {
  flex: 1;
  font-size: var(--text-sm);
  line-height: 1.6;
  color: var(--text-primary);
}

.announcement-title {
  font-weight: 600;
  color: var(--primary-color);
  margin-right: var(--spacing-xs);
}

.close-btn {
  flex-shrink: 0;
  color: var(--text-secondary);
  transition: color var(--transition-base);
}

.close-btn:hover {
  color: var(--text-primary);
}

/* 动画 */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
}

.slide-down-enter-from {
  opacity: 0;
  transform: translateY(-20px);
}

.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* 暗色模式 */
[data-theme="dark"] .system-announcement {
  background: linear-gradient(135deg, rgba(61, 127, 255, 0.15) 0%, rgba(227, 77, 89, 0.15) 100%);
  border-color: rgba(61, 127, 255, 0.3);
}
</style>
