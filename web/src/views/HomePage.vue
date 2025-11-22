<template>
  <div class="home-page">
    <!-- SystemAnnouncement - 系统公告 -->
    <SystemAnnouncement />

    <!-- Hero Section - 英雄区域 -->
    <section class="hero-section">
      <div class="hero-content">
        <div class="hero-text">
          <h1 class="hero-title">
            <span class="gradient-text">政府政策智能</span>
            <br>
            <span class="gradient-text">知识服务平台</span>
          </h1>
          <p class="hero-subtitle">
            基于人工智能技术，提供政策智能问答、DSL规则生成、知识图谱可视化等全方位服务
          </p>
          <div class="hero-actions">
            <el-button
              size="large"
              @click="$router.push('/agent')"
              class="hero-btn primary-btn"
            >
              <el-icon><ChatDotRound /></el-icon>
              开始智能问答
            </el-button>
            <el-button
              size="large"
              @click="$router.push('/knowledge-graph')"
              class="hero-btn secondary-btn"
            >
              <el-icon><Share /></el-icon>
              探索知识图谱
            </el-button>
            <el-button
              size="large"
              @click="$router.push('/dsl-generator')"
              class="hero-btn secondary-btn"
            >
              <el-icon><Document /></el-icon>
              DSL规则生成
            </el-button>
          </div>
        </div>
        <div class="hero-visual">
          <div class="floating-cards">
            <div class="floating-card card-1" :style="{ transform: `translateY(${cardOffset1}px)` }">
              <div class="card-icon">
                <el-icon><Document /></el-icon>
              </div>
              <span>DSL规则</span>
            </div>
            <div class="floating-card card-2" :style="{ transform: `translateY(${cardOffset2}px)` }">
              <div class="card-icon">
                <el-icon><Collection /></el-icon>
              </div>
              <span>知识库</span>
            </div>
            <div class="floating-card card-3" :style="{ transform: `translateY(${cardOffset3}px)` }">
              <div class="card-icon">
                <el-icon><Share /></el-icon>
              </div>
              <span>知识图谱</span>
            </div>
            <div class="floating-card card-4" :style="{ transform: `translateY(${cardOffset4}px)` }">
              <div class="card-icon">
                <el-icon><ChatDotRound /></el-icon>
              </div>
              <span>AI问答</span>
            </div>
          </div>
        </div>
      </div>
      <div class="hero-bg">
        <div class="bg-pattern"></div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChatDotRound,
  Document,
  Collection,
  Share,
  DataAnalysis,
  ArrowRight,
  Refresh,
  Upload,
  Search,
  TrendCharts
} from '@element-plus/icons-vue'
import SystemAnnouncement from '@/components/SystemAnnouncement.vue'

const router = useRouter()

// 浮动卡片动画
const cardOffset1 = ref(0)
const cardOffset2 = ref(0)
const cardOffset3 = ref(0)
const cardOffset4 = ref(0)

// 动画循环
const animateCards = () => {
  const time = Date.now() / 1000
  cardOffset1.value = Math.sin(time * 2) * 10
  cardOffset2.value = Math.sin(time * 2 + 1) * 10
  cardOffset3.value = Math.sin(time * 2 + 2) * 10
  cardOffset4.value = Math.sin(time * 2 + 3) * 10
  requestAnimationFrame(animateCards)
}

onMounted(() => {
  animateCards()
})
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
}

/* Hero Section */
.hero-section {
  min-height: 100vh;
  display: flex;
  align-items: center;
  position: relative;
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  overflow: hidden;
}

.hero-content {
  position: relative;
  z-index: 1;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 var(--spacing-xl);
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-2xl);
  align-items: center;
}

.hero-text {
  z-index: 2;
  animation: fadeInUp 1s ease-out;
}

.hero-title {
  font-size: 3.5rem;
  font-weight: 800;
  line-height: 1.2;
  margin-bottom: var(--spacing-lg);
}

.gradient-text {
  background: var(--primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-subtitle {
  font-size: 1.25rem;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-2xl);
  line-height: 1.6;
  max-width: 600px;
}

.hero-actions {
  display: flex;
  gap: var(--spacing-lg);
  justify-content: center;
  flex-wrap: wrap;
}

.hero-btn {
  padding: var(--spacing-md) var(--spacing-xl);
  font-size: 1rem;
  font-weight: 500;
  border-radius: var(--radius-full);
  transition: all var(--transition-base);
  border: 2px solid transparent;
  background: var(--primary-gradient);
  color: white;
}

.hero-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 25px rgba(0, 82, 217, 0.3);
}

.primary-btn {
  background: white;
  color: var(--primary-color);
  border: none;
}

.primary-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 20px 40px rgba(0,0,0,0.2);
}

.secondary-btn {
  background: transparent;
  color: var(--primary-color);
  border-color: var(--primary-color);
}

.secondary-btn:hover {
  background: var(--primary-color);
  color: white;
}

/* Hero Visual */
.hero-visual {
  position: relative;
  height: 600px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.floating-cards {
  position: relative;
  width: 100%;
  height: 100%;
  perspective: 1000px;
}

.floating-card {
  position: absolute;
  width: 120px;
  height: 120px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.floating-card:hover {
  transform: translateY(-10px) scale(1.1);
  box-shadow: 0 30px 60px rgba(0, 0, 0, 0.15);
}

.card-icon {
  width: 60px;
  height: 60px;
  background: var(--primary-gradient);
  border-radius: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
}

.floating-card span {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.card-1 {
  top: 20%;
  left: 20%;
  animation: float 6s ease-in-out infinite;
}

.card-2 {
  top: 60%;
  left: 10%;
  animation: float 8s ease-in-out infinite;
}

.card-3 {
  top: 30%;
  right: 15%;
  animation: float 7s ease-in-out infinite;
}

.card-4 {
  top: 70%;
  right: 20%;
  animation: float 9s ease-in-out infinite;
}

/* Background */
.hero-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  opacity: 0.1;
}

.bg-pattern {
  width: 100%;
  height: 100%;
  background-image:
    radial-gradient(circle at 20% 80%, rgba(0, 82, 217, 0.3) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(200, 35, 44, 0.3) 0%, transparent 50%),
    radial-gradient(circle at 40% 40%, rgba(0, 82, 217, 0.2) 0%, transparent 50%);
}

/* Animations */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes float {
  0%, 100% {
    transform: translateY(0px) rotate(0deg);
  }
  50% {
    transform: translateY(-20px) rotate(5deg);
  }
}

/* 响应式 */
@media (max-width: 1200px) {
  .hero-content {
    grid-template-columns: 1fr;
    gap: var(--spacing-xl);
  }

  .hero-visual {
    height: 400px;
  }

  .hero-title {
    font-size: 2.5rem;
  }
}

@media (max-width: 768px) {
  .hero-title {
    font-size: 2rem;
  }

  .hero-subtitle {
    font-size: 1rem;
  }

  .hero-actions {
    flex-direction: column;
    align-items: center;
  }

  .hero-btn {
    width: 200px;
  }

  .floating-card {
    width: 100px;
    height: 100px;
  }

  .card-icon {
    width: 50px;
    height: 50px;
    font-size: 20px;
  }
}
</style>