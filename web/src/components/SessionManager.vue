<template>
  <div class="session-manager">
    <div class="session-header">
      <h3 class="header-title">
        <el-icon><ChatDotRound /></el-icon>
        对话历史
      </h3>
      <el-button
        size="small"
        type="primary"
        :icon="Plus"
        @click="createNewSession"
        class="new-session-btn"
      >
        新对话
      </el-button>
    </div>

    <!-- 搜索框 -->
    <div class="session-search">
      <el-input
        v-model="searchQuery"
        placeholder="搜索对话..."
        :prefix-icon="Search"
        clearable
        size="small"
      />
    </div>

    <!-- 会话列表 -->
    <div class="session-list">
      <el-scrollbar height="100%">
        <div
          v-for="session in filteredSessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === currentSessionId }"
          @click="selectSession(session)"
        >
          <div class="session-content">
            <div class="session-title">
              <el-icon><ChatLineRound /></el-icon>
              <span>{{ session.title }}</span>
            </div>
            <div class="session-meta">
              <span class="session-time">{{ formatTime(session.lastActive) }}</span>
              <span class="session-count">{{ session.messageCount || 0 }} 条消息</span>
            </div>
            <div v-if="session.lastMessage" class="session-preview">
              {{ truncate(session.lastMessage, 40) }}
            </div>
          </div>
          <div class="session-actions" @click.stop>
            <el-dropdown trigger="click" @command="(cmd) => handleAction(cmd, session)">
              <el-button :icon="MoreFilled" size="small" text circle />
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item :icon="Edit" command="rename">
                    重命名
                  </el-dropdown-item>
                  <el-dropdown-item :icon="CopyDocument" command="duplicate">
                    复制
                  </el-dropdown-item>
                  <el-dropdown-item :icon="Delete" command="delete" divided>
                    删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>

        <!-- 空状态 -->
        <el-empty
          v-if="filteredSessions.length === 0"
          description="暂无对话记录"
          :image-size="80"
        >
          <el-button type="primary" :icon="Plus" @click="createNewSession">
            创建新对话
          </el-button>
        </el-empty>
      </el-scrollbar>
    </div>

    <!-- 底部操作 -->
    <div class="session-footer">
      <el-button
        size="small"
        :icon="Delete"
        @click="clearAllSessions"
        :disabled="sessions.length === 0"
      >
        清空所有对话
      </el-button>
    </div>

    <!-- 重命名对话框 -->
    <el-dialog
      v-model="renameDialogVisible"
      title="重命名对话"
      width="400px"
    >
      <el-input
        v-model="newSessionTitle"
        placeholder="请输入对话标题"
        maxlength="50"
        show-word-limit
        @keyup.enter="confirmRename"
      />
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmRename">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ChatDotRound,
  ChatLineRound,
  Plus,
  Search,
  Edit,
  Delete,
  CopyDocument,
  MoreFilled
} from '@element-plus/icons-vue'
import { useSessionList } from '@/composables/useLocalStorage'

// Props & Emits
const props = defineProps({
  currentSessionId: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['session-change', 'session-create', 'session-delete'])

// State
const { sessions, upsertSession, removeSession, clearAll } = useSessionList()
const searchQuery = ref('')
const renameDialogVisible = ref(false)
const newSessionTitle = ref('')
const selectedSession = ref(null)

// Computed
const filteredSessions = computed(() => {
  if (!searchQuery.value) {
    return sortedSessions.value
  }

  const query = searchQuery.value.toLowerCase()
  return sortedSessions.value.filter(session =>
    session.title.toLowerCase().includes(query) ||
    (session.lastMessage && session.lastMessage.toLowerCase().includes(query))
  )
})

const sortedSessions = computed(() => {
  return [...sessions.value].sort((a, b) => {
    return new Date(b.lastActive) - new Date(a.lastActive)
  })
})

// Methods
const createNewSession = () => {
  const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  const newSession = {
    id: sessionId,
    title: `新对话 ${sessions.value.length + 1}`,
    createdAt: new Date().toISOString(),
    lastActive: new Date().toISOString(),
    messageCount: 0,
    lastMessage: ''
  }

  upsertSession(newSession)
  emit('session-create', sessionId)
  ElMessage.success('已创建新对话')
}

const selectSession = (session) => {
  emit('session-change', session.id)
}

const handleAction = async (command, session) => {
  selectedSession.value = session

  switch (command) {
    case 'rename':
      newSessionTitle.value = session.title
      renameDialogVisible.value = true
      break

    case 'duplicate':
      duplicateSession(session)
      break

    case 'delete':
      await deleteSession(session)
      break
  }
}

const confirmRename = () => {
  if (!newSessionTitle.value.trim()) {
    ElMessage.warning('请输入对话标题')
    return
  }

  upsertSession({
    ...selectedSession.value,
    title: newSessionTitle.value.trim()
  })

  ElMessage.success('重命名成功')
  renameDialogVisible.value = false
}

const duplicateSession = (session) => {
  const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  const duplicated = {
    ...session,
    id: newSessionId,
    title: `${session.title} (副本)`,
    createdAt: new Date().toISOString(),
    lastActive: new Date().toISOString()
  }

  upsertSession(duplicated)

  // 复制消息历史
  const originalMessages = localStorage.getItem(`chat_history_${session.id}`)
  if (originalMessages) {
    localStorage.setItem(`chat_history_${newSessionId}`, originalMessages)
  }

  ElMessage.success('已复制对话')
}

const deleteSession = async (session) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除对话 "${session.title}" 吗？此操作不可撤销。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    removeSession(session.id)
    emit('session-delete', session.id)
    ElMessage.success('已删除对话')
  } catch {
    // 用户取消
  }
}

const clearAllSessions = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要清空所有对话吗？此操作不可撤销。`,
      '清空确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    clearAll()
    emit('session-delete', null)
    ElMessage.success('已清空所有对话')
  } catch {
    // 用户取消
  }
}

const formatTime = (isoString) => {
  if (!isoString) return ''

  const date = new Date(isoString)
  const now = new Date()
  const diff = now - date

  // 小于1分钟
  if (diff < 60000) {
    return '刚刚'
  }

  // 小于1小时
  if (diff < 3600000) {
    return `${Math.floor(diff / 60000)} 分钟前`
  }

  // 小于24小时
  if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)} 小时前`
  }

  // 小于7天
  if (diff < 604800000) {
    return `${Math.floor(diff / 86400000)} 天前`
  }

  // 超过7天，显示日期
  return date.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit'
  })
}

const truncate = (text, length) => {
  if (!text) return ''
  return text.length > length ? text.substring(0, length) + '...' : text
}

// 暴露方法给父组件
defineExpose({
  updateSession: (sessionId, updates) => {
    const session = sessions.value.find(s => s.id === sessionId)
    if (session) {
      upsertSession({ ...session, ...updates })
    }
  }
})
</script>

<style scoped>
.session-manager {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.session-header {
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(to bottom, #ffffff, #fafbfc);
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.new-session-btn {
  border-radius: var(--radius-md);
}

.session-search {
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.session-list {
  flex: 1;
  overflow: hidden;
  padding: var(--spacing-sm);
}

.session-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-xs);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
}

.session-item:hover {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
  border-color: rgba(102, 126, 234, 0.2);
}

.session-item.active {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  border-color: var(--primary-color);
  box-shadow: var(--shadow-sm);
}

.session-content {
  flex: 1;
  min-width: 0;
}

.session-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 4px;
  font-size: 14px;
}

.session-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.session-time {
  font-weight: 500;
}

.session-count {
  padding: 2px 6px;
  background: rgba(0, 82, 217, 0.1);
  border-radius: var(--radius-sm);
  color: var(--primary-color);
}

.session-preview {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: 0.7;
}

.session-actions {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.session-item:hover .session-actions {
  opacity: 1;
}

.session-footer {
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--border-color);
  background: linear-gradient(to top, #ffffff, #fafbfc);
}

/* 暗色模式 */
[data-theme="dark"] .session-manager {
  background: var(--bg-secondary);
}

[data-theme="dark"] .session-header,
[data-theme="dark"] .session-footer {
  background: linear-gradient(to bottom, #2d3748, #1a202c);
  border-color: rgba(255, 255, 255, 0.1);
}

[data-theme="dark"] .session-search {
  border-color: rgba(255, 255, 255, 0.1);
}

[data-theme="dark"] .session-item:hover {
  background: rgba(61, 127, 255, 0.1);
  border-color: rgba(61, 127, 255, 0.3);
}

[data-theme="dark"] .session-item.active {
  background: rgba(61, 127, 255, 0.15);
  border-color: var(--primary-color);
}

[data-theme="dark"] .session-count {
  background: rgba(61, 127, 255, 0.2);
  color: var(--primary-light);
}
</style>
