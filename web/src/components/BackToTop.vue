<template>
  <transition name="fade-up">
    <div
      v-if="visible"
      class="back-to-top"
      @click="scrollToTop"
      role="button"
      tabindex="0"
      aria-label="返回顶部"
      @keypress.enter="scrollToTop"
      @keypress.space="scrollToTop"
    >
      <el-icon :size="20">
        <Top />
      </el-icon>
    </div>
  </transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Top } from '@element-plus/icons-vue'

const visible = ref(false)

const handleScroll = () => {
  const scrollTop = window.pageYOffset || document.documentElement.scrollTop
  visible.value = scrollTop > 300
}

const scrollToTop = () => {
  window.scrollTo({
    top: 0,
    behavior: 'smooth'
  })
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<style scoped>
.back-to-top {
  position: fixed;
  right: var(--spacing-xl);
  bottom: var(--spacing-xl);
  width: 48px;
  height: 48px;
  background: var(--primary-gradient);
  color: white;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--shadow-lg);
  transition: all var(--transition-base);
  z-index: 1000;
}

.back-to-top:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-xl);
}

.back-to-top:active {
  transform: translateY(-2px);
}

.back-to-top:focus {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

/* 动画 */
.fade-up-enter-active,
.fade-up-leave-active {
  transition: all 0.3s ease;
}

.fade-up-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.fade-up-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

/* 移动端适配 */
@media (max-width: 768px) {
  .back-to-top {
    right: var(--spacing-lg);
    bottom: var(--spacing-lg);
    width: 40px;
    height: 40px;
  }
}

/* 暗色模式 */
[data-theme="dark"] .back-to-top {
  background: linear-gradient(135deg, #3d7fff 0%, #e34d59 100%);
}
</style>
