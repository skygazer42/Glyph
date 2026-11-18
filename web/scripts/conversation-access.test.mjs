import assert from 'node:assert/strict'
import {
  clearStaffConversationCache,
  conversationStorageKey,
  useChatHistory,
  useSessionList
} from '../src/composables/useLocalStorage.js'

class MemoryStorage {
  #values = new Map()

  get length() { return this.#values.size }
  key(index) { return [...this.#values.keys()][index] ?? null }
  getItem(key) { return this.#values.get(String(key)) ?? null }
  setItem(key, value) { this.#values.set(String(key), String(value)) }
  removeItem(key) { this.#values.delete(String(key)) }
  clear() { this.#values.clear() }
}

const snapshot = storage => Array.from({ length: storage.length }, (_, index) => {
  const key = storage.key(index)
  return [key, storage.getItem(key)]
}).sort(([left], [right]) => left.localeCompare(right))

const originalStorage = ['localStorage', 'sessionStorage'].map(name => [
  name, Object.getOwnPropertyDescriptor(globalThis, name)
])
const historyHandles = []
const local = new MemoryStorage()
const tab = new MemoryStorage()

try {
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: local })
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: tab })

  const sessionId = 'shared-session-id'
  const publicSession = { id: sessionId, title: '公众咨询', lastMessage: '', serverId: 'public-server' }
  const publicMessages = [{ role: 'user', content: '公众记录' }]
  local.setItem('chat_sessions', JSON.stringify([publicSession]))
  local.setItem(`chat_history_${sessionId}`, JSON.stringify(publicMessages))
  local.setItem('agent_chat_user_id', 'legacy-public-value')
  local.setItem('gov-policy-theme', 'dark')

  const publicList = useSessionList()
  const publicHistory = useChatHistory(sessionId)
  historyHandles.push(publicHistory)
  assert.deepEqual(publicList.sessions.value, [publicSession])
  assert.deepEqual(publicHistory.messages.value, publicMessages)
  assert.strictEqual(useSessionList('public').sessions, publicList.sessions)
  publicHistory.addMessage({ role: 'assistant', content: '公众答复' })
  assert.equal(JSON.parse(local.getItem(`chat_history_${sessionId}`)).at(-1).content, '公众答复')
  const publicBeforeStaffAccess = snapshot(local)

  const username = 'alice'
  const otherUsername = 'alice_admin'
  const scope = `staff:${username}`
  const otherScope = `staff:${otherUsername}`
  const staffList = useSessionList(scope)
  const otherList = useSessionList(otherScope)
  const staffHistory = useChatHistory(sessionId, scope)
  const otherHistory = useChatHistory(sessionId, otherScope)
  historyHandles.push(staffHistory, otherHistory)

  assert.deepEqual(staffList.sessions.value, [])
  assert.deepEqual(otherList.sessions.value, [])
  assert.deepEqual(staffHistory.messages.value, [])
  assert.deepEqual(otherHistory.messages.value, [])
  assert.notStrictEqual(staffList.sessions, publicList.sessions)
  assert.notStrictEqual(staffList.sessions, otherList.sessions)
  assert.strictEqual(useSessionList(scope).sessions, staffList.sessions)

  const staffSession = { id: sessionId, title: '工作人员甲', lastMessage: '', serverId: 'staff-a-server' }
  const otherSession = { id: sessionId, title: '工作人员乙', lastMessage: '', serverId: 'staff-b-server' }
  staffList.upsertSession(staffSession)
  otherList.upsertSession(otherSession)
  staffHistory.addMessage({ role: 'user', content: '工作人员甲记录' })
  otherHistory.addMessage({ role: 'user', content: '工作人员乙记录' })

  const listKey = conversationStorageKey(scope, 'chat_sessions')
  const historyKey = conversationStorageKey(scope, `chat_history_${sessionId}`)
  const userIdKey = conversationStorageKey(scope, 'agent_chat_user_id')
  const orphanHistoryKey = conversationStorageKey(scope, 'chat_history_orphaned')
  const otherKeys = [
    conversationStorageKey(otherScope, 'chat_sessions'),
    conversationStorageKey(otherScope, `chat_history_${sessionId}`),
    conversationStorageKey(otherScope, 'agent_chat_user_id')
  ]
  assert.notEqual(listKey, otherKeys[0])
  assert.equal(tab.getItem(listKey), JSON.stringify([staffSession]))
  assert.equal(tab.getItem(historyKey), JSON.stringify(staffHistory.messages.value))
  assert.equal(local.getItem(listKey), null)
  assert.equal(local.getItem(historyKey), null)
  assert.equal(tab.getItem('chat_sessions'), null)
  assert.equal(tab.getItem(`chat_history_${sessionId}`), null)
  assert.equal(publicHistory.messages.value[0].content, '公众记录')
  assert.equal(staffHistory.messages.value[0].content, '工作人员甲记录')
  assert.equal(otherHistory.messages.value[0].content, '工作人员乙记录')
  assert.deepEqual(snapshot(local), publicBeforeStaffAccess)

  tab.setItem(userIdKey, 'staff-a-user-id')
  tab.setItem(orphanHistoryKey, JSON.stringify([{ role: 'user', content: '未关联记录' }]))
  tab.setItem(otherKeys[2], 'staff-b-user-id')
  tab.setItem('unrelated-tab-preference', 'keep')
  const otherBeforeLogout = otherKeys.map(key => [key, tab.getItem(key)])

  clearStaffConversationCache(username)

  for (const key of [listKey, historyKey, userIdKey, orphanHistoryKey]) {
    assert.equal(tab.getItem(key), null)
  }
  assert.deepEqual(staffList.sessions.value, [])
  assert.deepEqual(useSessionList(scope).sessions.value, [])
  assert.deepEqual(otherList.sessions.value, [otherSession])
  assert.deepEqual(otherHistory.messages.value, [{ role: 'user', content: '工作人员乙记录' }])
  assert.deepEqual(otherKeys.map(key => [key, tab.getItem(key)]), otherBeforeLogout)
  assert.equal(tab.getItem('unrelated-tab-preference'), 'keep')
  assert.deepEqual(publicList.sessions.value, [publicSession])
  assert.deepEqual(snapshot(local), publicBeforeStaffAccess)
} finally {
  for (const history of historyHandles) history.stop()
  for (const [name, descriptor] of originalStorage) {
    if (descriptor) Object.defineProperty(globalThis, name, descriptor)
    else delete globalThis[name]
  }
}
