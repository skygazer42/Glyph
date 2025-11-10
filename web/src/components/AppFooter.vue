<template>
  <footer class="app-footer">
    <div class="footer-content">
      <div class="footer-section">
        <h4>关于平台</h4>
        <p>政府政策智能分析平台致力于为政府决策提供智能化支持</p>
      </div>

      <div class="footer-section">
        <h4>功能模块</h4>
        <ul>
          <li>政策智能问答</li>
          <li>DSL规则生成</li>
          <li>知识库管理</li>
        </ul>
      </div>

      <div class="footer-section">
        <h4>技术支持</h4>
        <p>基于先进的AI技术和知识图谱</p>
        <p>支持多源数据融合与智能分析</p>
      </div>
    </div>

    <div class="footer-bottom">
      <div class="copyright">
        <p>© {{ currentYear }} 政府政策智能分析平台 版权所有</p>
        <p class="icp">备案号：XXX-XXXXXXXX</p>
      </div>
      <div class="footer-links">
        <a href="#" @click.prevent>隐私政策</a>
        <span>|</span>
        <a href="#" @click.prevent>使用条款</a>
        <span>|</span>
        <a href="#" @click.prevent>帮助中心</a>
      </div>
    </div>
  </footer>
</template>

<script setup>
import { computed } from 'vue'

const currentYear = computed(() => new Date().getFullYear())
</script>

<style scoped>
.app-footer {
  background: linear-gradient(to bottom, #1f2937, #111827);
  color: rgba(255, 255, 255, 0.8);
  padding: var(--spacing-2xl) 0 var(--spacing-lg);
  margin-top: auto;
}

.footer-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--spacing-xl);
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: var(--spacing-2xl);
  margin-bottom: var(--spacing-xl);
}

.footer-section h4 {
  color: white;
  font-size: var(--text-lg);
  font-weight: 600;
  margin-bottom: var(--spacing-md);
  border-bottom: 2px solid var(--secondary-color);
  padding-bottom: var(--spacing-sm);
  display: inline-block;
}

.footer-section p {
  line-height: 1.8;
  margin: var(--spacing-sm) 0;
  font-size: var(--text-sm);
}

.footer-section ul {
  list-style: none;
  padding: 0;
}

.footer-section li {
  padding: var(--spacing-xs) 0;
  font-size: var(--text-sm);
  transition: color var(--transition-base);
}

.footer-section li:hover {
  color: white;
  padding-left: var(--spacing-xs);
}

.footer-bottom {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--spacing-lg) var(--spacing-xl) 0;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-md);
}

.copyright {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.copyright p {
  margin: 0;
  font-size: var(--text-xs);
  color: rgba(255, 255, 255, 0.6);
}

.icp {
  font-size: 0.7rem !important;
}

.footer-links {
  display: flex;
  gap: var(--spacing-md);
  align-items: center;
  font-size: var(--text-sm);
}

.footer-links a {
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  transition: color var(--transition-base);
}

.footer-links a:hover {
  color: white;
}

.footer-links span {
  color: rgba(255, 255, 255, 0.3);
}

@media (max-width: 768px) {
  .footer-content {
    grid-template-columns: 1fr;
    gap: var(--spacing-lg);
  }

  .footer-bottom {
    flex-direction: column;
    text-align: center;
  }
}
</style>
