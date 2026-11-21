import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'
const require = createRequire(new URL('../../web/package.json', import.meta.url))
const { parse, compileScript, compileTemplate } = require('@vue/compiler-sfc')
const root = new URL('../../', import.meta.url)
const hooks = () => ({ mounted: [], unmounted: [] })
function load(name, names, overrides = {}) {
  const lifecycle = hooks()
  const source = fs.readFileSync(new URL(`web/src/views/${name}.vue`, root), 'utf8')
  const { descriptor, errors } = parse(source)
  assert.equal(errors.length, 0)
  compileScript(descriptor, { id: name })
  assert.equal(compileTemplate({ source: descriptor.template.content, filename: name, id: name }).errors.length, 0)
  const context = vm.createContext({ console: { log() {}, error() {} }, AbortController, TextDecoder, setInterval, clearInterval, ref: value => ({ value }), shallowRef: value => ({ value }), computed: getter => ({ get value() { return getter() } }), reactive: value => value, onMounted: fn => lifecycle.mounted.push(fn), onBeforeUnmount: fn => lifecycle.unmounted.push(fn), nextTick: fn => fn?.(), watch() {}, localStorage: { getItem() { return null }, setItem() {}, removeItem() {} }, useAppStore: () => ({ kbState: { searchQuery: '' }, dslState: {} }), useRouter: () => ({}), useSessionList: () => ({ sessions: { value: [] }, upsertSession() {}, updateSessionActivity() {} }), useChatHistory: () => { const messages = { value: [] }; return { messages, addMessage: message => messages.value.push(message), clearMessages: () => { messages.value = [] } } }, ...overrides })
  const script = descriptor.scriptSetup.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*$/gm, '')
  vm.runInContext(`${script}\nthis.result = { ${names.join(', ')} }`, context)
  return { ...context.result, lifecycle }
}
const cases = []
function test(name, run) { cases.push([name, run]) }
test('chat escapes external HTML while retaining simple formatting', () => {
  const { formatMessage } = load('AgentChat', ['formatMessage'])
  assert.equal(formatMessage('<img src=x onerror=alert(1)> **safe**').includes('<img'), false)
  assert.match(formatMessage('**safe**'), /<strong>safe<\/strong>/)
})
test('knowledge highlight treats query as literal text and escapes HTML', () => {
  const store = { kbState: { searchQuery: '[' } }
  const { highlightKeywords } = load('KnowledgeBase', ['highlightKeywords'], { useAppStore: () => store })
  assert.equal(highlightKeywords('<img> ['), '&lt;img&gt; <mark>[</mark>')
})
test('home cancels its outstanding animation on unmount', () => {
  let cancelled = null
  const view = load('HomePage', [], { requestAnimationFrame: () => 42, cancelAnimationFrame: id => { cancelled = id } })
  view.lifecycle.mounted.forEach(fn => fn())
  view.lifecycle.unmounted.forEach(fn => fn())
  assert.equal(cancelled, 42)
})
test('isolated graph node remains visible in its own neighborhood', () => {
  const view = load('KnowledgeGraph', ['getSubGraph', 'fullGraphData'])
  view.fullGraphData.nodes = [{ id: 'alone' }]
  assert.equal(view.getSubGraph('alone').nodes.length, 1)
})
test('chat response cannot write into a different session', async () => {
  let complete
  const view = load('AgentChat', ['loadSession', 'sendMessageNonStream', 'messages', 'loading'], {
    agentApi: { chat: () => new Promise(resolve => { complete = resolve }) }
  })
  view.loadSession('old')
  const sending = view.sendMessageNonStream('question')
  view.loadSession('new')
  complete({ success: true, message: 'old reply' })
  await sending
  assert.equal(view.messages.value.length, 0)
})
test('DSL generation cannot overwrite a changed input draft', async () => {
  let complete
  const store = { dslState: { inputText: 'old', generatedYAML: '' }, showNotification() {} }
  const view = load('DSLGenerator', ['generateDSL'], { useAppStore: () => store, dslApi: { generateFromText: () => new Promise(resolve => { complete = resolve }) } })
  const generation = view.generateDSL()
  store.dslState.inputText = 'new'
  complete({ yaml_content: 'old yaml', dsl_data: { rule_id: 'old', inputs: [] } })
  await generation
  assert.equal(store.dslState.generatedYAML, '')
})
test('SSE error and truncated stream fail without discarding attachments', async () => {
  for (const ending of ['event: error\ndata: {"error":"failed","done":true}\n\n', '']) {
    const data = new TextEncoder().encode('data: {"content":"partial"}\n\n' + ending)
    let read = false
    const view = load('AgentChat', ['loadSession', 'sendMessageStream', 'attachments'], {
      fetch: async () => ({ ok: true, body: { getReader: () => ({ read: async () => read ? { done: true } : (read = true, { done: false, value: data }) }) } })
    })
    view.loadSession('test')
    view.attachments.value = [{ file_id: 'keep' }]
    assert.equal(await view.sendMessageStream('question'), false)
    assert.equal(view.attachments.value.length, 1)
  }
})
test('latest graph load wins and disposal invalidates pending loads', async () => {
  const pending = []
  let renders = 0
  const view = load('KnowledgeGraph', ['loadFromApi', 'fullGraphData', 'chartInstance'], {
    getGraphData: () => new Promise(resolve => pending.push(resolve))
  })
  view.chartInstance.value = { setOption() { renders++ }, dispose() {} }
  const first = view.loadFromApi()
  const second = view.loadFromApi()
  pending[1]({ nodes: [{ id: 'new', label: 'New' }], links: [] })
  await second
  pending[0]({ nodes: [{ id: 'old', label: 'Old' }], links: [] })
  await first
  assert.equal(view.fullGraphData.nodes[0].id, 'new')
  const last = view.loadFromApi()
  view.lifecycle.unmounted.forEach(fn => fn())
  pending[2]({ nodes: [{ id: 'late' }], links: [] })
  await last
  assert.equal(renders, 1)
})
test('failed knowledge document load is not reported as an empty library', async () => {
  const notices = []
  const store = { kbState: { documents: [], searchResults: [] }, showNotification: (...notice) => notices.push(notice) }
  const view = load('KnowledgeBase', ['performSearch'], { useAppStore: () => store, knowledgeApi: { listDocuments: async () => { throw new Error('offline') } } })
  await view.performSearch({ query: 'query' })
  assert.equal(notices.length, 1)
  assert.equal(notices[0][0], 'error')
})
test('all five SFCs compile with existing Vue compiler', () => {
  for (const name of ['AgentChat', 'DSLGenerator', 'HomePage', 'KnowledgeBase', 'KnowledgeGraph']) load(name, [])
})
test('DSL detail and test inputs follow the real rule response contract', async () => {
  const rule = { rule_id: 'r', inputs: [{ name: 'amount' }] }
  const view = load('DSLGenerator', ['viewRule', 'testRule', 'currentRuleDetail', 'testForm', 'showTestDialog'], { dslApi: { getDSL: async () => ({ success: true, rule }) } })
  await view.viewRule(rule)
  assert.deepEqual(JSON.parse(view.currentRuleDetail.value), rule)
  await view.testRule({ rule_id: 'r' })
  assert.equal(view.testForm.value.inputs.amount, '')
  assert.equal(view.showTestDialog.value, true)
})
test('failed chat retains submitted input and local clear failure retains history', async () => {
  const notices = []
  const view = load('AgentChat', ['loadSession', 'sendMessage', 'useStreaming', 'inputMessage', 'clearChat', 'messages'], {
    agentApi: { chat: async () => { throw new Error('offline') } },
    ElMessage: { error: text => notices.push(text) },
    useChatHistory: () => { const messages = { value: [] }; return { messages, addMessage: message => messages.value.push(message), clearMessages: () => { throw new Error('storage denied') } } }
  })
  view.loadSession('test')
  view.useStreaming.value = false
  view.inputMessage.value = 'keep draft'
  await view.sendMessage()
  assert.equal(view.inputMessage.value, 'keep draft')
  const count = view.messages.value.length
  view.clearChat()
  assert.equal(view.messages.value.length, count)
  assert.equal(notices.length, 1)
})
test('installed Element Plus renders RouterLink navigation as one real anchor', async () => {
  const { createSSRApp, h } = require('vue')
  const { createRouter, createMemoryHistory, RouterLink } = require('vue-router')
  const { ElButton } = require('element-plus')
  const { renderToString } = require('@vue/server-renderer')
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/agent', component: { render: () => null } }] })
  await router.push('/agent')
  await router.isReady()
  const app = createSSRApp({ render: () => h(ElButton, { tag: RouterLink, to: '/agent', class: 'hero-btn primary-btn' }, () => '问答') })
  app.use(router)
  const html = await renderToString(app)
  assert.match(html, /<a[^>]*href="\/agent"/)
  assert.match(html, /hero-btn primary-btn/)
  assert.equal(html.includes('<button'), false)
  const home = fs.readFileSync(new URL('web/src/views/HomePage.vue', root), 'utf8')
  for (const route of ['agent', 'dsl', 'knowledge', 'graph']) {
    assert.match(home, new RegExp(`:tag="RouterLink"\\s+to="/${route}"`))
  }
})
test('clearing chat keeps the next send connected to the displayed history', async () => {
  const view = load('AgentChat', ['loadSession', 'clearChat', 'sendMessageNonStream', 'messages'], {
    agentApi: { chat: async () => ({ success: true, message: 'reply' }) }, ElMessage: { success() {} }
  })
  view.loadSession('test')
  view.clearChat()
  await view.sendMessageNonStream('next')
  assert.equal(view.messages.value.length, 2)
  assert.equal(view.messages.value[1].content, 'reply')
})
test('saving generated YAML uses its own rule identity after testing another rule', async () => {
  let saved
  const store = { dslState: { generatedYAML: 'yaml A', generatedRuleId: 'A', generatedInputs: [{ name: 'amount' }] }, showNotification() {} }
  const view = load('DSLGenerator', ['saveDSL', 'testForm', 'testCurrentDSL'], { useAppStore: () => store, dslApi: { saveDSL: async value => { saved = value }, listDSL: async () => ({ rules: [] }) } })
  view.testForm.value.ruleId = 'B'
  await view.saveDSL()
  assert.equal(saved.rule_id, 'A')
  view.testCurrentDSL()
  assert.equal(view.testForm.value.ruleId, 'A')
  assert.equal(view.testForm.value.inputs.amount, '')
})
test('chat first mount keeps an in-memory session when session storage fails', async () => {
  const notices = []
  const view = load('AgentChat', ['sessionId', 'sendMessageNonStream', 'messages'], {
    useSessionList: () => ({ sessions: { value: [] }, upsertSession() { throw new Error('storage denied') }, updateSessionActivity() {} }),
    ElMessage: { warning: text => notices.push(text) },
    fetch: async () => ({ ok: true }), setInterval: () => 0, clearInterval() {},
    agentApi: { chat: async () => ({ success: true, message: 'reply' }) }
  })
  view.lifecycle.mounted.at(-1)()
  assert.ok(view.sessionId.value)
  assert.equal(await view.sendMessageNonStream('question'), true)
  assert.equal(view.messages.value.length, 2)
  assert.equal(notices.length, 1)
  view.lifecycle.unmounted.forEach(fn => fn())
})
test('deleting current session cancels its stream even if replacement storage fails', async () => {
  let aborted = false
  const view = load('AgentChat', ['loadSession', 'handleSessionDelete', 'sessionId', 'sendMessageStream', 'sendMessageNonStream', 'messages'], {
    useSessionList: () => ({ sessions: { value: [] }, upsertSession() { throw new Error('storage denied') }, updateSessionActivity() {} }),
    ElMessage: { warning() {} },
    fetch: (_, options) => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => { aborted = true; reject(new Error('aborted')) })),
    agentApi: { chat: async () => ({ success: true, message: 'new reply' }) }
  })
  view.loadSession('old')
  const streaming = view.sendMessageStream('old question')
  view.handleSessionDelete('old')
  assert.equal(await streaming, false)
  assert.equal(aborted, true)
  assert.notEqual(view.sessionId.value, 'old')
  assert.equal(view.messages.value.length, 0)
  await view.sendMessageNonStream('new question')
  assert.equal(view.messages.value[1].content, 'new reply')
  view.lifecycle.unmounted.forEach(fn => fn())
})
test('generation completion does not replace a separate rule test draft', async () => {
  let complete
  const store = { dslState: { inputText: 'policy', generatedYAML: '', generatedRuleId: '', generatedInputs: [], generating: false }, showNotification() {} }
  const view = load('DSLGenerator', ['generateDSL', 'testForm'], { useAppStore: () => store, dslApi: { generateFromText: () => new Promise(resolve => { complete = resolve }) } })
  const generation = view.generateDSL()
  view.testForm.value.ruleId = 'B'
  view.testForm.value.inputs = { kept: 'draft' }
  complete({ yaml_content: 'yaml A', dsl_data: { rule_id: 'A', inputs: [{ name: 'amount' }] } })
  await generation
  assert.equal(store.dslState.generatedRuleId, 'A')
  assert.equal(view.testForm.value.ruleId, 'B')
  assert.equal(view.testForm.value.inputs.kept, 'draft')
})
test('clearing DSL invalidates pending test results and input-detail loads', async () => {
  let completeTest
  let completeDetail
  const store = { dslState: {}, resetDSLState() {}, showNotification() {} }
  const view = load('DSLGenerator', ['clearInput', 'executeTest', 'testRule', 'testing', 'showTestDialog', 'showResultDialog', 'testForm'], {
    useAppStore: () => store,
    dslApi: { testDSL: () => new Promise(resolve => { completeTest = resolve }), getDSL: () => new Promise(resolve => { completeDetail = resolve }) }
  })
  const testing = view.executeTest()
  view.clearInput()
  completeTest({ result: { value: 'old' } })
  await testing
  assert.equal(view.showResultDialog.value, false)
  assert.equal(view.testing.value, false)
  const detail = view.testRule({ rule_id: 'old' })
  view.clearInput()
  completeDetail({ rule: { inputs: [{ name: 'old' }] } })
  await detail
  assert.equal(view.showTestDialog.value, false)
  assert.equal(view.testForm.value.ruleId, '')
})
test('chat storage denial keeps a usable user ID and watcher', () => {
  let persist
  const view = load('AgentChat', ['userId'], {
    console: { warn() {} },
    watch: (_, callback) => { persist = callback },
    localStorage: { getItem() { throw new Error('denied') }, setItem() { throw new Error('denied') }, removeItem() { throw new Error('denied') } }
  })
  assert.equal(view.userId.value, '')
  assert.doesNotThrow(() => persist('12345'))
  assert.doesNotThrow(() => persist(''))
})
test('chat selects latest session without reordering shared sessions', () => {
  const sessions = { value: [{ id: 'old', lastActive: '2025-01-01' }, { id: 'new', lastActive: '2025-02-01' }] }
  const view = load('AgentChat', ['sessionId'], { useSessionList: () => ({ sessions, updateSessionActivity() {} }), fetch: async () => ({ ok: true }), setInterval: () => 0, clearInterval() {} })
  view.lifecycle.mounted.at(-1)()
  assert.equal(view.sessionId.value, 'new')
  assert.equal(sessions.value[0].id, 'old')
  view.lifecycle.unmounted.forEach(fn => fn())
})
test('chat health and connection results become invalid at unmount', async () => {
  let healthDone
  let connectionsDone
  const view = load('AgentChat', ['checkConnection', 'isConnected', 'dbConnections'], {
    fetch: () => new Promise(resolve => { healthDone = resolve }),
    dbApi: { listConnections: () => new Promise(resolve => { connectionsDone = resolve }) }
  })
  const connections = view.lifecycle.mounted[0]()
  const health = view.checkConnection()
  view.lifecycle.unmounted.forEach(fn => fn())
  healthDone({ ok: false })
  connectionsDone([{ id: 'late' }])
  await Promise.all([health, connections])
  assert.equal(view.isConnected.value, true)
  assert.equal(view.dbConnections.value.length, 0)
})
test('DSL test completion preserves an edited test draft', async () => {
  let complete
  const view = load('DSLGenerator', ['executeTest', 'testForm', 'showTestDialog', 'showResultDialog'], { dslApi: { testDSL: () => new Promise(resolve => { complete = resolve }) } })
  view.testForm.value = { ruleId: 'A', inputs: { amount: 'old' } }
  view.showTestDialog.value = true
  const testing = view.executeTest()
  view.testForm.value.inputs.amount = 'new'
  complete({ result: { status: 'QUALIFIED' } })
  await testing
  assert.equal(view.showTestDialog.value, true)
  assert.equal(view.showResultDialog.value, false)
  assert.equal(view.testForm.value.inputs.amount, 'new')
})
test('filtered rule and document counts match paginated data', () => {
  const dsl = load('DSLGenerator', ['searchQuery', 'matchingRules', 'filteredRules'], { useAppStore: () => ({ dslState: { dslList: [{ rule_id: 'a', title: 'yes' }, { rule_id: 'b', title: 'no' }] } }) })
  dsl.searchQuery.value = 'yes'
  assert.equal(dsl.matchingRules.value.length, 1)
  assert.equal(dsl.filteredRules.value.length, 1)
  const kb = load('KnowledgeBase', ['documentSearch', 'matchingDocuments', 'filteredDocuments'], { useAppStore: () => ({ kbState: { documents: [{ doc_id: 'a', name: 'yes' }, { doc_id: 'b', name: 'no' }] } }) })
  kb.documentSearch.value = 'yes'
  assert.equal(kb.matchingDocuments.value.length, 1)
  assert.equal(kb.filteredDocuments.value.length, 1)
})
test('knowledge processing does not start embedding after unmount', async () => {
  let parsed
  let embedded = 0
  const view = load('KnowledgeBase', ['processUploadedDocument'], { knowledgeApi: { parseDocument: () => new Promise(resolve => { parsed = resolve }), embedDocument: async () => { embedded++ } }, useAppStore: () => ({ showNotification() {} }) })
  const processing = view.processUploadedDocument({ doc_id: 'A' }, 'file')
  view.lifecycle.unmounted.forEach(fn => fn())
  parsed()
  await processing
  assert.equal(embedded, 0)
})
test('chat message keys stay with the same object after history trimming', () => {
  const view = load('AgentChat', ['getMessageKey'])
  const first = {}
  const second = {}
  assert.notEqual(view.getMessageKey(first), view.getMessageKey(second))
  const key = view.getMessageKey(second)
  assert.equal(view.getMessageKey(second), key)
})
test('DSL save and knowledge search completion cannot update a departed or changed view', async () => {
  let saved
  const notices = []
  const dsl = load('DSLGenerator', ['saveDSL'], { useAppStore: () => ({ dslState: { generatedYAML: 'yaml', generatedRuleId: 'A' }, showNotification: (...args) => notices.push(args) }), dslApi: { saveDSL: () => new Promise(resolve => { saved = resolve }), listDSL: async () => ({ rules: [] }) } })
  const saving = dsl.saveDSL()
  dsl.lifecycle.unmounted.forEach(fn => fn())
  saved()
  await saving
  assert.equal(notices.length, 0)
  let searched
  const store = { kbState: { searchQuery: 'old', documents: [{}], searchResults: [] }, showNotification() {} }
  const kb = load('KnowledgeBase', ['performSearch'], { useAppStore: () => store, knowledgeApi: { search: () => new Promise(resolve => { searched = resolve }) } })
  const search = kb.performSearch({ query: 'old' })
  store.kbState.searchQuery = 'new'
  searched({ results: [{ content: 'old' }] })
  await search
  assert.equal(store.kbState.searchResults.length, 0)
})
test('successful clear still reports metadata failure without throwing', () => {
  const warnings = []
  const view = load('AgentChat', ['loadSession', 'clearChat', 'sessionManagerRef', 'messages'], { ElMessage: { warning: value => warnings.push(value) } })
  view.loadSession('A')
  view.messages.value.push({ content: 'old' })
  view.sessionManagerRef.value = { updateSession() { throw new Error('storage denied') } }
  assert.doesNotThrow(() => view.clearChat())
  assert.equal(view.messages.value.length, 0)
  assert.equal(warnings.length, 1)
})
test('filtering from a later page still renders the remaining matching row', () => {
  for (const [name, search, filtered, store] of [
    ['DSLGenerator', 'searchQuery', 'filteredRules', { dslState: { dslList: [{ rule_id: 'a', title: 'yes' }] } }],
    ['KnowledgeBase', 'documentSearch', 'filteredDocuments', { kbState: { documents: [{ doc_id: 'a', name: 'yes' }] } }]
  ]) {
    const view = load(name, ['currentPage', 'pageSize', search, filtered], { useAppStore: () => store })
    view.currentPage.value = 3
    view.pageSize.value = 20
    view[search].value = 'yes'
    assert.equal(view[filtered].value.length, 1)
  }
})
let failed = 0
for (const [name, run] of cases) {
  try { await run(); console.log(`PASS ${name}`) } catch (error) { failed++; console.error(`FAIL ${name}: ${error.message}`) }
}
if (failed) process.exitCode = 1
