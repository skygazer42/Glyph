<template>
  <div class="agent-chat-container">
    <!-- Main Content Area -->
    <div class="main-content">
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
              <el-icon><MenuIcon /></el-icon>
              会话管理
            </el-button>
            <div class="connection-status">
              <el-tag :type="isConnected ? 'success' : 'danger'" effect="light">
                {{ isConnected ? '已连接' : '未连接' }}
              </el-tag>
              <el-tag v-if="sessionId" type="info" size="small" effect="light">
                会话: {{ sessionId.substring(0, 8) }}...
              </el-tag>
            </div>
          </div>
          <div class="header-right">
            <el-select
              v-model="userId"
              size="small"
              class="user-id-input"
              placeholder="选择或输入用户ID"
              clearable
              filterable
              allow-create
              default-first-option
              :disabled="loading"
            >
              <el-option
                v-for="id in presetUserIds"
                :key="id"
                :label="`示例ID：${id}`"
                :value="id"
              />
            </el-select>
            <el-select
              v-model="selectedConnectionId"
              size="small"
              class="connection-select"
              placeholder="选择数据库连接"
              clearable
              :disabled="loading || dbConnections.length === 0"
              style="min-width: 180px; margin-right: 8px"
            >
              <el-option
                v-for="conn in dbConnections"
                :key="conn.id"
                :label="conn.name"
                :value="conn.id"
              />
            </el-select>
            <el-switch
              v-model="text2sqlMode"
              active-text="Text2SQL"
              inactive-text="普通问答"
              :disabled="loading || !dbConnections.length"
              style="margin-right: 10px"
            />
            <el-switch
              v-model="useStreaming"
              active-text="流式"
              inactive-text="普通"
              :disabled="loading"
              style="margin-right: 10px"
            />
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
        <div v-if="messages.length === 0" class="empty-state">
          <div class="empty-icon">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <h3>开始您的政策咨询</h3>
          <p>向AI助手提问任何政策相关问题，获取专业的解答和建议</p>
          <div class="quick-questions">
            <el-button
              v-for="(question, index) in exampleQuestions.slice(0, 3)"
              :key="index"
              class="quick-question-btn"
              @click="askExample(question)"
              :disabled="loading"
              size="small"
              plain
            >
              {{ question }}
            </el-button>
          </div>
        </div>

        <div
          v-for="(message, index) in messages"
          :key="index"
          class="message-wrapper"
          :class="message.role"
        >
          <div class="message-avatar">
            <el-avatar
              :icon="message.role === 'user' ? User : Service"
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
            <div
              v-if="getReferences(message).length"
              class="ref-block"
            >
              <div class="ref-title">引用</div>
              <ul class="ref-list">
                <li
                  v-for="(ref, idx) in getReferences(message)"
                  :key="idx"
                  class="ref-item"
                  :title="ref.path || ref.origin || ref.title"
                >
                  <span class="ref-label">{{ ref.title || '引用' }}</span>
                  <span class="ref-path" v-if="ref.path">{{ ref.path }}</span>
                  <span class="ref-origin" v-else-if="ref.origin">{{ ref.origin }}</span>
                </li>
              </ul>
            </div>
            <div v-if="getRouteLabel(message)" class="message-meta route-info">
              <el-tag size="small" type="info">
                路由：{{ getRouteLabel(message) }}
              </el-tag>
            </div>
            <Text2SQLResult
              v-if="message.role === 'assistant' && message.metadata && message.metadata.route === 'text2sql'"
              :metadata="message.metadata"
            />
          </div>
        </div>

        <!-- 加载动画 -->
        <div v-if="loading" class="message-wrapper assistant">
          <div class="message-avatar">
            <el-avatar :icon="Service" style="background-color: #67c23a" />
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
          :rows="2"
          placeholder="输入你的问题..."
          @keydown.ctrl.enter="sendMessage"
          :disabled="loading"
          resize="none"
          class="chat-input"
        />

        <div class="attachment-toolbar">
          <FileUploader
            ref="attachmentUploaderRef"
            :upload-url="'/api/uploads'"
            :multiple="true"
            :limit="5"
            :drag="false"
            :accept="attachmentAccepts"
            :button-text="hasAttachments ? '继续添加附件' : '上传附件'"
            :tip-text="'支持图片、PDF、Office 文档，单个不超过10MB'"
            :max-size="10 * 1024 * 1024"
            :show-file-list="true"
            @change="handleAttachmentChange"
          />
          <div class="attachment-info" v-if="hasAttachments">
            <el-tag size="small" type="info">
              已选择 {{ attachments.length }} 个附件
            </el-tag>
          </div>
        </div>

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
    </div> <!-- Close main-content -->
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { agentApi, dbApi } from '@/api'
import { ElMessage } from 'element-plus'
import {
  ChatDotRound,
  Delete,
  User,
  Service,
  Promotion,
  QuestionFilled,
  CopyDocument,
  Menu as MenuIcon
} from '@element-plus/icons-vue'
import SessionManager from '@/components/SessionManager.vue'
import FileUploader from '@/components/FileUploader.vue'
import Text2SQLResult from '@/components/Text2SQLResult.vue'
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
const attachmentUploaderRef = ref(null)

const USER_ID_STORAGE_KEY = 'agent_chat_user_id'
const presetUserIds = ['12345', '67890', '88888']
const userId = ref(localStorage.getItem(USER_ID_STORAGE_KEY) || '')
const attachments = ref([])
const attachmentAccepts = '.png,.jpg,.jpeg,.webp,.bmp,.pdf,.doc,.docx,.xls,.xlsx'
const hasAttachments = computed(() => attachments.value.length > 0)

// 数据库连接 & Text2SQL 模式
const dbConnections = ref([])
const selectedConnectionId = ref(null)
const text2sqlMode = ref(false)

const normalizeUserId = (value) => {
  if (!value) return ''
  return value.trim()
}

const getResolvedUserId = () => {
  const normalized = normalizeUserId(userId.value)
  return normalized || null
}

watch(userId, (value) => {
  const normalized = normalizeUserId(value)
  if (!normalized) {
    localStorage.removeItem(USER_ID_STORAGE_KEY)
    if (value) {
      userId.value = ''
    }
    return
  }

  if (normalized !== value) {
    userId.value = normalized
    return
  }

  localStorage.setItem(USER_ID_STORAGE_KEY, normalized)
})

// 加载可用的数据库连接，并优先选择 Policy Demo MySQL
onMounted(async () => {
  try {
    const connections = await dbApi.listConnections()
    dbConnections.value = Array.isArray(connections) ? connections : []
    const policyConn = dbConnections.value.find(c => c.name === 'Policy Demo MySQL')
    if (policyConn) {
      selectedConnectionId.value = policyConn.id
    } else if (dbConnections.value.length > 0) {
      selectedConnectionId.value = dbConnections.value[0].id
    }
  } catch (e) {
    console.warn('加载数据库连接失败:', e)
  }
})

const normalizeAttachmentRecords = (files = []) => {
  return files
    .map((item) => {
      const resp = item.response || {}
      const mime = resp.mime_type || item.raw?.type || ''
      return {
        uid: item.uid,
        name: item.name,
        size: item.size,
        mime_type: mime,
        path: resp.path || resp.file_path || '',
        url: resp.url || '',
        type: mime.toLowerCase().startsWith('image/') ? 'image' : 'file'
      }
    })
    .filter((record) => record.path || record.url)
}

const handleAttachmentChange = (fileItems) => {
  attachments.value = normalizeAttachmentRecords(fileItems)
}

const buildAttachmentPayload = () => {
  if (!attachments.value.length) {
    return []
  }
  return attachments.value.map((record) => ({
    type: record.type,
    path: record.path,
    url: record.url,
    mime_type: record.mime_type,
    metadata: {
      name: record.name,
      size: record.size
    }
  }))
}

const resetAttachments = () => {
  attachments.value = []
  attachmentUploaderRef.value?.clearAll?.()
}

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

// 提取引用信息
const getReferences = (message) => {
  const refs = message?.metadata?.sources
  if (!Array.isArray(refs)) return []
  return refs
    .map((ref) => ({
      title: ref.title || '',
      path: ref.path || '',
      origin: ref.origin || ''
    }))
    .filter((ref) => ref.title || ref.path || ref.origin)
}

// 路由标签
const getRouteLabel = (message) => {
  const meta = message?.metadata || {}
  if (meta.route_display) return meta.route_display
  if (meta.route) return meta.route
  return ''
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 轻量型吐字渲染器，提升“流式”观感
const createTypewriterRenderer = (getTarget) => {
  const STEP = 6
  const INTERVAL = 18
  let queue = ''
  let timer = null
  const resolvers = []

  const resolveAll = () => {
    while (resolvers.length) {
      const resolve = resolvers.shift()
      resolve?.()
    }
  }

  const stop = () => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
    resolveAll()
  }

  const tick = () => {
    if (!queue) {
      stop()
      return
    }

    const target = getTarget()
    if (!target) {
      queue = ''
      stop()
      return
    }

    const chunk = queue.slice(0, STEP)
    queue = queue.slice(STEP)
    target.content += chunk
    scrollToBottom()

    if (!queue) {
      stop()
    }
  }

  const ensureTimer = () => {
    if (!timer) {
      timer = setInterval(tick, INTERVAL)
    }
  }

  return {
    push(text = '') {
      if (!text) return
      queue += text
      ensureTimer()
    },
    async finish() {
      if (!queue) return
      return new Promise((resolve) => {
        resolvers.push(resolve)
        ensureTimer()
      })
    },
    dispose() {
      queue = ''
      stop()
    }
  }
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
}

// 更新会话元数据
const updateSessionMetadata = (message) => {
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
  addMessageToHistory(userMsg)

  // 添加空的助手消息（用于流式更新）
  const assistantMessageIndex = messages.value.length
  const assistantMsg = {
    role: 'assistant',
    content: '',
    time: new Date().toLocaleTimeString(),
    metadata: null
  }
  addMessageToHistory(assistantMsg)

  scrollToBottom()
  loading.value = true

  let streamingSucceeded = false
  const typewriter = createTypewriterRenderer(() => messages.value[assistantMessageIndex])
  let aggregatedContent = ''

  try {
    const url = `/api/agent/chat/stream`
    const resolvedUserId = getResolvedUserId()
    const payload = {
      message: userMessage,
      session_id: sessionId.value
    }

    if (resolvedUserId) {
      payload.user_id = resolvedUserId
    }

    const attachmentPayload = buildAttachmentPayload()
    if (attachmentPayload.length) {
      payload.attachments = attachmentPayload
    }

    if (selectedConnectionId.value) {
      payload.connection_id = selectedConnectionId.value
    }
    if (text2sqlMode.value) {
      payload.text2sql_mode = true
    }

    // 使用fetch发送POST请求并接收SSE
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      },
      body: JSON.stringify(payload)
    })

    if (!response.ok) {
      throw new Error('请求失败')
    }

    if (!response.body) {
      throw new Error('浏览器不支持流式响应')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let stopReading = false

    const processSSEEvent = (rawEvent) => {
      const lines = rawEvent.split(/\r?\n/)
      let eventType = 'message'
      const dataLines = []

      for (const rawLine of lines) {
        const line = rawLine.trim()
        if (!line) continue
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim() || 'message'
          continue
        }
        if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim())
        }
      }

      if (!dataLines.length) return null
      const dataStr = dataLines.join('\n')

      try {
        const parsed = JSON.parse(dataStr)

        if (parsed.error) {
          throw new Error(parsed.error)
        }

        if (parsed.session_id && !sessionId.value) {
          sessionId.value = parsed.session_id
        }

        if (eventType === 'session') {
          return null
        }

        if (parsed.content) {
          aggregatedContent += parsed.content
          typewriter.push(parsed.content)
        }

        if (parsed.metadata) {
          messages.value[assistantMessageIndex].metadata = parsed.metadata
        }

        if (parsed.done || eventType === 'done') {
          return 'done'
        }

        return null
      } catch (e) {
        console.error('解析SSE数据失败:', e, dataStr)
        return null
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      const segments = buffer.split(/\r?\n\r?\n/)
      buffer = segments.pop() || ''

      for (const rawEvent of segments) {
        if (!rawEvent.trim()) continue
        const status = processSSEEvent(rawEvent)
        if (status === 'done') {
          buffer = ''
          stopReading = true
          break
        }
      }

      if (stopReading) {
        break
      }
    }

    if (buffer.trim()) {
      processSSEEvent(buffer)
    }

    await typewriter.finish()

    const targetMessage = messages.value[assistantMessageIndex]
    if (aggregatedContent && !targetMessage.content) {
      targetMessage.content = aggregatedContent
    }

    // 如果没有收到任何内容，显示错误
    if (!targetMessage.content) {
      targetMessage.content = '抱歉，没有收到回复。'
    }

    // 更新会话元数据
    updateSessionMetadata(targetMessage)
    streamingSucceeded = true

  } catch (error) {
    console.error('流式发送消息失败:', error)

    typewriter.dispose()

    // 更新错误消息
    const targetMessage = messages.value[assistantMessageIndex]
    targetMessage.content = '抱歉，我遇到了一些问题，请稍后再试。'
    updateSessionMetadata(targetMessage)
  } finally {
    if (streamingSucceeded) {
      resetAttachments()
    }
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
  addMessageToHistory(userMsg)

  scrollToBottom()
  loading.value = true

  try {
    // 调用API
    const resolvedUserId = getResolvedUserId()
    const attachmentPayload = buildAttachmentPayload()
    const response = await agentApi.chat(
      userMessage,
      sessionId.value,
      selectedConnectionId.value || null,
      resolvedUserId,
      attachmentPayload,
      text2sqlMode.value ? { text2sql_mode: true } : {}
    )

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
      addMessageToHistory(assistantMsg)
      updateSessionMetadata(assistantMsg)
      resetAttachments()
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
    addMessageToHistory(errorMsg)
    updateSessionMetadata(errorMsg)
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
  height: 100vh;
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  animation: fadeIn 0.6s ease;
  display: flex;
  flex-direction: column;
}


/* Main Content Layout */
.main-content {
  display: flex;
  gap: var(--spacing-md);
  flex: 1;
  height: 100%;
}

.chat-card {
  flex: 1;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(20px);
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.3);
  display: flex;
  flex-direction: column;
  height: 100%;
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
  padding: var(--spacing-md) var(--spacing-lg);
  background: linear-gradient(135deg, rgba(0, 82, 217, 0.05) 0%, rgba(200, 35, 44, 0.05) 100%);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.connection-status {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.session-toggle {
  background: var(--primary-gradient);
  color: white;
  border: none;
  border-radius: var(--radius-lg);
  padding: var(--spacing-sm) var(--spacing-md);
  transition: all var(--transition-base);
}

.session-toggle:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 82, 217, 0.3);
}

.user-id-input {
  width: 190px;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg) var(--spacing-lg) var(--spacing-sm) var(--spacing-lg);
  background: linear-gradient(to bottom, #fafbfc 0%, #f5f7fa 100%);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  padding: var(--spacing-2xl);
}

.empty-icon {
  width: 80px;
  height: 80px;
  background: var(--primary-gradient);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 32px;
  margin-bottom: var(--spacing-xl);
  box-shadow: 0 10px 30px rgba(0, 82, 217, 0.3);
}

.empty-state h3 {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-md) 0;
}

.empty-state p {
  font-size: 1rem;
  color: var(--text-secondary);
  margin: 0 0 var(--spacing-xl) 0;
  line-height: 1.6;
  max-width: 500px;
}

.quick-questions {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  max-width: 400px;
}

.quick-question-btn {
  text-align: left;
  border: 1px solid rgba(0, 82, 217, 0.2);
  color: var(--primary-color);
  transition: all var(--transition-base);
}

.quick-question-btn:hover {
  background: linear-gradient(135deg, rgba(0, 82, 217, 0.05) 0%, rgba(200, 35, 44, 0.05) 100%);
  border-color: var(--primary-color);
  transform: translateX(4px);
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
  max-width: 80%;
  background: white;
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg) var(--spacing-xl);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  transition: all var(--transition-base);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.message-content:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-1px);
}

.message-wrapper.user .message-content {
  background: var(--primary-gradient);
  color: white;
  border: none;
  box-shadow: 0 10px 25px rgba(0, 82, 217, 0.3);
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

.ref-block {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed rgba(0, 0, 0, 0.08);
}

.ref-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
  letter-spacing: 0.5px;
}

.ref-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ref-item {
  font-size: 13px;
  color: var(--el-text-color-primary);
  display: flex;
  gap: 8px;
  align-items: center;
}

.ref-label {
  font-weight: 600;
}

.ref-path {
  color: var(--el-text-color-secondary);
  word-break: break-all;
}

.ref-origin {
  color: var(--el-text-color-secondary);
}

.route-info {
  margin-top: 8px;
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
  background: var(--primary-color);
  border-radius: 50%;
  animation: typing 1.4s infinite;
  box-shadow: 0 0 4px rgba(0, 82, 217, 0.5);
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
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  padding: var(--spacing-sm) var(--spacing-lg);
  background: linear-gradient(to top, #ffffff, #fafbfc);
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.05);
}

.attachment-toolbar {
  margin-top: var(--spacing-sm);
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
}

.attachment-info {
  display: flex;
  align-items: center;
  height: 40px;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0;
}

.chat-input :deep(.el-textarea__inner) {
  font-size: 15px;
  line-height: 1.5;
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  border: 2px solid rgba(0, 0, 0, 0.08);
  transition: all var(--transition-base);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  min-height: 48px;
}

.chat-input :deep(.el-textarea__inner):focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(0, 82, 217, 0.1);
  background: white;
}

.examples-card {
  width: 320px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(20px);
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.3);
  height: fit-content;
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
  background: linear-gradient(135deg, rgba(0, 82, 217, 0.05) 0%, rgba(200, 35, 44, 0.05) 100%);
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(0, 82, 217, 0.15);
}

/* Animations */
@keyframes float {
  0%, 100% {
    transform: translateY(0px) rotate(0deg);
  }
  50% {
    transform: translateY(-10px) rotate(3deg);
  }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* Responsive Design */
@media (max-width: 1200px) {
  .main-content {
    padding: 0;
  }

  .examples-card {
    display: none;
  }

  .message-content {
    max-width: 85%;
  }
}

@media (max-width: 768px) {
  .main-content {
    padding: 0;
  }

  .card-header {
    flex-direction: column;
    gap: var(--spacing-md);
    align-items: flex-start;
  }

  .header-right {
    flex-wrap: wrap;
    width: 100%;
  }

  .message-content {
    max-width: 90%;
    padding: var(--spacing-md) var(--spacing-lg);
  }

  .quick-questions {
    max-width: 100%;
  }
}
</style>
