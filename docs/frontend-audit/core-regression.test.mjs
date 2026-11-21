import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'
import test from 'node:test'

const require = createRequire(new URL('../../web/package.json', import.meta.url))
const vue = require('vue')
const root = new URL('../../', import.meta.url)

function storageFixture() {
  const values = new Map()
  return {
    values,
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key)
  }
}

function loadModule(path, names, globals = {}) {
  const source = readFileSync(new URL(path, root), 'utf8')
    .replace(/^import .* from .*\r?\n/gm, '')
    .replace(/^export default .*$/gm, '')
    .replace(/^export /gm, '')
  const context = vm.createContext({ ...vue, console, setTimeout, clearTimeout, ...globals })
  return vm.runInContext(`${source}\n;({ ${names.join(', ')} })`, context, { filename: path })
}

function requestFixture(timers = {}) {
  let requestHandler
  let errorHandler
  const retried = []
  const errors = []
  const instance = config => { retried.push(config); return Promise.resolve({ retried: true }) }
  instance.interceptors = {
    request: { use: handler => { requestHandler = handler } },
    response: { use: (_, handler) => { errorHandler = handler } }
  }
  const exports = loadModule('web/src/api/request.js', ['withRetryConfig'], {
    axios: { create: () => instance, isCancel: error => error.code === 'ERR_CANCELED' },
    ElMessage: { error: message => errors.push(message) },
    setTimeout: callback => { queueMicrotask(callback); return 1 },
    ...timers
  })
  return { ...exports, retried, errors, configure: config => requestHandler(config), reject: error => errorHandler(error) }
}

test('explicit zero retries and delay are preserved', () => {
  const request = requestFixture()
  const config = request.withRetryConfig({}, { retries: 0, retryDelay: 0 })
  assert.equal(config.retryConfig.retries, 0)
  assert.equal(config.retryConfig.retryDelay, 0)
})

test('cancellation neither retries nor reports a network error', async () => {
  const request = requestFixture()
  const error = { code: 'ERR_CANCELED', config: request.configure({ method: 'get' }) }
  await assert.rejects(request.reject(error), reason => reason === error)
  assert.equal(request.retried.length, 0)
  assert.equal(request.errors.length, 0)
})

test('uncertain write requests are not automatically replayed', async () => {
  const request = requestFixture()
  const error = { request: {}, config: request.configure({ method: 'post' }) }
  await assert.rejects(request.reject(error), reason => reason === error)
  assert.equal(request.retried.length, 0)
})

test('read requests still use the existing retry path', async () => {
  const request = requestFixture()
  const result = await request.reject({ request: {}, config: request.configure({ method: 'get' }) })
  assert.equal(result.retried, true)
  assert.equal(request.retried.length, 1)
})

test('aborting retry backoff settles immediately and releases its timer and listener', async () => {
  const pendingTimers = new Map()
  const listeners = new Set()
  const signal = {
    aborted: false,
    addEventListener: (_, listener) => listeners.add(listener),
    removeEventListener: (_, listener) => listeners.delete(listener)
  }
  const request = requestFixture({
    setTimeout: callback => { pendingTimers.set(1, callback); return 1 },
    clearTimeout: id => pendingTimers.delete(id)
  })
  const error = { request: {}, config: request.configure({ method: 'get', signal }) }
  const rejection = request.reject(error)
  assert.equal(pendingTimers.size, 1)
  signal.aborted = true
  for (const listener of listeners) listener()
  assert.equal(pendingTimers.size, 0)
  assert.equal(listeners.size, 0)
  await assert.rejects(rejection, reason => reason === error)
  assert.equal(request.retried.length, 0)
  assert.equal(request.errors.length, 0)
})

test('completed retry backoff removes its abort listener before replay', async () => {
  const pendingTimers = new Map()
  const listeners = new Set()
  const signal = {
    aborted: false,
    addEventListener: (_, listener) => listeners.add(listener),
    removeEventListener: (_, listener) => listeners.delete(listener)
  }
  const request = requestFixture({
    setTimeout: callback => { pendingTimers.set(1, callback); return 1 },
    clearTimeout: id => pendingTimers.delete(id)
  })
  const rejection = request.reject({ request: {}, config: request.configure({ method: 'get', signal }) })
  assert.equal(listeners.size, 1)
  pendingTimers.get(1)()
  assert.equal(pendingTimers.size, 0)
  assert.equal(listeners.size, 0)
  await rejection
  assert.equal(request.retried.length, 1)
})

test('clearing history restores a fresh empty array', async () => {
  const localStorage = storageFixture()
  const { useChatHistory } = loadModule('web/src/composables/useLocalStorage.js', ['useChatHistory'], { localStorage })
  const history = useChatHistory('one')
  history.addMessage({ role: 'user', content: 'hello' })
  await vue.nextTick()
  history.clearMessages()
  await vue.nextTick()
  assert.equal(history.messages.value.length, 0)
  history.stop?.()
})

test('malformed session cache is rejected before collection operations', () => {
  const localStorage = storageFixture()
  localStorage.setItem('chat_sessions', 'null')
  const { useSessionList } = loadModule('web/src/composables/useLocalStorage.js', ['useSessionList'], { localStorage })
  const list = useSessionList()
  assert.doesNotThrow(() => list.upsertSession({ id: 'one', title: 'one' }))
  assert.equal(list.sessions.value.length, 1)
})

test('session consumers share state and failed persistence keeps the previous list', () => {
  const localStorage = storageFixture()
  const { useSessionList } = loadModule('web/src/composables/useLocalStorage.js', ['useSessionList'], { localStorage })
  const first = useSessionList()
  const second = useSessionList()
  first.upsertSession({ id: 'one', title: 'one' })
  assert.equal(second.sessions.value.length, 1)
  localStorage.setItem = () => { throw new Error('quota exceeded') }
  assert.throws(() => first.upsertSession({ id: 'two', title: 'two' }), /quota/)
  assert.equal(first.sessions.value.length, 1)
})

test('failed deletion metadata writes preserve the existing message history', () => {
  const localStorage = storageFixture()
  const { useSessionList } = loadModule('web/src/composables/useLocalStorage.js', ['useSessionList'], { localStorage })
  const list = useSessionList()
  list.upsertSession({ id: 'one', title: 'one' })
  localStorage.setItem('chat_history_one', '[{"role":"user","content":"keep me"}]')
  localStorage.setItem = () => { throw new Error('quota exceeded') }
  assert.throws(() => list.removeSession('one'), /quota/)
  assert.equal(list.sessions.value.length, 1)
  assert.ok(localStorage.getItem('chat_history_one'))
})

test('history cleanup failures follow a confirmed list deletion', () => {
  const localStorage = storageFixture()
  const { useSessionList } = loadModule('web/src/composables/useLocalStorage.js', ['useSessionList'], { localStorage })
  const list = useSessionList()
  list.upsertSession({ id: 'one', title: 'one' })
  localStorage.setItem('chat_history_one', '[]')
  const removeItem = localStorage.removeItem
  localStorage.removeItem = key => {
    if (key.startsWith('chat_history_')) throw new Error('storage denied')
    removeItem(key)
  }
  const result = list.clearAll()
  assert.equal(result.failedHistoryIds[0], 'one')
  assert.equal(list.sessions.value.length, 0)
  assert.equal(localStorage.getItem('chat_sessions'), null)
})

test('theme consumers share state and all media listeners are removed', () => {
  const mounted = []
  const unmounted = []
  const listeners = new Set()
  const localStorage = storageFixture()
  const media = { matches: false, addEventListener: (_, handler) => listeners.add(handler), removeEventListener: (_, handler) => listeners.delete(handler) }
  const document = { documentElement: { setAttribute() {}, classList: { add() {}, remove() {} } } }
  const { useTheme } = loadModule('web/src/composables/useTheme.js', ['useTheme'], {
    localStorage, document, window: { matchMedia: () => media },
    onMounted: callback => mounted.push(callback), onUnmounted: callback => unmounted.push(callback)
  })
  const first = useTheme()
  const second = useTheme()
  mounted.forEach(callback => callback())
  first.toggleTheme()
  assert.equal(second.isDark.value, true)
  unmounted.forEach(callback => callback())
  assert.equal(listeners.size, 0)
})

test('a previous notification timeout cannot dismiss a replacement', () => {
  const timers = new Map()
  const disposal = []
  let nextId = 0
  const { useAppStore } = loadModule('web/src/stores/app.js', ['useAppStore'], {
    defineStore: (_, factory) => factory,
    ElMessage: () => {},
    onScopeDispose: callback => disposal.push(callback),
    setTimeout: callback => { timers.set(++nextId, callback); return nextId },
    clearTimeout: id => timers.delete(id)
  })
  const store = useAppStore()
  store.showNotification('info', 'first')
  store.showNotification('success', 'second')
  assert.equal(timers.size, 1)
  disposal.forEach(callback => callback())
  assert.equal(timers.size, 0)
})

test('store notifications use the installed visible message service', () => {
  const shown = []
  const { useAppStore } = loadModule('web/src/stores/app.js', ['useAppStore'], {
    defineStore: (_, factory) => factory,
    ElMessage: options => shown.push(options),
    onScopeDispose: () => {},
    setTimeout: () => 1,
    clearTimeout: () => {}
  })
  const store = useAppStore()
  store.showNotification('warning', 'review notice')
  assert.equal(shown.length, 1)
  assert.equal(shown[0].message, 'review notice')
  assert.equal(shown[0].type, 'warning')
})
