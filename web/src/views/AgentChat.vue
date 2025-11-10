<template>
  <div class="agent-chat-container">
    <el-card class="chat-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button
              :icon="MenuIcon"
              size="small"
              @click="showSessionDrawer = true"
              class="session-toggle"
            >
              会话列表
            </el-button>
            <el-icon size="24"><ChatDotRound /></el-icon>
            <span class="title">AI 政策助手</span>
          </div>
          <div class="header-right">
            <el-switch
              v-model="useStreaming"
              active-text="流式"
              inactive-text="普通"
              :disabled="loading"
              style="margin-right: 10px"
            />
            <el-tag :type="isConnected ? 'success' : 'danger'">
              {{ isConnected ? '已连接' : '未连接' }}
            </el-tag>
            <el-tag v-if="sessionId" type="info" size="small">
              会话: {{ sessionId.substring(0, 8) }}...
            </el-tag>
            <el-button
              size="small"
              :icon="Delete"
              @click="clearChat"
              :disabled="messages.length === 0"
            >
              清空对话
            </el-button>
          </div>
        </div>
      </template>

      <!-- 聊天消息区域 -->
      <div class="chat-messages" ref="messagesContainer">
        <el-empty
          v-if="messages.length === 0"
          description="开始和AI助手对话吧！"
          :image-size="120"
        />

        <div
          v-for="(message, index) in messages"
          :key="index"
          class="message-wrapper"
          :class="message.role"
        >
          <div class="message-avatar">
            <el-avatar
              :icon="message.role === 'user' ? User : Robot"
              :style="{ backgroundColor: message.role === 'user' ? '#409eff' : '#67c23a' }"
            />
          </div>
          <div class="message-content">
            <div class="message-header">
              <span class="message-role">
                {{ message.role === 'user' ? '你' : 'AI助手' }}
              </span>
              <div class="message-actions">
                <el-button
                  :icon="CopyDocument"
                  size="small"
                  text
                  @click="copyMessage(message)"
                  title="复制消息"
                  class="copy-btn"
                />
                <span class="message-time">{{ message.time }}</span>
              </div>
            </div>
            <div class="message-text" v-html="formatMessage(message.content)"></div>
            <div v-if="message.metadata" class="message-meta">
              <el-tag size="small" type="info">{{ message.metadata.model }}</el-tag>
            </div>
          </div>
        </div>

        <!-- 加载动画 -->
        <div v-if="loading" class="message-wrapper assistant">
          <div class="message-avatar">
            <el-avatar :icon="Robot" style="background-color: #67c23a" />
          </div>
          <div class="message-content">
            <div class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="chat-input-area">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="3"
          placeholder="输入你的问题..."
          @keydown.ctrl.enter="sendMessage"
          :disabled="loading"
        />
        <div class="input-actions">
          <div class="input-tips">
            <el-text size="small" type="info">
              按 Ctrl+Enter 发送
            </el-text>
          </div>
          <el-button
            type="primary"
            :icon="Promotion"
            @click="sendMessage"
            :loading="loading"
            :disabled="!inputMessage.trim()"
          >
            发送
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 侧边栏：示例问题 -->
    <el-card class="examples-card">
      <template #header>
        <div class="card-header">
          <el-icon><QuestionFilled /></el-icon>
          <span>示例问题</span>
        </div>
      </template>

      <div class="example-questions">
        <el-button
          v-for="(question, index) in exampleQuestions"
          :key="index"
          class="example-btn"
          @click="askExample(question)"
          :disabled="loading"
          text
        >
          {{ question }}
        </el-button>
      </div>
    </el-card>

    <!-- 会话管理抽屉 -->
    <el-drawer
      v-model="showSessionDrawer"
      title="会话管理"
      direction="ltr"
      :size="360"
    >
      <SessionManager
        ref="sessionManagerRef"
        :current-session-id="sessionId"
        @session-change="handleSessionChange"
        @session-create="handleSessionCreate"
        @session-delete="handleSessionDelete"
      />
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onMounted, watch } from 'vue'
import { agentApi } from '@/api'
import { ElMessage } from 'element-plus'
import {
  ChatDotRound,
  Delete,
  User,
  Robot,
  Promotion,
  QuestionFilled,
  CopyDocument,
  Menu as MenuIcon
} from '@element-plus/icons-vue'
import SessionManager from '@/components/SessionManager.vue'
import { useChatHistory, useSessionList } from '@/composables/useLocalStorage'

// 状态
const inputMessage = ref('')
const loading = ref(false)
const isConnected = ref(true)
const messagesContainer = ref(null)
const useStreaming = ref(true) // 是否使用流式响应
const sessionId = ref(null) // 会话ID
const showSessionDrawer = ref(false) // 显示会话侧边栏
const sessionManagerRef = ref(null) // 会话管理器引用

// 会话管理
const { sessions, upsertSession, updateSessionActivity } = useSessionList()

// 当前会话的消息历史（使用 localStorage 持久化）
let chatHistory = null
const messages = ref([])

// 初始化或切换会话时加载历史
const loadSession = (newSessionId) => {
  sessionId.value = newSessionId

  // 创建或加载会话历史
  chatHistory = useChatHistory(newSessionId)
  messages.value = chatHistory.messages.value

  // 更新会话活跃时间
  updateSessionActivity(newSessionId)

  // 滚动到底部
  nextTick(() => scrollToBottom())
}

// 示例问题
const exampleQuestions = [
  '什么是政策DSL？',
  '如何使用知识库功能？',
  '济南市有哪些消费补贴政策？',
  '如何上传和管理文档？'
]

// 格式化消息（支持简单的Markdown）
const formatMessage = (text) => {
  if (!text) return ''

  // 简单的markdown转换
  return text
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 复制消息到剪贴板
const copyMessage = async (message) => {
  try {
    await navigator.clipboard.writeText(message.content)
    ElMessage.success('已复制到剪贴板')
  } catch (error) {
    // 降级方案：使用 document.execCommand
    const textarea = document.createElement('textarea')
    textarea.value = message.content
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()

    try {
      document.execCommand('copy')
      ElMessage.success('已复制到剪贴板')
    } catch (err) {
      ElMessage.error('复制失败')
    } finally {
      document.body.removeChild(textarea)
    }
  }
}

// 添加消息到历史
const addMessageToHistory = (message) => {
  if (chatHistory) {
    chatHistory.addMessage(message)
  }

  // 更新会话信息
  const session = sessions.value.find(s => s.id === sessionId.value)
  if (session && sessionManagerRef.value) {
    sessionManagerRef.value.updateSession(sessionId.value, {
      lastMessage: message.content,
      lastActive: new Date().toISOString(),
      messageCount: messages.value.length
    })
  }
}

// 发送消息（流式）
const sendMessageStream = async (userMessage) => {
  // 添加用户消息
  const userMsg = {
    role: 'user',
    content: userMessage,
    time: new Date().toLocaleTimeString()
  }
  messages.value.push(userMsg)
  addMessageToHistory(userMsg)

  // 添加空的助手消息（用于流式更新）
  const assistantMessageIndex = messages.value.length
  const assistantMsg = {
    role: 'assistant',
    content: '',
    time: new Date().toLocaleTimeString(),
    metadata: null
  }
  messages.value.push(assistantMsg)

  scrollToBottom()
  loading.value = true

  try {
    // 使用EventSource接收SSE流
    const url = `/api/agent/chat/stream`
    const payload = {
      message: userMessage,
      session_id: sessionId.value
    }

    // 使用fetch发送POST请求并接收SSE
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload)
    })

    if (!response.ok) {
      throw new Error('请求失败')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() // 保留不完整的行

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.substring(6)
          try {
            const parsed = JSON.parse(data)

            if (parsed.error) {
              throw new Error(parsed.error)
            }

            // 更新会话ID
            if (parsed.session_id && !sessionId.value) {
              sessionId.value = parsed.session_id
            }

            // 更新消息内容
            if (parsed.content) {
              messages.value[assistantMessageIndex].content += parsed.content
              scrollToBottom()
            }

            // 处理完成信号
            if (parsed.done) {
              if (parsed.metadata) {
                messages.value[assistantMessageIndex].metadata = parsed.metadata
              }
              break
            }
          } catch (e) {
            console.error('解析SSE数据失败:', e, data)
          }
        }
      }
    }

    // 如果没有收到任何内容，显示错误
    if (!messages.value[assistantMessageIndex].content) {
      messages.value[assistantMessageIndex].content = '抱歉，没有收到回复。'
    }

    // 保存助手消息到历史
    addMessageToHistory(messages.value[assistantMessageIndex])

  } catch (error) {
    console.error('流式发送消息失败:', error)

    // 更新错误消息
    messages.value[assistantMessageIndex].content = '抱歉，我遇到了一些问题，请稍后再试。'
    addMessageToHistory(messages.value[assistantMessageIndex])
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// 发送消息
const sendMessage = async () => {
  if (!inputMessage.value.trim() || loading.value) return

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''

  // 根据设置选择流式或非流式
  if (useStreaming.value) {
    await sendMessageStream(userMessage)
  } else {
    await sendMessageNonStream(userMessage)
  }
}

// 发送消息（非流式）
const sendMessageNonStream = async (userMessage) => {
  // 添加用户消息
  const userMsg = {
    role: 'user',
    content: userMessage,
    time: new Date().toLocaleTimeString()
  }
  messages.value.push(userMsg)
  addMessageToHistory(userMsg)

  scrollToBottom()
  loading.value = true

  try {
    // 调用API
    const response = await agentApi.chat(userMessage, sessionId.value)

    if (response.success) {
      // 更新会话ID
      if (response.session_id) {
        sessionId.value = response.session_id
      }

      // 添加助手回复
      const assistantMsg = {
        role: 'assistant',
        content: response.message,
        time: new Date().toLocaleTimeString(),
        metadata: response.metadata
      }
      messages.value.push(assistantMsg)
      addMessageToHistory(assistantMsg)
    } else {
      throw new Error('获取回复失败')
    }
  } catch (error) {
    console.error('发送消息失败:', error)

    // 添加错误消息
    const errorMsg = {
      role: 'assistant',
      content: '抱歉，我遇到了一些问题，请稍后再试。',
      time: new Date().toLocaleTimeString()
    }
    messages.value.push(errorMsg)
    addMessageToHistory(errorMsg)
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

// 清空对话
const clearChat = () => {
  if (chatHistory) {
    chatHistory.clearMessages()
  }
  messages.value = []

  // 更新会话信息
  if (sessionManagerRef.value) {
    sessionManagerRef.value.updateSession(sessionId.value, {
      lastMessage: '',
      messageCount: 0
    })
  }

  ElMessage.success('对话已清空')
}

// 点击示例问题
const askExample = (question) => {
  inputMessage.value = question
  sendMessage()
}

// 检查连接状态
const checkConnection = async () => {
  try {
    const response = await fetch('/api/health')
    isConnected.value = response.ok
  } catch {
    isConnected.value = false
  }
}

// 会话切换
const handleSessionChange = (newSessionId) => {
  loadSession(newSessionId)
  showSessionDrawer.value = false
}

// 创建新会话
const handleSessionCreate = (newSessionId) => {
  loadSession(newSessionId)
  showSessionDrawer.value = false
}

// 删除会话
const handleSessionDelete = (deletedSessionId) => {
  // 如果删除的是当前会话，创建新会话
  if (deletedSessionId === sessionId.value || !deletedSessionId) {
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // 创建新会话
    upsertSession({
      id: newSessionId,
      title: '新对话',
      createdAt: new Date().toISOString(),
      lastActive: new Date().toISOString(),
      messageCount: 0,
      lastMessage: ''
    })

    loadSession(newSessionId)
  }
}

// 初始化
onMounted(() => {
  checkConnection()
  // 每30秒检查一次连接状态
  setInterval(checkConnection, 30000)

  // 加载或创建第一个会话
  if (sessions.value.length > 0) {
    // 加载最近的会话
    const latestSession = sessions.value.sort((a, b) =>
      new Date(b.lastActive) - new Date(a.lastActive)
    )[0]
    loadSession(latestSession.id)
  } else {
    // 创建新会话
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    upsertSession({
      id: newSessionId,
      title: '新对话',
      createdAt: new Date().toISOString(),
      lastActive: new Date().toISOString(),
      messageCount: 0,
      lastMessage: ''
    })
    loadSession(newSessionId)
  }
})
</script>

<style scoped>
.agent-chat-container {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: var(--spacing-lg);
  height: calc(100vh - 120px);
  animation: fadeIn 0.4s ease;
}

.chat-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  border-radius: var(--radius-xl);
  overflow: hidden;
  box-shadow: var(--shadow-lg);
  background: white;
}

.chat-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
  background: linear-gradient(to bottom, #fafbfc 0%, #f0f3f7 100%);
}

.message-wrapper {
  display: flex;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  animation: slideIn 0.3s ease;
}

.message-wrapper.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.message-content {
  max-width: 70%;
  background: white;
  border-radius: var(--radius-lg);
  padding: var(--spacing-md) var(--spacing-lg);
  box-shadow: var(--shadow-md);
  transition: all var(--transition-base);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.message-content:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-1px);
}

.message-wrapper.user .message-content {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
  opacity: 0.8;
}

.message-role {
  font-weight: 600;
}

.message-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.copy-btn {
  opacity: 0;
  transition: opacity var(--transition-fast);
  padding: 4px;
}

.message-content:hover .copy-btn {
  opacity: 1;
}

.session-toggle {
  margin-right: var(--spacing-sm);
}

.message-text {
  line-height: 1.6;
  word-break: break-word;
}

.message-text :deep(code) {
  background: rgba(0,0,0,0.05);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
}

.message-wrapper.user .message-text :deep(code) {
  background: rgba(255,255,255,0.2);
}

.message-meta {
  margin-top: 8px;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--primary-gradient);
  border-radius: 50%;
  animation: typing 1.4s infinite;
  box-shadow: 0 0 4px rgba(102, 126, 234, 0.5);
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-10px);
  }
}

.chat-input-area {
  border-top: 1px solid var(--border-color);
  padding: var(--spacing-lg);
  background: linear-gradient(to top, #ffffff, #fafbfc);
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.03);
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.examples-card {
  height: 100%;
  overflow-y: auto;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  background: white;
}

.example-questions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.example-btn {
  width: 100%;
  text-align: left;
  padding: var(--spacing-md);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  transition: all var(--transition-base);
  background: white;
}

.example-btn:hover:not(:disabled) {
  border-color: var(--primary-color);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
  transform: translateX(4px);
  box-shadow: var(--shadow-md);
}

@media (max-width: 1200px) {
  .agent-chat-container {
    grid-template-columns: 1fr;
  }

  .examples-card {
    display: none;
  }
}
</style>
