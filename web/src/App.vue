<template>
  <div id="app">
    <el-container class="app-container">
      <el-header class="app-header">
        <div class="header-content">
          <div class="logo-section">
            <div class="logo-icon">🏛️</div>
            <h1 class="logo-text">政策智能分析系统</h1>
          </div>
          <el-menu
            class="nav-menu"
            mode="horizontal"
            :default-active="$route.path"
            router
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
          </el-menu>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { Document, Collection, ChatDotRound } from '@element-plus/icons-vue'
</script>

<style scoped>
.app-container {
  height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
}

.app-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 0;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
  position: relative;
  z-index: 100;
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

.logo-text {
  font-size: 1.25rem;
  font-weight: 600;
  white-space: nowrap;
  background: linear-gradient(to right, #ffffff, #f0f9ff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
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

.app-main {
  padding: var(--spacing-xl);
  overflow-y: auto;
  background: transparent;
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
    flex-wrap: wrap;
  }

  .logo-section {
    flex: 1;
  }

  .logo-text {
    font-size: 1rem;
  }

  .nav-menu {
    flex: 1 1 100%;
    margin-top: var(--spacing-sm);
  }

  .nav-menu :deep(.el-menu-item) {
    padding: 0 var(--spacing-md);
    font-size: 0.875rem;
  }

  .app-main {
    padding: var(--spacing-md);
  }
}

@media (max-width: 480px) {
  .logo-text {
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

