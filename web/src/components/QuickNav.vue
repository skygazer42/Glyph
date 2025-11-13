<template>
  <div class="quick-nav" role="navigation" aria-label="快速导航">
    <el-card class="nav-card">
      <template #header>
        <div class="card-header">
          <el-icon><Promotion /></el-icon>
          <span>快速导航</span>
        </div>
      </template>

      <div class="nav-grid">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :aria-label="`前往${item.title}`"
        >
          <div class="nav-icon" :style="{ background: item.color }">
            <el-icon :size="24">
              <component :is="item.icon" />
            </el-icon>
          </div>
          <div class="nav-info">
            <h4>{{ item.title }}</h4>
            <p>{{ item.description }}</p>
          </div>
        </router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import {
  Promotion,
  ChatDotRound,
  Document,
  Collection,
  Share
} from '@element-plus/icons-vue'

const navItems = [
  {
    path: '/agent',
    title: 'AI智能问答',
    description: '快速获取政策解答',
    icon: ChatDotRound,
    color: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
  },
  {
    path: '/dsl',
    title: 'DSL规则生成',
    description: '自动生成政策规则',
    icon: Document,
    color: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)'
  },
  {
    path: '/knowledge',
    title: '知识库管理',
    description: '管理政策文档库',
    icon: Collection,
    color: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'
  },
  {
    path: '/graph',
    title: '知识图谱',
    description: '可视化政策关系',
    icon: Share,
    color: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)'
  }
]
</script>

<style scoped>
.quick-nav {
  margin-bottom: var(--spacing-lg);
}

.nav-card {
  border: none;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.nav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: var(--spacing-lg);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  text-decoration: none;
  transition: all var(--transition-base);
  cursor: pointer;
}

.nav-item:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: var(--primary-color);
}

.nav-item:focus {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}

.nav-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}

.nav-info {
  flex: 1;
}

.nav-info h4 {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
}

.nav-info p {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}

/* 响应式 */
@media (max-width: 768px) {
  .nav-grid {
    grid-template-columns: 1fr;
  }
}

/* 键盘导航高亮 */
.nav-item:focus-visible {
  outline: 3px solid var(--primary-color);
  outline-offset: 3px;
}
</style>
