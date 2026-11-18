<template>
<div class="policy-workbench" :class="{ 'is-staff': workspace, 'is-empty': !messages.length, 'evidence-collapsed': !evidenceVisible }">
  <header v-if="!workspace" class="public-consultation-header">
    <div class="public-header-inner">
      <router-link to="/agent" class="public-brand" aria-label="政策咨询服务">
        <PlatformMark class="public-platform-symbol" width="34" height="34" /><div class="public-brand-copy"><strong>政策知识服务平台</strong><span>公众咨询</span></div>
      </router-link>
      <div class="public-header-actions">
        <ConsultationActions :evidence-visible="evidenceVisible" :source-count="activeSources.length" @new="startConsultation" @history="showSessionDrawer = true" @evidence="toggleEvidence" @settings="settingsVisible = true" />
        <router-link :to="auth.hasActiveSession() ? '/workbench' : '/login?redirect=/workbench'" class="public-staff-link">{{ auth.hasActiveSession() ? '进入工作台' : '工作人员登录' }} <el-icon><Right /></el-icon></router-link>
      </div>
    </div>
  </header>
  <div v-if="workspace" class="consultation-titlebar">
      <div>
        <h1>政策咨询</h1>
      </div>
      <ConsultationActions workspace :evidence-visible="evidenceVisible" :source-count="activeSources.length" @new="startConsultation" @history="showSessionDrawer = true" @evidence="toggleEvidence" @settings="settingsVisible = true" />
  </div>
  <main class="conversation-workspace" aria-label="政策咨询">
    <div v-if="isConnected === false" class="consultation-service-note" role="status">
      <el-icon aria-hidden="true"><Warning /></el-icon>
      <span>咨询暂未连接，已有记录可查阅。</span>
      <button type="button" :disabled="checkingConnection" @click="checkConnection"><el-icon :class="{ 'is-loading': checkingConnection }"><Refresh /></el-icon>{{ checkingConnection ? '正在连接' : '重新连接' }}</button>
    </div>
    <section v-if="!messages.length" class="consultation-welcome">
      <div class="welcome-heading"><span class="welcome-symbol" aria-hidden="true"><el-icon><Reading /></el-icon></span><component :is="workspace ? 'h2' : 'h1'">从一个政策问题开始</component></div>
      <p class="welcome-description">请说明政策、地区和时间；测算时补充金额与能效等级。</p>
    </section>
    <div v-show="messages.length" ref="messagesContainer" class="conversation-scroll" role="log" aria-label="咨询记录" :aria-busy="loading">
      <div class="conversation-reading">
        <article v-for="(message, index) in messages" :key="getMessageKey(message)" class="conversation-message" :class="message.role">
          <div v-if="message.role === 'user'" class="user-question">
            <span class="question-label">{{ workspace ? '咨询问题' : '您的提问' }}</span>
            <p>
              {{ message.content }}
            </p>
          </div>
          <template v-else>
            <div class="assistant-heading">
              <span class="assistant-mark"><el-icon><Reading /></el-icon></span>
              <strong>政策答复</strong>
              <span class="answer-number">
                答复 {{ getAnswerNumber(index) }}
              </span>
            </div>
            <SubsidyResultCard
              v-if="getSubsidyResult(message.metadata)"
              :result="getSubsidyResult(message.metadata)"
              :source-count="getReferences(message).length"
              @source="showEvidence(message, $event)"
              @expanded="revealDetails"
            />
            <div v-else class="answer-prose">
              <span v-if="message.metadata?.engine_result?.status === 'EXPIRED'" class="answer-status">
                政策已结束
              </span>
              <div v-if="message.content" class="formatted-answer" v-html="formatMessage(message.content)" />
              <span v-else-if="loading" class="answer-pending">
                <span class="loading-dot" />
                正在查询政策与整理依据…
              </span>
              <span v-else>
                本条答复未返回正文。
              </span>
              <div v-if="getReferences(message).length" class="answer-source-links">
                <span>政策依据</span>
                <div class="inline-source-list">
                  <button v-for="(source, sourceIndex) in getReferences(message)" :key="sourceIndex" type="button" class="inline-policy-source"
                    :aria-label="'查看政策依据 ' + (sourceIndex + 1) + '：' + source.title" @click="showEvidence(message, sourceIndex)">
                    <span class="citation">{{ sourceIndex + 1 }}</span><span>{{ source.title }}</span><el-icon><Right /></el-icon>
                  </button>
                </div>
              </div>
            </div>
            <details v-if="getSubsidyResult(message.metadata)" class="answer-details" @toggle="revealDetails($event.target)">
              <summary>
                查看完整答复
              </summary>
              <div class="formatted-answer" v-html="formatMessage(message.content)" />
            </details>
            <Text2SQLResult v-if="workspace && message.metadata?.route === 'text2sql'" :metadata="message.metadata" />
            <div class="answer-actions">
              <el-tooltip content="复制答复" placement="bottom">
                <button type="button" class="workbench-icon" aria-label="复制答复" :disabled="!message.content" @click="copyMessage(message)">
                  <el-icon>
                    <CopyDocument />
                  </el-icon>
                </button>
              </el-tooltip>
              <span v-if="workspace && getRouteLabel(message)" class="answer-route">
                {{ getRouteLabel(message) }}
              </span>
              <button v-if="getReferences(message).length" type="button" class="answer-evidence-link" @click="showEvidence(message, 0)">
                <el-icon>
                  <Reading />
                </el-icon>
                {{ activeMessage === message && evidenceVisible ? '正在查看本轮依据' : '查看本轮依据' }}
              </button>
              <time v-else class="answer-time">
                {{ message.time || '' }}
              </time>
            </div>
          </template>
        </article>
        <div v-if="loading && (!messages.length || messages[messages.length - 1].role !== 'assistant')" class="answer-pending">
          <span class="loading-dot" />
          正在查询政策与整理依据…
        </div>
      </div>
    </div>
    <div class="composer-area">
      <div class="composer-reading">

        <div class="consultation-composer">
          <div v-if="currentConditions.length" class="composer-context">
            <span>
              本轮条件
            </span>
            <span v-for="condition in currentConditions.slice(0, 3)" :key="condition.name" class="context-chip">
              {{ condition.label }} · {{ condition.value }}
            </span>
          </div>
          <el-input
            ref="composerRef"
            v-model="inputMessage"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 5 }"
            resize="none"
            maxlength="10000"
            aria-label="政策咨询问题"
            placeholder="输入政策问题，或补充地区、购买金额、能效等级…"
            @keydown="handleComposerKeydown"
          />
          <div v-if="hasAttachments" class="composer-attachments">
            <el-tag
              v-for="file in attachments"
              :key="file.uid || file.path || file.name"
              size="small"
              effect="plain"
              :closable="!loading"
              @close="attachmentUploaderRef?.removeFile(file)"
            >
              {{ file.name }}
            </el-tag>
            <button type="button" :disabled="loading" @click="resetAttachments">
              清空附件
            </button>
          </div>
          <div class="composer-toolbar">
            <div class="composer-tools">
              <FileUploader
                ref="attachmentUploaderRef"
                variant="quiet"
                :upload-url="workspace ? '/api/uploads/staff' : '/api/uploads'"
                :headers="workspace ? auth.staffHeaders() : {}"
                :drag="false"
                :multiple="true"
                :limit="5"
                :accept="attachmentAccepts"
                :max-size="10 * 1024 * 1024"
                :show-file-list="false"
                :disabled="loading"
                button-text="附件"
                @change="handleAttachmentChange"
                @error="handleAttachmentError"
              />
              <div class="composer-shortcuts">
                <button type="button" :disabled="loading" @click="openMeasurement"><el-icon><Plus /></el-icon>补贴测算</button>
                <button type="button" :disabled="loading" aria-label="查询条件与材料" @click="setFollowup('请列出这项政策的适用条件和所需材料。')"><el-icon><Plus /></el-icon>条件与材料</button>
              </div>
              <span class="keyboard-hint">
                <kbd>
                  Enter
                </kbd>
                发送 ·
                <kbd>
                  Shift+Enter
                </kbd>
                换行
              </span>
            </div>
            <button v-if="loading" type="button" class="send-question" @click="cancelPendingMessage">
              <el-icon>
                <VideoPause />
              </el-icon>
              停止生成
            </button>
            <button v-else type="button" class="send-question" :disabled="!inputMessage.trim()" @click="sendMessage">
              发送
              <el-icon>
                <Right />
              </el-icon>
            </button>
          </div>
        </div>
        <section v-if="!messages.length" class="consultation-starters" aria-label="常见政策问题">
          <p class="suggestion-heading">选择常见问题，补充后发送</p>
          <div class="consultation-suggestions">
            <button v-for="question in exampleQuestions" :key="question.title" type="button" :disabled="loading" @click="askExample(question.prompt)"><el-icon><Reading /></el-icon><span><strong>{{ question.title }}</strong><span>{{ question.prompt }}</span></span><el-icon><Right /></el-icon></button>
            <button type="button" :disabled="loading" @click="openMeasurement"><el-icon><Plus /></el-icon><span><strong>补贴测算</strong><span>填写金额与能效等级</span></span><el-icon><Right /></el-icon></button>
          </div>
        </section>
        <p class="consultation-disclaimer">
          智能答复与测算结果仅供参考，具体办理请以政策原文及主管部门要求为准。
        </p>
      </div>
    </div>
  </main>
  <PolicyEvidence
    v-if="evidenceVisible && !isCompact"
    :message="activeMessage"
    :source-index="activeSourceIndex"
    :reveal-token="evidenceRevealToken"
    @close="closeEvidence"
  />
  <el-drawer
    v-if="isCompact"
    v-model="evidenceVisible"
    title="政策依据"
    :with-header="false"
    size="min(356px, 100vw)"
    class="glyph-dialog evidence-drawer"
    @update:model-value="value => { if (!value) closeEvidence() }"
  >
    <PolicyEvidence
      :message="activeMessage"
      :source-index="activeSourceIndex"
      :reveal-token="evidenceRevealToken"
      @close="closeEvidence"
    />
  </el-drawer>
  <el-drawer v-model="showSessionDrawer" title="会话管理" direction="ltr" size="min(380px, 100vw)" class="glyph-dialog">
    <SessionManager
      ref="sessionManagerRef"
      :current-session-id="sessionId"
      :scope="conversationScope"
      @session-change="handleSessionChange"
      @session-create="handleSessionCreate"
      @session-delete="handleSessionDelete"
    />
  </el-drawer>
  <el-drawer v-model="settingsVisible" title="咨询设置" size="min(380px, 100vw)" class="glyph-dialog">
    <el-form label-position="top" class="consultation-settings">
      <template v-if="workspace">
      <el-form-item label="用户 ID">
        <el-select v-model="userId" :disabled="loading" filterable allow-create default-first-option clearable placeholder="可选，用于关联咨询身份">
          <el-option v-for="id in presetUserIds" :key="id" :label="id" :value="id" />
        </el-select>
      </el-form-item>
      <el-form-item label="数据库连接">
        <el-select v-model="selectedConnectionId" :disabled="loading || !dbConnections.length" clearable placeholder="选择数据库连接">
          <el-option v-for="connection in dbConnections" :key="connection.id" :label="connection.name" :value="connection.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="数据库查询模式">
        <el-switch v-model="text2sqlMode" :disabled="loading || !dbConnections.length" />
        <p>
          将问题转换为 SQL，查询所选数据库。
        </p>
      </el-form-item>
      </template>
      <el-form-item label="逐步显示答复">
        <el-switch v-model="useStreaming" :disabled="loading" />
        <p>
          关闭后，完整答复将一次性显示。
        </p>
      </el-form-item>
      <el-form-item label="界面主题">
        <button type="button" class="settings-theme" @click="toggleTheme">
          {{ isDark ? '切换到亮色模式' : '切换到暗色模式' }}
        </button>
      </el-form-item>
      <el-divider />
      <el-popconfirm title="清空当前会话的全部消息？" confirm-button-text="清空" cancel-button-text="保留" @confirm="clearChat">
        <template #reference>
          <el-button :icon="Delete" :disabled="loading || !messages.length" plain>
            清空当前对话
          </el-button>
        </template>
      </el-popconfirm>
      <p class="settings-storage-note">
        清空仅影响当前会话，其他咨询记录会保留。
      </p>
    </el-form>
  </el-drawer>
  <el-dialog v-model="measurementVisible" title="补贴测算" width="480px" class="glyph-dialog" :close-on-click-modal="false">
    <p class="measurement-intro">
      补充具体条件，由政策助手查询适用规则并测算。
    </p>
    <el-form label-position="top" @submit.prevent="submitMeasurement">
      <div class="measurement-grid">
        <el-form-item label="地区">
          <el-input v-model="measurementForm.region" placeholder="例如：山东省济南市" maxlength="60" />
        </el-form-item>
        <el-form-item label="政策年度">
          <el-input-number v-model="measurementForm.year" :min="2000" :max="2100" :controls="false" />
        </el-form-item>
      </div>
      <el-form-item label="家电品类">
        <el-input v-model="measurementForm.category" placeholder="例如：冰箱、空调" maxlength="40" />
      </el-form-item>
      <div class="measurement-grid">
        <el-form-item label="购买金额（元）">
          <el-input-number v-model="measurementForm.price" :min="0" :max="100000000" :precision="2" :controls="false" placeholder="请输入金额" />
        </el-form-item>
        <el-form-item label="能效等级">
          <el-select v-model="measurementForm.energyLevel">
            <el-option label="一级能效" :value="1" />
            <el-option label="二级能效" :value="2" />
            <el-option label="不确定 / 无标识" :value="0" />
          </el-select>
        </el-form-item>
      </div>
      <p class="measurement-note">
        历史年度将按问题中的时间查询；是否仍可申领需以政策有效期为准。
      </p>
      <div class="measurement-actions">
        <el-button @click="measurementVisible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          native-type="submit"
          :disabled="loading || !measurementForm.region.trim() || !measurementForm.category.trim() || !Number.isFinite(measurementForm.price) || !Number.isFinite(measurementForm.year)"
        >
          查询并测算
        </el-button>
      </div>
    </el-form>
  </el-dialog>
  <el-dialog v-model="helpVisible" title="如何使用政策工作台" width="480px" class="glyph-dialog">
    <div class="workbench-help">
      <p>
        直接描述问题，并尽量提供地区、政策年度和个人或企业条件。
      </p>
      <p>
        需要测算家电补贴时，可点击「补贴测算」填写金额与能效等级。
      </p>
      <p>
        答复中的引用编号会打开右侧政策依据；会话管理可重命名、复制或删除历史咨询。
      </p>
      <p>
        支持图片、PDF 和 Office 附件，每个文件不超过 10 MB，单次最多 5 个。
      </p>
      <p>
        Enter 发送，Shift+Enter 换行。生成过程中可停止，发送失败会保留输入内容。
      </p>
    </div>
  </el-dialog>
</div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { agentApi, dbApi } from '@/api'
import { ElMessage } from 'element-plus'
import { Delete, CopyDocument, Reading, Right, Plus, Refresh, VideoPause, Warning } from '@element-plus/icons-vue'
import SessionManager from '@/components/SessionManager.vue'
import FileUploader from '@/components/FileUploader.vue'
import Text2SQLResult from '@/components/Text2SQLResult.vue'
import { useChatHistory, useSessionList, conversationStorage, conversationStorageKey } from '@/composables/useLocalStorage'
import { useAuthStore } from '@/stores/auth'
import { redirectStaffToLogin } from '@/api/request'
import { useTheme } from '@/composables/useTheme'
import PlatformMark from '@/components/workbench/PlatformMark.vue'
import ConsultationActions from '@/components/workbench/ConsultationActions.vue'
import { shouldOpenEvidence } from '@/utils/consultationEvidence'
import PolicyEvidence from '@/components/workbench/PolicyEvidence.vue'
import SubsidyResultCard from '@/components/workbench/SubsidyResultCard.vue'
import { getSubsidyResult, getPolicySources, getPolicyConditions } from '@/utils/policyPresentation'

const props = defineProps({ workspace: { type: Boolean, default: false } })
const auth = useAuthStore()
const conversationScope = props.workspace ? `staff:${auth.staffUser.username}` : 'public'

// 状态
const inputMessage = ref('')
const loading = ref(false)
const isConnected = ref(null)
const checkingConnection = ref(false)
const messagesContainer = ref(null)
const useStreaming = ref(true) // 是否使用流式响应
const sessionId = ref(null) // 会话ID
const serverSessionId = ref(null)
const showSessionDrawer = ref(false) // 显示会话侧边栏
const sessionManagerRef = ref(null) // 会话管理器引用
const attachmentUploaderRef = ref(null)

const USER_ID_STORAGE_KEY = conversationStorageKey(conversationScope, 'agent_chat_user_id')
const presetUserIds = ['12345', '67890', '88888']
const readStoredUserId = () => {
  try {
    return props.workspace ? conversationStorage(conversationScope).getItem(USER_ID_STORAGE_KEY) ?? '' : ''
  } catch {
    console.warn('用户ID无法读取，当前可继续临时对话')
    return ''
  }
}
const userId = ref(readStoredUserId())
const attachments = ref([])
const attachmentAccepts = '.png,.jpg,.jpeg,.webp,.bmp,.pdf,.doc,.docx,.xls,.xlsx'
const hasAttachments = computed(() => attachments.value.length > 0)

// 数据库连接 & Text2SQL 模式
const dbConnections = ref([])
const selectedConnectionId = ref(null)
const text2sqlMode = ref(false)

const normalizeUserId = (value) => {
  if (!value) {
    return ''
  }
  return value.trim()
}

const getResolvedUserId = () => {
  if (!props.workspace) return null
  const normalized = normalizeUserId(userId.value)
  return normalized.length > 0 ? normalized : null
}

watch(userId, (value) => {
  if (!props.workspace) return
  const normalized = normalizeUserId(value)
  try {
    if (normalized.length === 0) {
      conversationStorage(conversationScope).removeItem(USER_ID_STORAGE_KEY)
      if (value) {
        userId.value = ''
      }
      return
    }

    if (normalized !== value) {
      userId.value = normalized
      return
    }

    conversationStorage(conversationScope).setItem(USER_ID_STORAGE_KEY, normalized)
  } catch {
    console.warn('用户ID无法保存，当前可继续临时对话')
  }
})

// 加载可用的数据库连接，并优先选择 Policy Demo MySQL
let connectionsRequest = null
onMounted(async () => {
  if (!props.workspace) return
  const request = {}
  connectionsRequest = request
  try {
    const connections = await dbApi.listConnections()
    if (connectionsRequest !== request) {
      return
    }
    dbConnections.value = Array.isArray(connections) ? connections : []
    const policyConnection = dbConnections.value.find(connection => connection.name === 'Policy Demo MySQL')
    if (policyConnection) {
      selectedConnectionId.value = policyConnection.id
    } else if (dbConnections.value.length > 0) {
      selectedConnectionId.value = dbConnections.value[0].id
    }
  } catch (error) {
    if (connectionsRequest === request) {
      console.warn('加载数据库连接失败:', error)
    }
  }
})

const normalizeAttachmentRecords = (files = []) => {
  return files
    .map((item) => {
      const response = item.response || {}
      const mime = response.mime_type || item.raw?.type || ''
      return {
        uid: item.uid,
        name: item.name,
        size: item.size,
        mime_type: mime,
        path: response.path || response.file_path || '',
        url: response.url || '',
        type: mime.toLowerCase().startsWith('image/') ? 'image' : 'file'
      }
    })
    .filter((record) => record.path || record.url)
}

const handleAttachmentChange = (fileItems) => {
  attachments.value = normalizeAttachmentRecords(fileItems)
}

const handleAttachmentError = ({ error }) => {
  if (props.workspace && error.status === 401) redirectStaffToLogin()
}

const buildAttachmentPayload = () => {
  if (attachments.value.length === 0) {
    return []
  }
  return attachments.value.map(({ type, path, url, mime_type, name, size }) => ({
    type,
    path,
    url,
    mime_type,
    metadata: {
      name,
      size
    }
  }))
}

const resetAttachments = () => {
  attachments.value = []
  attachmentUploaderRef.value?.clearAll?.()
}

// 会话管理
const { sessions, upsertSession, updateSessionActivity } = useSessionList(conversationScope)

// 公众记录保存在本机，工作人员记录仅保存在本标签页。
let chatHistory = null
const messages = ref([])
const messageKeys = new WeakMap()
let nextMessageKey = 0
const getMessageKey = (message) => {
  if (!messageKeys.has(message)) {
    messageKeys.set(message, nextMessageKey++)
  }
  return messageKeys.get(message)
}

// 初始化或切换会话时加载历史
let chatRequest = null
let connectionTimer = null
let healthRequest = null

const cancelPendingMessage = () => {
  chatRequest?.controller?.abort()
  chatRequest?.typewriter?.dispose()
  chatRequest = null
  loading.value = false
}

const loadSession = (newSessionId) => {
  cancelPendingMessage()
  resetAttachments()
  evidenceVisible.value = false
  manualEvidenceChoice = null
  chatHistory?.stop?.()
  sessionId.value = newSessionId
  serverSessionId.value = sessions.value.find(session => session.id === newSessionId)?.serverId ?? null

  // 创建或加载会话历史
  chatHistory = useChatHistory(newSessionId, conversationScope)
  messages.value = chatHistory.messages.value

  // 更新会话活跃时间
  try {
    updateSessionActivity(newSessionId)
  } catch {
    ElMessage.error('会话活动记录保存失败')
  }

  // 滚动到底部
  nextTick(() => scrollToBottom())
}

// 示例问题
const exampleQuestions = [
  { title: '查找政策', prompt: '济南有哪些消费补贴政策？' },
  { title: '核对条件', prompt: '家电补贴需要满足哪些条件？' },
  { title: '办理材料', prompt: '新能源车补贴要哪些材料？' }
]

// 格式化消息（支持简单的Markdown）
const formatMessage = (text) => {
  if (!text) {
    return ''
  }

  // 简单的markdown转换
  const formatted = String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
  return formatted.split(/\n\s*\n/).map(paragraph => `<p>${paragraph.replace(/\n/g, '<br>')}</p>`).join('')
}

// 提取引用信息
const getReferences = (message) => getPolicySources(message?.metadata)

// 路由标签
const getRouteLabel = (message) => {
  return message?.metadata?.route_display || ''
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messages.value.length ? messagesContainer.value.scrollHeight : 0
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
    while (resolvers.length > 0) {
      const resolve = resolvers.shift()
      resolve?.()
    }
  }

  const stop = () => {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
    resolveAll()
  }

  const tick = () => {
    if (queue.length === 0) {
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

    if (queue.length === 0) {
      stop()
    }
  }

  const ensureTimer = () => {
    if (timer === null) {
      timer = setInterval(tick, INTERVAL)
    }
  }

  return {
    push(text = '') {
      if (!text) {
        return
      }
      queue += text
      ensureTimer()
    },
    async finish() {
      if (queue.length === 0) {
        return
      }
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
  } catch {
    // 降级方案：使用 document.execCommand
    const textarea = document.createElement('textarea')
    textarea.value = message.content
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()

    try {
      if (!document.execCommand('copy')) {
        throw new Error('复制失败')
      }
      ElMessage.success('已复制到剪贴板')
    } catch {
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
  const session = sessions.value.find(candidateSession => candidateSession.id === sessionId.value)
  if (!session) return
  const firstQuestion = messages.value.find(item => item.role === 'user')?.content
  try {
    upsertSession({
      ...session,
      title: session.title === '新对话' && firstQuestion ? firstQuestion.slice(0, 28) : session.title,
      lastMessage: message.content,
      lastActive: new Date().toISOString(),
      messageCount: messages.value.length
    })
  } catch {
    ElMessage.error('回复已收到，但会话记录保存失败')
  }
}

const acceptServerSession = (id) => {
  if (!id || serverSessionId.value === id) return
  serverSessionId.value = id
  const session = sessions.value.find(item => item.id === sessionId.value)
  if (!session) return
  try {
    upsertSession({ ...session, serverId: id })
  } catch {
    ElMessage.warning('会话凭证未能保存，刷新后可能需要新建咨询')
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
  const targetMessage = messages.value[messages.value.length - 1]
  const request = { controller: new AbortController() }
  chatRequest = request
  const typewriter = createTypewriterRenderer(() => chatRequest === request ? targetMessage : null)
  request.typewriter = typewriter
  let aggregatedContent = ''

  try {
    const url = '/api/agent/chat/stream'
    const resolvedUserId = getResolvedUserId()
    const payload = {
      message: userMessage,
      session_id: serverSessionId.value ?? sessionId.value
    }

    if (resolvedUserId) {
      payload.user_id = resolvedUserId
    }

    const attachmentPayload = buildAttachmentPayload()
    if (attachmentPayload.length > 0) {
      payload.attachments = attachmentPayload
    }

    if (props.workspace && selectedConnectionId.value) {
      payload.connection_id = selectedConnectionId.value
    }
    if (props.workspace && text2sqlMode.value) {
      payload.text2sql_mode = true
    }

    // 使用fetch发送POST请求并接收SSE
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
        ...(props.workspace ? auth.staffHeaders() : { 'X-Client-Audience': 'public' })
      },
      body: JSON.stringify(payload),
      signal: request.controller.signal
    })

    if (chatRequest !== request) {
      return false
    }
    if (!response.ok) {
      if (props.workspace && response.status === 401) {
        await redirectStaffToLogin()
        return false
      }
      const problem = await response.json().catch(() => null)
      throw new Error(typeof problem?.detail === 'string' ? problem.detail : '咨询请求未完成，请稍后重试')
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
        if (line.length === 0) {
          continue
        }
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim() || 'message'
          continue
        }
        if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim())
        }
      }

      if (dataLines.length === 0) {
        return null
      }
      const dataStr = dataLines.join('\n')

      const parsed = JSON.parse(dataStr)

      if (chatRequest !== request) {
        return 'done'
      }
      const { error, session_id, content, metadata, done } = parsed
      if (error || eventType === 'error') {
        throw new Error(error || '流式响应失败')
      }

      acceptServerSession(session_id)

      if (eventType === 'session') {
        return null
      }

      if (content) {
        aggregatedContent += content
        typewriter.push(content)
      }

      if (metadata) {
        targetMessage.metadata = metadata
      }

      if (done || eventType === 'done') {
        return 'done'
      }

      return null
    }

    while (true) {
      const { done, value } = await reader.read()
      if (chatRequest !== request) {
        return false
      }
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })

      const segments = buffer.split(/\r?\n\r?\n/)
      buffer = segments.pop() || ''

      for (const rawEvent of segments) {
        if (rawEvent.trim().length === 0) {
          continue
        }
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

    if (buffer.trim().length > 0) {
      stopReading = processSSEEvent(buffer) === 'done'
    }
    if (!stopReading) {
      throw new Error('流式响应意外中断')
    }

    await typewriter.finish()

    if (chatRequest !== request) {
      return false
    }
    if (aggregatedContent.length > 0 && targetMessage.content.length === 0) {
      targetMessage.content = aggregatedContent
    }

    // 如果没有收到任何内容，显示错误
    if (targetMessage.content.length === 0) {
      throw new Error('没有收到回复')
    }

    // 更新会话元数据
    updateSessionMetadata(targetMessage)
    streamingSucceeded = true
    return true

  } catch (error) {
    if (chatRequest !== request) {
      return false
    }
    console.error('流式发送消息失败:', error)

    typewriter.dispose()

    // 更新错误消息
    targetMessage.content = error.message || '咨询请求未完成，请稍后重试。'
    updateSessionMetadata(targetMessage)
    return false
  } finally {
    typewriter.dispose()
    request.controller.abort()
    if (chatRequest === request && streamingSucceeded) {
      resetAttachments()
    }
    if (chatRequest === request) {
      chatRequest = null
      loading.value = false
      scrollToBottom()
    }
  }
}

// 发送消息
const sendMessage = async () => {
  if (inputMessage.value.trim().length === 0 || loading.value) {
    return
  }

  const userMessage = inputMessage.value.trim()
  // 根据设置选择流式或非流式，失败时保留输入以便重试
  const succeeded = useStreaming.value
    ? await sendMessageStream(userMessage)
    : await sendMessageNonStream(userMessage)
  if (succeeded && inputMessage.value.trim() === userMessage) {
    inputMessage.value = ''
  }
}

// 发送消息（非流式）
const sendMessageNonStream = async (userMessage) => {
  const request = {}
  chatRequest = request
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
      serverSessionId.value ?? sessionId.value,
      props.workspace ? selectedConnectionId.value || null : null,
      resolvedUserId,
      attachmentPayload,
      { staffRequest: props.workspace, text2sql_mode: props.workspace && text2sqlMode.value }
    )

    if (chatRequest !== request) {
      return false
    }
    const { success } = response
    if (success) {
      const { session_id, message, metadata } = response
      // 更新会话ID
      acceptServerSession(session_id)

      // 添加助手回复
      const assistantMsg = {
        role: 'assistant',
        content: message,
        time: new Date().toLocaleTimeString(),
        metadata
      }
      addMessageToHistory(assistantMsg)
      updateSessionMetadata(assistantMsg)
      resetAttachments()
      return true
    } else {
      throw new Error('获取回复失败')
    }
  } catch (error) {
    if (chatRequest !== request) {
      return false
    }
    console.error('发送消息失败:', error)

    // 添加错误消息
    const errorMsg = {
      role: 'assistant',
      content: '抱歉，我遇到了一些问题，请稍后再试。',
      time: new Date().toLocaleTimeString()
    }
    addMessageToHistory(errorMsg)
    updateSessionMetadata(errorMsg)
    return false
  } finally {
    if (chatRequest === request) {
      chatRequest = null
      loading.value = false
      scrollToBottom()
    }
  }
}

// 清空对话
const clearChat = () => {
  cancelPendingMessage()
  if (chatHistory) {
    try {
      chatHistory.clearMessages()
    } catch {
      ElMessage.error('清空对话失败，记录已保留')
      return
    }
  }
  messages.value = chatHistory ? chatHistory.messages.value : []
  evidenceVisible.value = false
  manualEvidenceChoice = null

  const session = sessions.value.find(item => item.id === sessionId.value)
  if (session) {
    try {
      upsertSession({ ...session, lastMessage: '', messageCount: 0 })
    } catch {
      ElMessage.warning('对话已清空，但会话记录保存失败')
      return
    }
  }

  ElMessage.success('对话已清空')
}

// 点击示例问题
const askExample = (question) => {
  setFollowup(question)
}

// 检查连接状态
const checkConnection = async () => {
  healthRequest?.controller.abort()
  const request = { controller: new AbortController() }
  healthRequest = request
  checkingConnection.value = true
  try {
    const response = await fetch('/api/health', { signal: request.controller.signal })
    if (healthRequest === request) {
      isConnected.value = response.ok
    }
  } catch {
    if (healthRequest === request) {
      isConnected.value = false
    }
  } finally {
    if (healthRequest === request) {
      healthRequest = null
      checkingConnection.value = false
    }
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

const createNewSession = () => {
  const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  // 先切换内存会话并停止旧请求，存储不可写时仍可继续临时对话。
  loadSession(newSessionId)
  try {
    upsertSession({
      id: newSessionId,
      title: '新对话',
      createdAt: new Date().toISOString(),
      lastActive: new Date().toISOString(),
      messageCount: 0,
      lastMessage: ''
    })
  } catch {
    ElMessage.warning('会话记录无法保存，当前可继续临时对话')
  }
}

// 删除会话
const handleSessionDelete = (deletedSessionId) => {
  if (deletedSessionId === sessionId.value || !deletedSessionId) {
    createNewSession()
  }
}


// Workbench presentation reads the existing per-message snapshots.
const { isDark, toggleTheme } = useTheme()
const compactQuery = window.matchMedia('(max-width: 1099px)')
const isCompact = ref(compactQuery.matches)
const updateCompactLayout = (event) => {
  isCompact.value = event.matches
  if (event.matches) evidenceVisible.value = false
}
const evidenceVisible = ref(false)
let manualEvidenceChoice = null
const toggleEvidence = () => {
  evidenceVisible.value = !evidenceVisible.value
  manualEvidenceChoice = evidenceVisible.value
}
const closeEvidence = () => {
  evidenceVisible.value = false
  manualEvidenceChoice = false
}
const settingsVisible = ref(false)
const measurementVisible = ref(false)
const helpVisible = ref(false)
const composerRef = ref(null)
const selectedAnswerKey = ref(null)
const activeSourceIndex = ref(0)
const evidenceRevealToken = ref(0)
const measurementForm = ref({ region: '', year: new Date().getFullYear(), category: '', price: undefined, energyLevel: 1 })
const measurementDrafts = new Map()
const currentSession = computed(() => sessions.value.find(session => session.id === sessionId.value))
const latestAnswer = computed(() => [...messages.value].reverse().find(message => message.role === 'assistant') || null)
const activeMessage = computed(() => messages.value.find(message => message.role === 'assistant' && getMessageKey(message) === selectedAnswerKey.value) || latestAnswer.value)
const activeSources = computed(() => getPolicySources(activeMessage.value?.metadata))
const currentConditions = computed(() => getPolicyConditions(latestAnswer.value?.metadata))
watch([activeSources, currentConditions, loading], () => {
  if (shouldOpenEvidence({ sourceCount: activeSources.value.length, conditionCount: currentConditions.value.length, compact: isCompact.value, loading: loading.value, manualChoice: manualEvidenceChoice })) evidenceVisible.value = true
})
watch(() => messages.value.length, () => { selectedAnswerKey.value = null })

const getAnswerNumber = (index) => messages.value.slice(0, index + 1).filter(message => message.role === 'assistant').length
const showEvidence = (message, sourceIndex) => {
  selectedAnswerKey.value = getMessageKey(message)
  activeSourceIndex.value = sourceIndex
  evidenceRevealToken.value++
  evidenceVisible.value = true
  manualEvidenceChoice = true
}
const revealDetails = (element) => {
  if (!element.open) return
  nextTick(() => {
    const container = messagesContainer.value
    if (!container) return
    const overflow = element.getBoundingClientRect().bottom - container.getBoundingClientRect().bottom + 16
    if (overflow > 0) container.scrollBy({ top: overflow, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
  })
}
const startConsultation = () => {
  createNewSession()
  selectedAnswerKey.value = null
  inputMessage.value = ''
  nextTick(() => composerRef.value?.focus())
}
const setFollowup = (question) => {
  inputMessage.value = inputMessage.value.trim() ? `${inputMessage.value}\n\n${question}` : question
  nextTick(() => composerRef.value?.focus())
}
const handleComposerKeydown = (event) => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault()
    sendMessage()
  }
}
const openMeasurement = () => {
  if (!isCompact.value) {
    evidenceVisible.value = true
    manualEvidenceChoice = true
  }
  const draft = measurementDrafts.get(sessionId.value)
  if (draft) {
    measurementForm.value = draft
  } else {
    const metadata = latestAnswer.value?.metadata
    const inputs = metadata?.inputs
    measurementForm.value = {
      region: typeof metadata?.domain_context?.region === 'string' ? metadata.domain_context.region : '',
      year: new Date().getFullYear(),
      category: typeof inputs?.category === 'string' ? inputs.category : '',
      price: typeof inputs?.price === 'number' ? inputs.price : undefined,
      energyLevel: [1, 2].includes(inputs?.energy_level) ? inputs.energy_level : 0
    }
    measurementDrafts.set(sessionId.value, measurementForm.value)
  }
  measurementVisible.value = true
}
const submitMeasurement = () => {
  const form = measurementForm.value
  if (loading.value || !form.region.trim() || !form.category.trim() || !Number.isFinite(form.price) || !Number.isFinite(form.year)) return
  const energy = form.energyLevel ? `${form.energyLevel}级能效` : '能效等级不确定'
  inputMessage.value = `请查询${form.year}年${form.region.trim()}的家电补贴政策：购买${form.category.trim()}，金额${form.price}元，${energy}。请核对政策有效期、适用条件，并在规则支持时测算补贴金额，给出政策依据。`
  measurementVisible.value = false
  sendMessage()
}

// 初始化
onMounted(() => {
  compactQuery.addEventListener('change', updateCompactLayout)
  checkConnection()
  // 每30秒检查一次连接状态
  connectionTimer = setInterval(checkConnection, 30000)

  // 加载或创建第一个会话
  if (sessions.value.length > 0) {
    // 加载最近的会话
    const latestSession = [...sessions.value].sort((a, b) =>
      new Date(b.lastActive) - new Date(a.lastActive)
    )[0]
    loadSession(latestSession.id)
  } else {
    createNewSession()
  }
})
onBeforeUnmount(() => {
  compactQuery.removeEventListener('change', updateCompactLayout)
  cancelPendingMessage()
  connectionsRequest = null
  healthRequest?.controller.abort()
  healthRequest = null
  clearInterval(connectionTimer)
  chatHistory?.stop?.()
})

watch(() => auth.staffUser, (user) => {
  if (props.workspace && (!user || conversationScope !== `staff:${user.username}`)) {
    cancelPendingMessage()
    chatHistory?.stop?.()
    messages.value = []
    resetAttachments()
  }
}, { flush: 'sync' })
</script>

<style src="@/styles/workbench.css"></style>
