<template>
  <div id="app">
    <el-container class="app-container">
      <!-- 头部导航 -->
      <el-header class="app-header">
        <div class="header-content">
          <!-- Logo 和标题 -->
          <div class="header-logo">
            <span class="logo-icon">🏛️</span>
            <h1 class="logo-title">
              <span class="hide-mobile">政策DSL生成和知识库管理系统</span>
              <span class="hide-desktop">政策系统</span>
            </h1>
          </div>

          <!-- 导航菜单 - 桌面端 -->
          <el-menu
            class="nav-menu hide-mobile"
            mode="horizontal"
            :default-active="$route.path"
            router
          >
            <el-menu-item index="/agent">
              <el-icon><ChatDotRound /></el-icon>
              <span>AI问答</span>
            </el-menu-item>
            <el-menu-item index="/dsl">
              <el-icon><Document /></el-icon>
              <span>DSL生成</span>
            </el-menu-item>
            <el-menu-item index="/knowledge">
              <el-icon><Collection /></el-icon>
              <span>知识库</span>
            </el-menu-item>
          </el-menu>

          <!-- 导航菜单 - 移动端 -->
          <el-dropdown class="nav-dropdown hide-desktop" @command="handleCommand">
            <el-button type="primary" circle>
              <el-icon><Menu /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="/agent" :class="{ 'is-active': $route.path === '/agent' }">
                  <el-icon><ChatDotRound /></el-icon>
                  AI问答
                </el-dropdown-item>
                <el-dropdown-item command="/dsl" :class="{ 'is-active': $route.path === '/dsl' }">
                  <el-icon><Document /></el-icon>
                  DSL生成
                </el-dropdown-item>
                <el-dropdown-item command="/knowledge" :class="{ 'is-active': $route.path === '/knowledge' }">
                  <el-icon><Collection /></el-icon>
                  知识库
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主要内容区 -->
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
import { useRouter } from 'vue-router'
import { Document, Collection, ChatDotRound, Menu } from '@element-plus/icons-vue'

const router = useRouter()

const handleCommand = (path) => {
  router.push(path)
}
</script>

<style scoped>
.app-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

/* 头部样式 */
.app-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 0;
  height: var(--header-height);
  box-shadow: var(--shadow-base);
  position: sticky;
  top: 0;
  z-index: 1000;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 var(--spacing-xl);
  max-width: var(--content-max-width);
  margin: 0 auto;
  width: 100%;
}

.header-logo {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.logo-icon {
  font-size: var(--font-size-xxl);
}

.logo-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  margin: 0;
  white-space: nowrap;
}

/* 导航菜单 */
.nav-menu {
  border: none;
  background: transparent;
  flex: 1;
  justify-content: flex-end;
}

.nav-menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.85);
  border-bottom: 3px solid transparent;
  transition: var(--transition-fast);
  font-weight: 500;
}

.nav-menu :deep(.el-menu-item:hover),
.nav-menu :deep(.el-menu-item.is-active) {
  color: white;
  border-bottom-color: white;
  background: rgba(255, 255, 255, 0.1);
}

.nav-menu :deep(.el-menu-item .el-icon) {
  margin-right: var(--spacing-xs);
}

/* 移动端下拉菜单 */
.nav-dropdown :deep(.el-dropdown-menu__item) {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 12px 20px;
}

.nav-dropdown :deep(.el-dropdown-menu__item.is-active) {
  background-color: var(--primary-color);
  color: white;
}

/* 主要内容区 */
.app-main {
  flex: 1;
  padding: 0;
  background-color: var(--bg-secondary);
  overflow-y: auto;
}

/* 页面过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* 移动端适配 */
@media (max-width: 768px) {
  .header-content {
    padding: 0 var(--spacing-md);
  }

  .logo-title {
    font-size: var(--font-size-base);
  }

  .logo-icon {
    font-size: var(--font-size-lg);
  }

  .app-header {
    height: 56px;
  }
}

/* 平板适配 */
@media (min-width: 769px) and (max-width: 1024px) {
  .header-content {
    padding: 0 var(--spacing-lg);
  }

  .logo-title {
    font-size: var(--font-size-md);
  }
}
</style>
