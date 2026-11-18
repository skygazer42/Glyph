/** JSON 本地持久化；默认对象属于每次调用，不与草稿共享。 */
import { ref, watch } from 'vue'

const sessionLists = new Map()
const SESSION_STORAGE_KEY = 'chat_sessions'

export function conversationStorage(scope = 'public') {
  return globalThis[scope === 'public' ? 'localStorage' : 'sessionStorage']
}

export function conversationStorageKey(scope, key) {
  return scope === 'public' ? key : `staff_chat_${encodeURIComponent(scope.slice(6)).replaceAll('_', '%5F')}_${key}`
}

/** 退出时只清理当前工作人员在本标签页的缓存。存储受限时由界面提示。 */
export function clearStaffConversationCache(username) {
  const scope = `staff:${username}`
  const storage = conversationStorage(scope)
  const prefix = conversationStorageKey(scope, '')
  const keys = []
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index)
    if (key?.startsWith(prefix)) keys.push(key)
  }
  for (const key of keys) storage.removeItem(key)
  const sessions = sessionLists.get(scope)
  if (sessions) sessions.value = []
}

function cloneDefaultValue(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value))
}

function readStorage(key, defaultValue, validate, scope) {
  try {
    const stored = conversationStorage(scope).getItem(key)
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

export function useLocalStorage(key, defaultValue = null, validate = () => true, scope = 'public') {
  const data = ref(readStorage(key, defaultValue, validate, scope))
  let clearing = false

  const stop = watch(data, (newValue) => {
    if (clearing) {
      return
    }
    try {
      if (newValue === null || newValue === undefined) {
        conversationStorage(scope).removeItem(key)
      } else {
        conversationStorage(scope).setItem(key, JSON.stringify(newValue))
      }
    } catch (error) {
      console.error(`Failed to save ${key} to localStorage:`, error)
    }
  }, { deep: true, flush: 'sync' })

  const clear = () => {
    const value = cloneDefaultValue(defaultValue)
    conversationStorage(scope).removeItem(key)
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
export function useChatHistory(sessionId, scope = 'public') {
  const STORAGE_KEY = conversationStorageKey(scope, `chat_history_${sessionId}`)
  const MAX_MESSAGES = 500
  const { data: messages, clear, stop } = useLocalStorage(STORAGE_KEY, [], value =>
    Array.isArray(value) && value.every(message =>
      message !== null &&
      typeof message === 'object' &&
      typeof message.role === 'string' &&
      typeof message.content === 'string'
    ), scope
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
    (session.serverId === undefined || session.serverId === null || typeof session.serverId === 'string') &&
    (
      session.lastMessage === null ||
      session.lastMessage === undefined ||
      typeof session.lastMessage === 'string'
    )
  )
}

/** 所有会话入口共享列表；写入失败时保留原状态并向调用方抛错。 */
export function useSessionList(scope = 'public') {
  const storageKey = conversationStorageKey(scope, SESSION_STORAGE_KEY)
  if (!sessionLists.has(scope)) {
    sessionLists.set(scope, ref(readStorage(storageKey, [], isSessionList, scope)))
  }
  const sessions = sessionLists.get(scope)

  const persistSessions = (nextSessions) => {
    conversationStorage(scope).setItem(storageKey, JSON.stringify(nextSessions))
    sessions.value = nextSessions
  }

  const clearHistories = (sessionIds) => {
    const failedHistoryIds = []
    for (const sessionId of sessionIds) {
      try {
        conversationStorage(scope).removeItem(conversationStorageKey(scope, `chat_history_${sessionId}`))
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
    conversationStorage(scope).removeItem(storageKey)
    sessions.value = []
    return clearHistories(sessionIds)
  }

  return { sessions, upsertSession, removeSession, updateSessionActivity, clearAll }
}
