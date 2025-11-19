<template>
  <div id="app">
    <el-container class="app-container">
      <el-header class="app-header">
        <div class="header-content">
          <router-link to="/" class="logo-section">
            <div class="logo-icon">🏛️</div>
            <div class="logo-info">
              <h1 class="logo-text">智策通</h1>
              <div class="subtitle">ZhiceTong Platform</div>
            </div>
          </router-link>
          <el-menu
            class="nav-menu"
            mode="horizontal"
            :default-active="$route.path"
            @select="handleMenuSelect"
          >
            <el-menu-item index="/agent" class="nav-item">
              <el-icon><ChatDotRound /></el-icon>
              <span>AI问答</span>
            </el-menu-item>
            <el-menu-item index="/dsl" class="nav-item">
              <el-icon><Document /></el-icon>
              <span>DSL生成</span>
            </el-menu-item>
            <el-menu-item index="/knowledge" class="nav-item">
              <el-icon><Collection /></el-icon>
              <span>知识库</span>
            </el-menu-item>
            <el-menu-item index="/graph" class="nav-item">
              <el-icon><Share /></el-icon>
              <span>知识图谱</span>
            </el-menu-item>
          </el-menu>
          <div class="header-actions">
            <ThemeToggle />
            <MobileMenu class="mobile-only" />
          </div>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
        <AppFooter />
        <BackToTop />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { useRouter, useRoute } from 'vue-router'
import { Document, Collection, ChatDotRound, Share } from '@element-plus/icons-vue'
import AppFooter from '@/components/AppFooter.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import MobileMenu from '@/components/MobileMenu.vue'
import BackToTop from '@/components/BackToTop.vue'

const router = useRouter()
const route = useRoute()

// 手动处理导航以确保路由跳转正常工作
const handleMenuSelect = (index) => {
  console.log('Navigating to:', index)
  router.push(index)
}
</script>

<style scoped>
.app-container {
  height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
  transition: background var(--transition-base);
}

/* 暗色模式背景 */
[data-theme="dark"] .app-container {
  background: linear-gradient(135deg, #0f1419 0%, #1a1d23 100%);
}

.app-header {
  background: linear-gradient(135deg, #c8232c 0%, #0052d9 100%);
  color: white;
  padding: 0;
  box-shadow: 0 2px 8px rgba(0, 82, 217, 0.2);
  position: relative;
  z-index: 100;
  border-bottom: 3px solid #c8232c;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 var(--spacing-xl);
  max-width: 1600px;
  margin: 0 auto;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  text-decoration: none;
  cursor: pointer;
  transition: all var(--transition-base);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-md);
}

.logo-section:hover {
  background: rgba(255, 255, 255, 0.1);
  transform: scale(1.02);
}

.logo-section:active {
  transform: scale(0.98);
}

.logo-icon {
  font-size: 2rem;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-5px);
  }
}

.logo-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.logo-text {
  font-size: 1.375rem;
  font-weight: 700;
  white-space: nowrap;
  color: white;
  letter-spacing: 1px;
  line-height: 1.2;
}

.subtitle {
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.85);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 400;
}

.nav-menu {
  border: none;
  background-color: transparent;
  flex: 1;
  justify-content: flex-end;
}

.nav-menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.85);
  border-bottom: 3px solid transparent;
  padding: 0 var(--spacing-lg);
  margin: 0 var(--spacing-xs);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  font-weight: 500;
  transition: all var(--transition-base);
}

.nav-menu :deep(.el-menu-item:hover) {
  color: white;
  background-color: rgba(255, 255, 255, 0.15);
  border-bottom-color: rgba(255, 255, 255, 0.5);
}

.nav-menu :deep(.el-menu-item.is-active) {
  color: white;
  background-color: rgba(255, 255, 255, 0.2);
  border-bottom-color: white;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.nav-menu :deep(.el-menu-item .el-icon) {
  font-size: 1.125rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.mobile-only {
  display: none;
}

.app-main {
  padding: var(--spacing-xl);
  overflow-y: auto;
  background: transparent;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* 页面切换动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .header-content {
    padding: 0 var(--spacing-md);
  }

  .logo-section {
    flex: 1;
  }

  .logo-text {
    font-size: 1rem;
  }

  .nav-menu {
    display: none;
  }

  .mobile-only {
    display: block;
  }

  .app-main {
    padding: var(--spacing-md);
  }
}

@media (max-width: 480px) {
  .logo-text {
    font-size: 0.9rem;
  }

  .subtitle {
    display: none;
  }

  .nav-menu :deep(.el-menu-item span) {
    display: none;
  }

  .nav-menu :deep(.el-menu-item) {
    padding: 0 var(--spacing-sm);
  }
}
</style>
