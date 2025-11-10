<template>
  <div class="dashboard">
    <!-- 欢迎横幅 -->
    <div class="hero-banner">
      <div class="hero-content">
        <div class="hero-text">
          <h1 class="hero-title">
            <span class="logo-icon">🏛️</span>
            智策通
          </h1>
          <p class="hero-subtitle">AI政策动态咨询智能体</p>
          <p class="hero-description">
            基于混合智能架构，为您提供精准的政策问答服务
          </p>
          <div class="hero-actions">
            <el-button type="primary" size="large" @click="goToChat">
              <el-icon><ChatDotRound /></el-icon>
              立即咨询
            </el-button>
            <el-button size="large" @click="goToCalculator">
              <el-icon><Calculator /></el-icon>
              政策计算
            </el-button>
          </div>
        </div>
        <div class="hero-illustration">
          <div class="illustration-circle"></div>
          <div class="illustration-icon">💡</div>
        </div>
      </div>
    </div>

    <!-- 数据统计卡片 -->
    <div class="stats-section">
      <el-row :gutter="20">
        <el-col :xs="24" :sm="12" :md="6" v-for="(stat, index) in stats" :key="index">
          <div class="stat-card" :class="`stat-${index + 1}`">
            <div class="stat-icon">{{ stat.icon }}</div>
            <div class="stat-content">
              <div class="stat-value">{{ stat.value }}</div>
              <div class="stat-label">{{ stat.label }}</div>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 核心功能入口 -->
    <div class="features-section">
      <h2 class="section-title">核心功能</h2>
      <el-row :gutter="20">
        <el-col :xs="24" :sm="12" :md="8" v-for="feature in features" :key="feature.id">
          <el-card class="feature-card" @click="handleFeatureClick(feature)">
            <div class="feature-icon">{{ feature.icon }}</div>
            <h3 class="feature-title">{{ feature.title }}</h3>
            <p class="feature-desc">{{ feature.description }}</p>
            <div class="feature-footer">
              <el-button type="primary" text>
                开始使用 <el-icon><ArrowRight /></el-icon>
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 热门政策领域 -->
    <div class="domains-section">
      <h2 class="section-title">热门政策领域</h2>
      <div class="domains-grid">
        <div
          v-for="domain in policyDomains"
          :key="domain.id"
          class="domain-card"
          @click="consultDomain(domain)"
        >
          <div class="domain-icon">{{ domain.icon }}</div>
          <div class="domain-name">{{ domain.name }}</div>
          <div class="domain-count">{{ domain.policyCount }} 项政策</div>
        </div>
      </div>
    </div>

    <!-- 常见问题 -->
    <div class="faq-section">
      <h2 class="section-title">常见问题</h2>
      <div class="faq-list">
        <div
          v-for="(faq, index) in faqs"
          :key="index"
          class="faq-item"
          @click="askQuestion(faq.question)"
        >
          <div class="faq-icon">
            <el-icon><QuestionFilled /></el-icon>
          </div>
          <div class="faq-content">
            <div class="faq-question">{{ faq.question }}</div>
            <div class="faq-category">{{ faq.category }}</div>
          </div>
          <el-icon class="faq-arrow"><ArrowRight /></el-icon>
        </div>
      </div>
    </div>

    <!-- 系统特点 -->
    <div class="advantages-section">
      <h2 class="section-title">系统特点</h2>
      <el-row :gutter="20">
        <el-col :xs="24" :sm="12" :md="6" v-for="adv in advantages" :key="adv.id">
          <div class="advantage-card">
            <div class="advantage-icon">{{ adv.icon }}</div>
            <h4 class="advantage-title">{{ adv.title }}</h4>
            <p class="advantage-desc">{{ adv.description }}</p>
          </div>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ChatDotRound, Calculator, ArrowRight, QuestionFilled } from '@element-plus/icons-vue'

const router = useRouter()

// 数据统计
const stats = ref([
  { icon: '📚', label: '政策文档', value: '1,234' },
  { icon: '💬', label: '累计咨询', value: '5,678' },
  { icon: '✅', label: '问题解决率', value: '95%' },
  { icon: '⚡', label: '平均响应时间', value: '2s' }
])

// 核心功能
const features = ref([
  {
    id: 'chat',
    icon: '💬',
    title: 'AI智能问答',
    description: '多轮对话，智能理解您的问题，提供精准的政策解答',
    route: '/chat'
  },
  {
    id: 'calculator',
    icon: '🧮',
    title: '政策计算器',
    description: '自动计算补贴额度，支持多种政策场景的精准计算',
    route: '/calculator'
  },
  {
    id: 'knowledge',
    icon: '📖',
    title: '知识库管理',
    description: '强大的文档管理和检索功能，快速找到您需要的政策信息',
    route: '/knowledge'
  }
])

// 政策领域
const policyDomains = ref([
  { id: 'car', name: '汽车补贴', icon: '🚗', policyCount: 45 },
  { id: 'appliance', name: '家电补贴', icon: '🏠', policyCount: 38 },
  { id: 'voucher', name: '消费券', icon: '🎫', policyCount: 62 },
  { id: 'tradeIn', name: '以旧换新', icon: '♻️', policyCount: 28 },
  { id: 'insurance', name: '保险补贴', icon: '🛡️', policyCount: 19 }
])

// 常见问题
const faqs = ref([
  { question: '购买新能源汽车能享受哪些补贴政策？', category: '汽车补贴' },
  { question: '家电以旧换新补贴标准是什么？', category: '家电补贴' },
  { question: '消费券的使用条件和限制有哪些？', category: '消费券' },
  { question: '如何申请汽车保险补贴？', category: '保险补贴' },
  { question: '购买高能效家电有什么优惠？', category: '家电补贴' }
])

// 系统优势
const advantages = ref([
  {
    id: 1,
    icon: '🤖',
    title: '智能理解',
    description: '先进的NLP技术，准确理解用户意图'
  },
  {
    id: 2,
    icon: '🎯',
    title: '精准匹配',
    description: '混合检索算法，快速定位相关政策'
  },
  {
    id: 3,
    icon: '⚡',
    title: '实时响应',
    description: '流式输出技术，提供流畅的交互体验'
  },
  {
    id: 4,
    icon: '🔒',
    title: '安全可靠',
    description: '严格的权限控制，保障数据安全'
  }
])

// 方法
const goToChat = () => {
  router.push('/chat')
}

const goToCalculator = () => {
  router.push('/calculator')
}

const handleFeatureClick = (feature) => {
  router.push(feature.route)
}

const consultDomain = (domain) => {
  router.push({
    path: '/chat',
    query: { domain: domain.id }
  })
}

const askQuestion = (question) => {
  router.push({
    path: '/chat',
    query: { q: question }
  })
}
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  background: linear-gradient(180deg, #f5f7fa 0%, #ffffff 100%);
}

/* 欢迎横幅 */
.hero-banner {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: var(--spacing-xxl) var(--spacing-xl);
  position: relative;
  overflow: hidden;
}

.hero-banner::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -10%;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 70%);
  border-radius: 50%;
}

.hero-content {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-xxl);
  position: relative;
  z-index: 1;
}

.hero-text {
  flex: 1;
}

.hero-title {
  font-size: 48px;
  font-weight: 700;
  margin-bottom: var(--spacing-md);
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.logo-icon {
  font-size: 56px;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

.hero-subtitle {
  font-size: var(--font-size-xl);
  margin-bottom: var(--spacing-sm);
  opacity: 0.95;
  font-weight: 600;
}

.hero-description {
  font-size: var(--font-size-md);
  margin-bottom: var(--spacing-xl);
  opacity: 0.9;
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  gap: var(--spacing-md);
}

.hero-illustration {
  position: relative;
  width: 300px;
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.illustration-circle {
  position: absolute;
  width: 100%;
  height: 100%;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.1); opacity: 0.3; }
}

.illustration-icon {
  font-size: 120px;
  animation: rotate 10s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 统计卡片 */
.stats-section {
  max-width: var(--content-max-width);
  margin: calc(var(--spacing-xxl) * -1) auto var(--spacing-xxl);
  padding: 0 var(--spacing-xl);
  position: relative;
  z-index: 2;
}

.stat-card {
  background: white;
  padding: var(--spacing-xl);
  border-radius: var(--radius-large);
  box-shadow: var(--shadow-light);
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  transition: var(--transition-fast);
  cursor: pointer;
}

.stat-card:hover {
  transform: translateY(-5px);
  box-shadow: var(--shadow-dark);
}

.stat-icon {
  font-size: 48px;
  line-height: 1;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: var(--font-size-xxl);
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: var(--spacing-xs);
}

.stat-label {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
}

.stat-1 .stat-icon { color: #667eea; }
.stat-2 .stat-icon { color: #f093fb; }
.stat-3 .stat-icon { color: #4facfe; }
.stat-4 .stat-icon { color: #43e97b; }

/* 通用区块样式 */
.features-section,
.domains-section,
.faq-section,
.advantages-section {
  max-width: var(--content-max-width);
  margin: 0 auto var(--spacing-xxl);
  padding: 0 var(--spacing-xl);
}

.section-title {
  font-size: var(--font-size-xxl);
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: var(--spacing-xl);
  text-align: center;
  position: relative;
}

.section-title::after {
  content: '';
  position: absolute;
  bottom: -10px;
  left: 50%;
  transform: translateX(-50%);
  width: 60px;
  height: 4px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 2px;
}

/* 功能卡片 */
.feature-card {
  text-align: center;
  cursor: pointer;
  transition: var(--transition-fast);
  height: 100%;
}

.feature-card:hover {
  transform: translateY(-10px);
  box-shadow: var(--shadow-dark);
}

.feature-icon {
  font-size: 64px;
  margin-bottom: var(--spacing-lg);
}

.feature-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-md);
}

.feature-desc {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: var(--spacing-lg);
}

.feature-footer {
  display: flex;
  justify-content: center;
}

/* 政策领域 */
.domains-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-lg);
}

.domain-card {
  background: white;
  padding: var(--spacing-xl);
  border-radius: var(--radius-large);
  box-shadow: var(--shadow-base);
  text-align: center;
  cursor: pointer;
  transition: var(--transition-fast);
}

.domain-card:hover {
  transform: translateY(-5px);
  box-shadow: var(--shadow-dark);
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.domain-icon {
  font-size: 48px;
  margin-bottom: var(--spacing-md);
}

.domain-name {
  font-size: var(--font-size-md);
  font-weight: 600;
  margin-bottom: var(--spacing-sm);
}

.domain-count {
  font-size: var(--font-size-sm);
  opacity: 0.8;
}

/* 常见问题 */
.faq-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.faq-item {
  background: white;
  padding: var(--spacing-lg);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-base);
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  cursor: pointer;
  transition: var(--transition-fast);
}

.faq-item:hover {
  transform: translateX(10px);
  box-shadow: var(--shadow-light);
}

.faq-icon {
  font-size: 24px;
  color: var(--primary-color);
}

.faq-content {
  flex: 1;
}

.faq-question {
  font-size: var(--font-size-base);
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: var(--spacing-xs);
}

.faq-category {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.faq-arrow {
  color: var(--text-secondary);
  transition: var(--transition-fast);
}

.faq-item:hover .faq-arrow {
  transform: translateX(5px);
  color: var(--primary-color);
}

/* 优势卡片 */
.advantage-card {
  text-align: center;
  padding: var(--spacing-xl);
  background: white;
  border-radius: var(--radius-large);
  box-shadow: var(--shadow-base);
  transition: var(--transition-fast);
}

.advantage-card:hover {
  transform: translateY(-5px);
  box-shadow: var(--shadow-light);
}

.advantage-icon {
  font-size: 48px;
  margin-bottom: var(--spacing-md);
}

.advantage-title {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-sm);
}

.advantage-desc {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}

/* 响应式 */
@media (max-width: 768px) {
  .hero-content {
    flex-direction: column;
    text-align: center;
  }

  .hero-title {
    font-size: 32px;
    justify-content: center;
  }

  .hero-illustration {
    width: 200px;
    height: 200px;
  }

  .illustration-icon {
    font-size: 80px;
  }

  .hero-actions {
    flex-direction: column;
    width: 100%;
  }

  .hero-actions :deep(.el-button) {
    width: 100%;
  }

  .stats-section {
    margin-top: 0;
  }

  .domains-grid {
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  }
}
</style>
