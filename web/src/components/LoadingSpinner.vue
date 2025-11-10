<template>
  <div class="loading-spinner" :class="{ 'fullscreen': fullscreen }">
    <div class="spinner-container">
      <div class="spinner" :style="spinnerStyle">
        <div class="spinner-blade" v-for="i in 12" :key="i"></div>
      </div>
      <p v-if="text" class="loading-text">{{ text }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: {
    type: String,
    default: 'medium', // small, medium, large
    validator: (value) => ['small', 'medium', 'large'].includes(value)
  },
  text: {
    type: String,
    default: ''
  },
  fullscreen: {
    type: Boolean,
    default: false
  },
  color: {
    type: String,
    default: '#409eff'
  }
})

const spinnerStyle = computed(() => {
  const sizes = {
    small: '24px',
    medium: '40px',
    large: '60px'
  }
  return {
    width: sizes[props.size],
    height: sizes[props.size]
  }
})
</script>

<style scoped>
.loading-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
}

.loading-spinner.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  z-index: 9999;
  backdrop-filter: blur(4px);
}

.spinner-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-md);
}

.spinner {
  position: relative;
  animation: spin 1.2s linear infinite;
}

.spinner-blade {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 8%;
  height: 25%;
  background: v-bind(color);
  border-radius: 50px;
  transform-origin: center -100%;
  opacity: 0;
  animation: fade 1.2s linear infinite;
}

.spinner-blade:nth-child(1) {
  transform: rotate(0deg);
  animation-delay: 0s;
}

.spinner-blade:nth-child(2) {
  transform: rotate(30deg);
  animation-delay: -0.1s;
}

.spinner-blade:nth-child(3) {
  transform: rotate(60deg);
  animation-delay: -0.2s;
}

.spinner-blade:nth-child(4) {
  transform: rotate(90deg);
  animation-delay: -0.3s;
}

.spinner-blade:nth-child(5) {
  transform: rotate(120deg);
  animation-delay: -0.4s;
}

.spinner-blade:nth-child(6) {
  transform: rotate(150deg);
  animation-delay: -0.5s;
}

.spinner-blade:nth-child(7) {
  transform: rotate(180deg);
  animation-delay: -0.6s;
}

.spinner-blade:nth-child(8) {
  transform: rotate(210deg);
  animation-delay: -0.7s;
}

.spinner-blade:nth-child(9) {
  transform: rotate(240deg);
  animation-delay: -0.8s;
}

.spinner-blade:nth-child(10) {
  transform: rotate(270deg);
  animation-delay: -0.9s;
}

.spinner-blade:nth-child(11) {
  transform: rotate(300deg);
  animation-delay: -1s;
}

.spinner-blade:nth-child(12) {
  transform: rotate(330deg);
  animation-delay: -1.1s;
}

.loading-text {
  margin: 0;
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  font-weight: 500;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes fade {
  0%, 100% {
    opacity: 0.2;
  }
  50% {
    opacity: 1;
  }
}

/* 深色模式 */
@media (prefers-color-scheme: dark) {
  .loading-spinner.fullscreen {
    background: rgba(30, 30, 30, 0.9);
  }
}
</style>
