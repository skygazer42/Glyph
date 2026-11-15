<template>
  <transition name="fade-up">
    <button
      type="button"
      v-if="visible"
      class="back-to-top"
      @click="scrollToTop"
      aria-label="返回顶部"
    >
      <el-icon :size="20">
        <Top />
      </el-icon>
    </button>
  </transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { Top } from '@element-plus/icons-vue'

const visible = ref(false)
let scrollTarget = null

const handleScroll = () => {
  const scrollTop = scrollTarget === window
    ? window.pageYOffset || document.documentElement.scrollTop
    : scrollTarget.scrollTop
  visible.value = scrollTop > 300
}

const scrollToTop = () => {
  scrollTarget?.scrollTo({
    top: 0,
    behavior: 'smooth'
  })
}

onMounted(() => {
  scrollTarget = document.querySelector('.app-main') || window
  handleScroll()
  scrollTarget.addEventListener('scroll', handleScroll)
})

onUnmounted(() => {
  scrollTarget?.removeEventListener('scroll', handleScroll)
})
</script>

<style scoped>
.back-to-top {
  border: 0;
  padding: 0;
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
