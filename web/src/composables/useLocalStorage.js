/**
 * LocalStorage 持久化 Composable
 * 自动保存和恢复数据到 localStorage
 */

import { ref, watch } from 'vue'

export function useLocalStorage(key, defaultValue = null) {
  // 从 localStorage 读取初始值
  const loadFromStorage = () => {
    try {
      const stored = localStorage.getItem(key)
      return stored ? JSON.parse(stored) : defaultValue
    } catch (error) {
      console.error(`Failed to load ${key} from localStorage:`, error)
      return defaultValue
    }
  }

  // 创建响应式引用
  const data = ref(loadFromStorage())

  // 监听变化并保存到 localStorage
  watch(
    data,
    (newValue) => {
      try {
        if (newValue === null || newValue === undefined) {
          localStorage.removeItem(key)
        } else {
          localStorage.setItem(key, JSON.stringify(newValue))
        }
      } catch (error) {
        console.error(`Failed to save ${key} to localStorage:`, error)
      }
    },
    { deep: true }
  )

  // 清除数据
  const clear = () => {
    data.value = defaultValue
    localStorage.removeItem(key)
  }

  return { data, clear }
}

/**
 * 会话历史管理 Composable
 * 专门用于管理聊天会话历史
 */
export function useChatHistory(sessionId) {
  const STORAGE_KEY = `chat_history_${sessionId}`
  const MAX_MESSAGES = 500 // 最多保存500条消息

  const { data: messages, clear } = useLocalStorage(STORAGE_KEY, [])

  // 添加消息
  const addMessage = (message) => {
    messages.value.push(message)

    // 限制消息数量，避免 localStorage 溢出
    if (messages.value.length > MAX_MESSAGES) {
      messages.value = messages.value.slice(-MAX_MESSAGES)
    }
  }

  // 清空消息
  const clearMessages = () => {
    clear()
  }

  return {
    messages,
    addMessage,
    clearMessages
  }
}

/**
 * 会话列表管理 Composable
 * 管理所有会话的元数据
 */
export function useSessionList() {
  const STORAGE_KEY = 'chat_sessions'
  const { data: sessions, clear } = useLocalStorage(STORAGE_KEY, [])

  // 添加或更新会话
  const upsertSession = (session) => {
    const index = sessions.value.findIndex(s => s.id === session.id)

    if (index >= 0) {
      sessions.value[index] = { ...sessions.value[index], ...session }
    } else {
      sessions.value.unshift(session)
    }
  }

  // 删除会话
  const removeSession = (sessionId) => {
    sessions.value = sessions.value.filter(s => s.id !== sessionId)
    // 同时删除会话的消息历史
    localStorage.removeItem(`chat_history_${sessionId}`)
  }

  // 更新会话最后活动时间
  const updateSessionActivity = (sessionId) => {
    const session = sessions.value.find(s => s.id === sessionId)
    if (session) {
      session.lastActive = new Date().toISOString()
    }
  }

  // 清空所有会话
  const clearAll = () => {
    // 删除所有会话的消息历史
    sessions.value.forEach(session => {
      localStorage.removeItem(`chat_history_${session.id}`)
    })
    clear()
  }

  return {
    sessions,
    upsertSession,
    removeSession,
    updateSessionActivity,
    clearAll
  }
}
