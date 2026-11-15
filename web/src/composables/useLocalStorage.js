/** JSON 本地持久化；默认对象属于每次调用，不与草稿共享。 */
import { ref, watch } from 'vue'

const sessions = ref(null)
const SESSION_STORAGE_KEY = 'chat_sessions'

function cloneDefaultValue(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value))
}

function readStorage(key, defaultValue, validate) {
  try {
    const stored = localStorage.getItem(key)
    if (stored !== null) {
      const value = JSON.parse(stored)
      if (validate(value)) {
        return value
      }
      console.warn(`忽略格式无效的本地缓存: ${key}`)
    }
  } catch (error) {
    console.error(`Failed to load ${key} from localStorage:`, error)
  }
  return cloneDefaultValue(defaultValue)
}

export function useLocalStorage(key, defaultValue = null, validate = () => true) {
  const data = ref(readStorage(key, defaultValue, validate))
  let clearing = false

  const stop = watch(data, (newValue) => {
    if (clearing) {
      return
    }
    try {
      if (newValue === null || newValue === undefined) {
        localStorage.removeItem(key)
      } else {
        localStorage.setItem(key, JSON.stringify(newValue))
      }
    } catch (error) {
      console.error(`Failed to save ${key} to localStorage:`, error)
    }
  }, { deep: true, flush: 'sync' })

  const clear = () => {
    const value = cloneDefaultValue(defaultValue)
    localStorage.removeItem(key)
    clearing = true
    try {
      data.value = value
    } finally {
      clearing = false
    }
  }

  return { data, clear, stop }
}

/** 管理单个聊天会话的消息历史，切换时由调用方 stop。 */
export function useChatHistory(sessionId) {
  const STORAGE_KEY = `chat_history_${sessionId}`
  const MAX_MESSAGES = 500
  const { data: messages, clear, stop } = useLocalStorage(STORAGE_KEY, [], value =>
    Array.isArray(value) && value.every(message =>
      message !== null &&
      typeof message === 'object' &&
      typeof message.role === 'string' &&
      typeof message.content === 'string'
    )
  )

  const addMessage = (message) => {
    messages.value.push(message)
    if (messages.value.length > MAX_MESSAGES) {
      messages.value.splice(0, messages.value.length - MAX_MESSAGES)
    }
  }

  return { messages, addMessage, clearMessages: clear, stop }
}

function isSessionList(value) {
  return Array.isArray(value) && value.every(session =>
    session !== null &&
    typeof session === 'object' &&
    typeof session.id === 'string' &&
    typeof session.title === 'string' &&
    (
      session.lastMessage === null ||
      session.lastMessage === undefined ||
      typeof session.lastMessage === 'string'
    )
  )
}

/** 所有会话入口共享列表；写入失败时保留原状态并向调用方抛错。 */
export function useSessionList() {
  if (sessions.value === null) {
    sessions.value = readStorage(SESSION_STORAGE_KEY, [], isSessionList)
  }

  const persistSessions = (nextSessions) => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(nextSessions))
    sessions.value = nextSessions
  }

  const clearHistories = (sessionIds) => {
    const failedHistoryIds = []
    for (const sessionId of sessionIds) {
      try {
        localStorage.removeItem(`chat_history_${sessionId}`)
      } catch (error) {
        failedHistoryIds.push(sessionId)
        console.warn(`会话已移除，但消息缓存清理失败: ${sessionId}`, error)
      }
    }
    return { failedHistoryIds }
  }

  const upsertSession = (session) => {
    if (!isSessionList([session])) {
      throw new Error('会话数据格式无效')
    }
    const index = sessions.value.findIndex(item => item.id === session.id)
    const nextSessions = [...sessions.value]
    if (index >= 0) {
      nextSessions[index] = { ...nextSessions[index], ...session }
    } else {
      nextSessions.unshift(session)
    }
    persistSessions(nextSessions)
  }

  const removeSession = (sessionId) => {
    persistSessions(sessions.value.filter(session => session.id !== sessionId))
    return clearHistories([sessionId])
  }

  const updateSessionActivity = (sessionId) => {
    const session = sessions.value.find(item => item.id === sessionId)
    if (session) {
      upsertSession({ ...session, lastActive: new Date().toISOString() })
    }
  }

  const clearAll = () => {
    const sessionIds = sessions.value.map(session => session.id)
    localStorage.removeItem(SESSION_STORAGE_KEY)
    sessions.value = []
    return clearHistories(sessionIds)
  }

  return { sessions, upsertSession, removeSession, updateSessionActivity, clearAll }
}
