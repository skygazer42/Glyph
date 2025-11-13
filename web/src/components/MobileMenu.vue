<template>
  <div class="mobile-menu">
    <!-- 移动端菜单按钮 -->
    <el-button
      class="menu-trigger"
      :icon="Menu"
      circle
      @click="drawerVisible = true"
      aria-label="打开菜单"
    />

    <!-- 抽屉菜单 -->
    <el-drawer
      v-model="drawerVisible"
      direction="ltr"
      :size="280"
      :show-close="false"
      class="mobile-drawer"
    >
      <template #header>
        <div class="drawer-header">
          <div class="logo-section">
            <div class="logo-icon">🏛️</div>
            <div class="logo-text">政务平台</div>
          </div>
          <el-button
            :icon="Close"
            circle
            @click="drawerVisible = false"
            aria-label="关闭菜单"
          />
        </div>
      </template>

      <div class="drawer-content">
        <!-- 导航菜单 -->
        <nav class="nav-list" role="navigation">
          <router-link
            v-for="item in menuItems"
            :key="item.path"
            :to="item.path"
            class="nav-link"
            @click="drawerVisible = false"
          >
            <el-icon class="nav-icon">
              <component :is="item.icon" />
            </el-icon>
            <span class="nav-label">{{ item.label }}</span>
            <el-icon class="nav-arrow">
              <ArrowRight />
            </el-icon>
          </router-link>
        </nav>

        <!-- 设置区域 -->
        <div class="drawer-footer">
          <div class="theme-control">
            <span>深色模式</span>
            <el-switch
              v-model="isDark"
              @change="toggleTheme"
              aria-label="切换深色模式"
            />
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  Menu,
  Close,
  ChatDotRound,
  Document,
  Collection,
  Share,
  HomeFilled,
  ArrowRight
} from '@element-plus/icons-vue'
import { useTheme } from '@/composables/useTheme'

const drawerVisible = ref(false)
const { isDark, toggleTheme } = useTheme()

const menuItems = [
  { path: '/', label: '首页', icon: HomeFilled },
  { path: '/agent', label: 'AI问答', icon: ChatDotRound },
  { path: '/dsl', label: 'DSL生成', icon: Document },
  { path: '/knowledge', label: '知识库', icon: Collection },
  { path: '/graph', label: '知识图谱', icon: Share }
]
</script>

<style scoped>
.mobile-menu {
  display: none;
}

.menu-trigger {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
}

.menu-trigger:hover {
  background: rgba(255, 255, 255, 0.2);
}

/* 抽屉样式 */
.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.logo-section {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.logo-icon {
  font-size: 1.5rem;
}

.logo-text {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.drawer-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--spacing-lg);
}

/* 导航列表 */
.nav-list {
  flex: 1;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-sm);
  border-radius: var(--radius-md);
  text-decoration: none;
  color: var(--text-primary);
  transition: all var(--transition-base);
  border: 1px solid transparent;
}

.nav-link:hover {
  background: var(--bg-color);
  border-color: var(--primary-color);
}

.nav-link.router-link-active {
  background: linear-gradient(135deg, rgba(0, 82, 217, 0.1) 0%, rgba(200, 35, 44, 0.1) 100%);
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.nav-icon {
  font-size: 1.25rem;
  flex-shrink: 0;
}

.nav-label {
  flex: 1;
  font-size: var(--text-base);
  font-weight: 500;
}

.nav-arrow {
  font-size: 1rem;
  opacity: 0.5;
}

/* 底部设置 */
.drawer-footer {
  border-top: 1px solid var(--border-color);
  padding-top: var(--spacing-lg);
  margin-top: var(--spacing-lg);
}

.theme-control {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md);
  background: var(--bg-color);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
}

/* 移动端显示 */
@media (max-width: 768px) {
  .mobile-menu {
    display: block;
  }
}

/* 暗色模式 */
[data-theme="dark"] .nav-link.router-link-active {
  background: linear-gradient(135deg, rgba(61, 127, 255, 0.15) 0%, rgba(227, 77, 89, 0.15) 100%);
}
</style>
