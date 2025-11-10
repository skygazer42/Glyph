<template>
  <div class="chat-consultation">
    <!-- 侧边栏 - 会话列表和快捷功能 -->
    <div class="chat-sidebar" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
      <div class="sidebar-header">
        <h3 v-if="!sidebarCollapsed">我的咨询</h3>
        <el-button
          circle
          :icon="sidebarCollapsed ? Expand : Fold"
          @click="toggleSidebar"
        />
      </div>

      <template v-if="!sidebarCollapsed">
        <!-- 新建会话按钮 -->
        <el-button
          class="new-chat-btn"
          type="primary"
          @click="createNewSession"
          :icon="Plus"
        >
          新建咨询
        </el-button>

        <!-- 快捷问题模板 -->
        <div class="quick-templates">
          <div class="template-title">常见问题</div>
          <div
            v-for="template in quickTemplates"
            :key="template.id"
            class="template-item"
            @click="useTemplate(template)"
          >
            <el-icon>{{ template.icon }}</el-icon>
            <span>{{ template.text }}</span>
          </div>
        </div>

        <!-- 政策领域过滤 -->
        <div class="domain-filter">
          <div class="template-title">政策领域</div>
          <el-checkbox-group v-model="selectedDomains">
            <el-checkbox
              v-for="domain in policyDomains"
              :key="domain.value"
              :label="domain.value"
            >
              <el-icon>{{ domain.icon }}</el-icon>
              {{ domain.label }}
            </el-checkbox>
          </el-checkbox-group>
        </div>
      </template>
    </div>

    <!-- 主聊天区域 -->
    <div class="chat-main">
      <!-- 聊天头部 -->
      <div class="chat-header">
        <div class="header-left">
          <el-icon class="header-icon" :size="28"><ChatDotRound /></el-icon>
          <div class="header-info">
            <h2 class="header-title">智策通AI助手</h2>
            <p class="header-subtitle">为您提供精准的政策解答服务</p>
          </div>
        </div>
        <div class="header-right">
          <!-- 流式开关 -->
          <el-switch
            v-model="useStreaming"
            active-text="流式响应"
            :disabled="isLoading"
          />
          <!-- 连接状态 -->
          <el-tag :type="connectionStatus.type" effect="plain">
            <el-icon><CircleCheck v-if="connectionStatus.connected" /><Warning v-else /></el-icon>
            {{ connectionStatus.text }}
          </el-tag>
          <!-- 会话ID -->
          <el-tooltip v-if="currentSessionId" content="当前会话ID" placement="bottom">
            <el-tag type="info">
              <el-icon><Key /></el-icon>
              {{ currentSessionId.substring(0, 8) }}
            </el-tag>
          </el-tooltip>
          <!-- 清空按钮 -->
          <el-button
            :icon="Delete"
            @click="confirmClearChat"
            :disabled="messages.length === 0"
          >
            清空对话
          </el-button>
        </div>
      </div>

      <!-- 消息列表 -->
      <div class="messages-container" ref="messagesContainer">
        <!-- 欢迎提示 -->
        <div v-if="messages.length === 0" class="welcome-section">
          <div class="welcome-icon">👋</div>
          <h3 class="welcome-title">您好，我是智策通AI助手</h3>
          <p class="welcome-desc">我可以帮您解答各类政策问题，快速计算补贴额度</p>

          <!-- 示例问题 -->
          <div class="example-questions">
            <div class="example-title">您可以问我：</div>
            <div class="example-grid">
              <div
                v-for="example in exampleQuestions"
                :key="example.id"
                class="example-card"
                @click="askExample(example)"
              >
                <el-icon class="example-icon">{{ example.icon }}</el-icon>
                <div class="example-text">{{ example.question }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <div
          v-for="(message, index) in messages"
          :key="index"
          class="message-item"
          :class="message.role"
        >
          <!-- 用户消息 -->
          <div v-if="message.role === 'user'" class="message-bubble user-bubble">
            <div class="message-content">{{ message.content }}</div>
            <div class="message-footer">
              <span class="message-time">{{ message.timestamp }}</span>
            </div>
          </div>

          <!-- AI回复 -->
          <div v-else class="message-bubble ai-bubble">
            <div class="message-avatar">
              <el-avatar :size="40" src="/logo.png">
                <el-icon><Robot /></el-icon>
              </el-avatar>
              <span class="avatar-label">智策通</span>
            </div>

            <div class="message-body">
              <!-- 回复内容 -->
              <div class="message-content" v-html="formatMarkdown(message.content)"></div>

              <!-- 元数据展示 -->
              <div v-if="message.metadata" class="message-metadata">
                <el-collapse accordion>
                  <el-collapse-item name="metadata">
                    <template #title>
                      <el-icon><InfoFilled /></el-icon>
                      <span>查看详细信息</span>
                    </template>
                    <div class="metadata-content">
                      <div class="metadata-row" v-if="message.metadata.intent">
                        <span class="meta-label">识别意图：</span>
                        <el-tag type="primary" size="small">{{ message.metadata.intent }}</el-tag>
                      </div>
                      <div class="metadata-row" v-if="message.metadata.route">
                        <span class="meta-label">处理路由：</span>
                        <el-tag type="success" size="small">{{ message.metadata.route }}</el-tag>
                      </div>
                      <div class="metadata-row" v-if="message.metadata.confidence">
                        <span class="meta-label">置信度：</span>
                        <el-progress
                          :percentage="Math.round(message.metadata.confidence * 100)"
                          :color="getConfidenceColor(message.metadata.confidence)"
                          :stroke-width="8"
                          style="width: 200px"
                        />
                      </div>
                      <div class="metadata-row" v-if="message.metadata.sources && message.metadata.sources.length">
                        <span class="meta-label">参考来源：</span>
                        <div class="sources-list">
                          <el-tag
                            v-for="(source, idx) in message.metadata.sources"
                            :key="idx"
                            size="small"
                            effect="plain"
                          >
                            {{ source }}
                          </el-tag>
                        </div>
                      </div>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>

              <!-- 操作按钮 -->
              <div class="message-actions">
                <el-button size="small" text :icon="CopyDocument" @click="copyMessage(message.content)">
                  复制
                </el-button>
                <el-button size="small" text :icon="Star">
                  收藏
                </el-button>
                <el-button size="small" text :icon="Share">
                  分享
                </el-button>
              </div>

              <div class="message-footer">
                <span class="message-time">{{ message.timestamp }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 加载指示器 -->
        <div v-if="isLoading" class="message-item assistant">
          <div class="message-bubble ai-bubble">
            <div class="message-avatar">
              <el-avatar :size="40">
                <el-icon><Robot /></el-icon>
              </el-avatar>
              <span class="avatar-label">智策通</span>
            </div>
            <div class="message-body">
              <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <div class="loading-text">正在思考中...</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-container">
        <div class="input-wrapper">
          <el-input
            v-model="userInput"
            type="textarea"
            :rows="3"
            placeholder="请输入您的问题..."
            :disabled="isLoading"
            @keydown.ctrl.enter="sendMessage"
            class="message-input"
          />
          <div class="input-footer">
            <div class="input-tips">
              <el-icon><QuestionFilled /></el-icon>
              <span>Ctrl + Enter 发送</span>
            </div>
            <div class="input-actions">
              <el-button @click="clearInput" :disabled="!userInput || isLoading">
                清空
              </el-button>
              <el-button
                type="primary"
                @click="sendMessage"
                :loading="isLoading"
                :disabled="!userInput.trim()"
                :icon="Promotion"
              >
                {{ isLoading ? '发送中...' : '发送' }}
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ChatDotRound, Plus, Expand, Fold, Delete, CopyDocument, Star, Share,
  Robot, CircleCheck, Warning, Key, InfoFilled, QuestionFilled, Promotion
} from '@element-plus/icons-vue'
import { agentApi } from '@/api'

// 响应式数据
const route = useRoute()
const messagesContainer = ref(null)
const userInput = ref('')
const messages = ref([])
const isLoading = ref(false)
const useStreaming = ref(true)
const currentSessionId = ref(null)
const sidebarCollapsed = ref(false)
const selectedDomains = ref([])

// 连接状态
const connectionStatus = computed(() => {
  // 这里可以添加实际的连接检测逻辑
  return {
    connected: true,
    type: 'success',
    text: '服务正常'
  }
})

// 政策领域
const policyDomains = ref([
  { label: '汽车补贴', value: 'car', icon: '🚗' },
  { label: '家电补贴', value: 'appliance', icon: '🏠' },
  { label: '消费券', value: 'voucher', icon: '🎫' },
  { label: '以旧换新', value: 'trade_in', icon: '♻️' },
  { label: '保险补贴', value: 'insurance', icon: '🛡️' }
])

// 快捷模板
const quickTemplates = ref([
  { id: 1, text: '补贴政策查询', icon: '🔍' },
  { id: 2, text: '申请流程咨询', icon: '📝' },
  { id: 3, text: '补贴额度计算', icon: '🧮' },
  { id: 4, text: '政策对比分析', icon: '📊' }
])

// 示例问题
const exampleQuestions = ref([
  {
    id: 1,
    icon: '🚗',
    question: '购买新能源汽车可以享受哪些补贴？'
  },
  {
    id: 2,
    icon: '🏠',
    question: '家电以旧换新的补贴标准是什么？'
  },
  {
    id: 3,
    icon: '🎫',
    question: '消费券的使用规则和限制有哪些？'
  },
  {
    id: 4,
    icon: '♻️',
    question: '如何申请以旧换新补贴？'
  }
])

// 生命周期
onMounted(() => {
  // 检查URL参数
  if (route.query.q) {
    userInput.value = route.query.q
    sendMessage()
  }
  if (route.query.domain) {
    selectedDomains.value = [route.query.domain]
  }

  // 生成或恢复会话ID
  currentSessionId.value = generateSessionId()
})

// 监听消息变化，自动滚动
watch(messages, () => {
  nextTick(() => {
    scrollToBottom()
  })
}, { deep: true })

// 方法
const generateSessionId = () => {
  return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const createNewSession = () => {
  if (messages.value.length > 0) {
    ElMessageBox.confirm(
      '开始新会话将清空当前对话，是否继续？',
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    ).then(() => {
      messages.value = []
      currentSessionId.value = generateSessionId()
      ElMessage.success('已创建新会话')
    }).catch(() => {})
  }
}

const useTemplate = (template) => {
  userInput.value = template.text
}

const askExample = (example) => {
  userInput.value = example.question
  sendMessage()
}

const sendMessage = async () => {
  if (!userInput.value.trim() || isLoading.value) return

  const query = userInput.value.trim()

  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: query,
    timestamp: formatTimestamp(new Date())
  })

  userInput.value = ''
  isLoading.value = true

  try {
    if (useStreaming.value) {
      await sendStreamingMessage(query)
    } else {
      await sendNormalMessage(query)
    }
  } catch (error) {
    console.error('发送消息失败:', error)
    messages.value.push({
      role: 'assistant',
      content: '抱歉，服务暂时不可用，请稍后再试。',
      timestamp: formatTimestamp(new Date()),
      metadata: null
    })
  } finally {
    isLoading.value = false
  }
}

const sendNormalMessage = async (query) => {
  const response = await agentApi.chat({
    query,
    session_id: currentSessionId.value,
    domains: selectedDomains.value
  })

  messages.value.push({
    role: 'assistant',
    content: response.answer,
    timestamp: formatTimestamp(new Date()),
    metadata: {
      intent: response.intent,
      route: response.route,
      confidence: response.confidence,
      sources: response.sources || []
    }
  })
}

const sendStreamingMessage = async (query) => {
  // 创建一个临时消息用于流式更新
  const assistantMessage = {
    role: 'assistant',
    content: '',
    timestamp: formatTimestamp(new Date()),
    metadata: null
  }
  messages.value.push(assistantMessage)

  try {
    const eventSource = await agentApi.chatStream({
      query,
      session_id: currentSessionId.value,
      domains: selectedDomains.value
    })

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === 'session') {
          // 会话初始化
          currentSessionId.value = data.session_id
        } else if (data.type === 'message') {
          // 流式内容
          assistantMessage.content += data.content
        } else if (data.type === 'metadata') {
          // 元数据
          assistantMessage.metadata = data.metadata
        } else if (data.type === 'done') {
          // 完成
          eventSource.close()
        }
      } catch (error) {
        console.error('解析流式数据失败:', error)
      }
    }

    eventSource.onerror = (error) => {
      console.error('流式连接错误:', error)
      eventSource.close()
      if (!assistantMessage.content) {
        assistantMessage.content = '抱歉，连接中断，请重试。'
      }
    }
  } catch (error) {
    assistantMessage.content = '抱歉，服务暂时不可用，请稍后再试。'
    throw error
  }
}

const clearInput = () => {
  userInput.value = ''
}

const confirmClearChat = () => {
  ElMessageBox.confirm(
    '确定要清空所有对话吗？',
    '提示',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    messages.value = []
    ElMessage.success('对话已清空')
  }).catch(() => {})
}

const copyMessage = async (content) => {
  try {
    await navigator.clipboard.writeText(content)
    ElMessage.success('已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const formatTimestamp = (date) => {
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  return `${hours}:${minutes}`
}

const formatMarkdown = (text) => {
  // 简单的 Markdown 渲染
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

const getConfidenceColor = (confidence) => {
  if (confidence >= 0.8) return '#67c23a'
  if (confidence >= 0.6) return '#e6a23c'
  return '#f56c6c'
}
</script>

<style scoped>
.chat-consultation {
  display: flex;
  height: calc(100vh - 60px);
  background: var(--bg-secondary);
}

/* 侧边栏 */
.chat-sidebar {
  width: 280px;
  background: white;
  border-right: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  transition: var(--transition-fast);
  overflow-y: auto;
}

.chat-sidebar.sidebar-collapsed {
  width: 60px;
}

.sidebar-header {
  padding: var(--spacing-lg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-lighter);
}

.sidebar-header h3 {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.new-chat-btn {
  margin: var(--spacing-lg);
  width: calc(100% - var(--spacing-lg) * 2);
}

.quick-templates,
.domain-filter {
  padding: var(--spacing-lg);
  border-top: 1px solid var(--border-lighter);
}

.template-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
}

.template-item {
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-base);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: var(--font-size-sm);
  transition: var(--transition-fast);
  margin-bottom: var(--spacing-xs);
}

.template-item:hover {
  background: var(--bg-secondary);
  color: var(--primary-color);
}

.domain-filter :deep(.el-checkbox) {
  display: flex;
  margin-bottom: var(--spacing-sm);
}

/* 主聊天区域 */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
}

/* 聊天头部 */
.chat-header {
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid var(--border-lighter);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: white;
  flex-wrap: wrap;
  gap: var(--spacing-md);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.header-icon {
  color: var(--primary-color);
}

.header-title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.header-subtitle {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

/* 消息容器 */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-xl);
  background: #f8f9fa;
}

/* 欢迎区域 */
.welcome-section {
  text-align: center;
  padding: var(--spacing-xxl);
  max-width: 800px;
  margin: 0 auto;
}

.welcome-icon {
  font-size: 80px;
  margin-bottom: var(--spacing-lg);
  animation: wave 2s ease-in-out infinite;
}

@keyframes wave {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(20deg); }
  75% { transform: rotate(-20deg); }
}

.welcome-title {
  font-size: var(--font-size-xxl);
  font-weight: 600;
  margin-bottom: var(--spacing-sm);
  color: var(--text-primary);
}

.welcome-desc {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xxl);
}

.example-questions {
  margin-top: var(--spacing-xxl);
}

.example-title {
  font-size: var(--font-size-md);
  font-weight: 600;
  margin-bottom: var(--spacing-lg);
  color: var(--text-primary);
}

.example-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-md);
}

.example-card {
  padding: var(--spacing-lg);
  background: white;
  border-radius: var(--radius-large);
  box-shadow: var(--shadow-base);
  cursor: pointer;
  transition: var(--transition-fast);
  text-align: left;
}

.example-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-light);
  border: 2px solid var(--primary-color);
}

.example-icon {
  font-size: 32px;
  margin-bottom: var(--spacing-sm);
}

.example-text {
  font-size: var(--font-size-sm);
  color: var(--text-regular);
  line-height: 1.5;
}

/* 消息项 */
.message-item {
  margin-bottom: var(--spacing-xl);
  animation: messageSlideIn 0.3s ease-out;
}

@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-bubble {
  max-width: 80%;
}

.user-bubble {
  margin-left: auto;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: var(--spacing-lg);
  border-radius: var(--radius-large) var(--radius-large) 0 var(--radius-large);
  box-shadow: var(--shadow-base);
}

.ai-bubble {
  display: flex;
  gap: var(--spacing-md);
  align-items: flex-start;
}

.message-avatar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
}

.avatar-label {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

.message-body {
  flex: 1;
  background: white;
  padding: var(--spacing-lg);
  border-radius: var(--radius-large);
  box-shadow: var(--shadow-base);
}

.message-content {
  line-height: 1.6;
  color: var(--text-primary);
  word-wrap: break-word;
}

.user-bubble .message-content {
  color: white;
}

.message-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--spacing-sm);
}

.message-time {
  font-size: var(--font-size-xs);
  opacity: 0.7;
}

/* 元数据 */
.message-metadata {
  margin-top: var(--spacing-md);
}

.metadata-content {
  padding: var(--spacing-md);
}

.metadata-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-sm);
}

.meta-label {
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 80px;
}

.sources-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

/* 操作按钮 */
.message-actions {
  display: flex;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-lighter);
}

/* 输入区域 */
.input-container {
  padding: var(--spacing-lg) var(--spacing-xl);
  border-top: 1px solid var(--border-lighter);
  background: white;
}

.input-wrapper {
  max-width: 1000px;
  margin: 0 auto;
}

.message-input :deep(.el-textarea__inner) {
  border: 2px solid var(--border-base);
  border-radius: var(--radius-base);
  font-size: var(--font-size-base);
  resize: none;
  transition: var(--transition-fast);
}

.message-input :deep(.el-textarea__inner:focus) {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.1);
}

.input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--spacing-md);
}

.input-tips {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.input-actions {
  display: flex;
  gap: var(--spacing-sm);
}

/* 加载动画 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: var(--spacing-sm) 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--primary-color);
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    opacity: 0.3;
    transform: translateY(0);
  }
  30% {
    opacity: 1;
    transform: translateY(-10px);
  }
}

.loading-text {
  margin-top: var(--spacing-sm);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

/* 响应式 */
@media (max-width: 768px) {
  .chat-sidebar {
    position: absolute;
    z-index: 100;
    height: 100%;
  }

  .chat-sidebar.sidebar-collapsed {
    width: 0;
    overflow: hidden;
  }

  .chat-header {
    padding: var(--spacing-md);
  }

  .header-left {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-right {
    width: 100%;
    justify-content: space-between;
  }

  .messages-container {
    padding: var(--spacing-md);
  }

  .message-bubble {
    max-width: 90%;
  }

  .example-grid {
    grid-template-columns: 1fr;
  }
}
</style>
