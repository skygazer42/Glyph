<template>
  <div class="home-page">
    <!-- 系统公告 -->
    <SystemAnnouncement />

    <!-- 快速导航 -->
    <QuickNav />

    <!-- 功能介绍 -->
    <el-row :gutter="20" class="feature-section">
      <el-col :xs="24" :sm="12" :md="8" v-for="feature in features" :key="feature.title">
        <el-card class="feature-card" shadow="hover">
          <div class="feature-icon" :style="{ background: feature.color }">
            <el-icon :size="32">
              <component :is="feature.icon" />
            </el-icon>
          </div>
          <h3>{{ feature.title }}</h3>
          <p>{{ feature.description }}</p>
          <ul class="feature-list">
            <li v-for="item in feature.items" :key="item">{{ item }}</li>
          </ul>
        </el-card>
      </el-col>
    </el-row>

    <!-- 使用统计 -->
    <el-card class="stats-card" shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon><DataAnalysis /></el-icon>
          <span>平台数据</span>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :xs="12" :sm="6" v-for="stat in stats" :key="stat.label">
          <div class="stat-item">
            <div class="stat-value">{{ stat.value }}</div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import {
  ChatDotRound,
  Document,
  Collection,
  DataAnalysis
} from '@element-plus/icons-vue'
import SystemAnnouncement from '@/components/SystemAnnouncement.vue'
import QuickNav from '@/components/QuickNav.vue'

const features = [
  {
    title: 'AI智能问答',
    description: '基于大语言模型的政策智能问答系统',
    icon: ChatDotRound,
    color: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    items: [
      '支持多轮对话',
      '上下文理解',
      '精准政策匹配',
      '流式响应'
    ]
  },
  {
    title: 'DSL规则生成',
    description: '自动从政策文本生成结构化规则',
    icon: Document,
    color: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    items: [
      '智能文本解析',
      'YAML规则生成',
      '规则测试验证',
      '版本管理'
    ]
  },
  {
    title: '知识库管理',
    description: '政策文档的向量化存储与检索',
    icon: Collection,
    color: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
    items: [
      '文档上传解析',
      '向量化嵌入',
      '语义搜索',
      '统计分析'
    ]
  }
]

const stats = reactive([
  { label: '政策文档', value: '1,234' },
  { label: '问答次数', value: '5,678' },
  { label: 'DSL规则', value: '89' },
  { label: '活跃用户', value: '123' }
])
</script>

<style scoped>
.home-page {
  max-width: 1400px;
  margin: 0 auto;
  animation: fadeIn 0.4s ease;
}

/* 功能卡片 */
.feature-section {
  margin-bottom: var(--spacing-2xl);
}

.feature-card {
  height: 100%;
  border-radius: var(--radius-lg);
  transition: all var(--transition-base);
}

.feature-card:hover {
  transform: translateY(-8px);
  box-shadow: var(--shadow-xl);
}

.feature-icon {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  margin-bottom: var(--spacing-lg);
  box-shadow: var(--shadow-md);
}

.feature-card h3 {
  margin: 0 0 var(--spacing-md) 0;
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
}

.feature-card p {
  margin: 0 0 var(--spacing-lg) 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.feature-list li {
  padding: var(--spacing-xs) 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.feature-list li::before {
  content: '✓';
  color: var(--success-color);
  font-weight: bold;
}

/* 统计卡片 */
.stats-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: var(--text-lg);
  font-weight: 600;
}

.stat-item {
  text-align: center;
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, rgba(0, 82, 217, 0.05) 0%, rgba(200, 35, 44, 0.05) 100%);
  border-radius: var(--radius-md);
  transition: all var(--transition-base);
}

.stat-item:hover {
  transform: scale(1.05);
  box-shadow: var(--shadow-md);
}

.stat-value {
  font-size: var(--text-3xl);
  font-weight: 700;
  background: var(--primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: var(--spacing-sm);
}

.stat-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: 500;
}

/* 响应式 */
@media (max-width: 768px) {
  .feature-section {
    margin-bottom: var(--spacing-xl);
  }
}
</style>
