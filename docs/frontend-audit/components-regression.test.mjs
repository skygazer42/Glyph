import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import { createRequire } from 'node:module'
const require = createRequire(new URL('../../web/package.json', import.meta.url))
const { parse, compileScript, compileTemplate } = require('@vue/compiler-sfc')
const root = new URL('../../', import.meta.url)
function load(name, props = {}, extra = {}) {
  const source = fs.readFileSync(new URL(`web/src/components/${name}.vue`, root), 'utf8')
  const { descriptor } = parse(source)
  const stopped = []
  const timers = new Map()
  const messages = []
  const context = {
    defineProps: () => props, defineEmits: () => () => {}, defineExpose: () => {},
    ref: value => ({ value }), computed: getter => typeof getter === 'function' ? ({ get value() { return getter() } }) : ({ get value() { return getter.get() }, set value(value) { getter.set(value) } }),
    watch: () => {}, onUnmounted: fn => stopped.push(fn), onMounted: () => {},
    setTimeout: fn => { const id = timers.size + 1; timers.set(id, fn); return id }, clearTimeout: id => timers.delete(id),
    localStorage: { getItem: () => null, setItem: () => {} },
    ElMessage: { success: value => messages.push(['success', value]), error: value => messages.push(['error', value]), warning: value => messages.push(['warning', value]) },
    console, ...extra
  }
  const script = descriptor.scriptSetup.content.replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*$/gm, '')
  vm.createContext(context)
  vm.runInContext(script, context)
  return { run: expression => vm.runInContext(expression, context), stopped, timers, messages, source }
}
const tests = []
function test(name, run) { tests.push([name, run]) }
test('clipboard rejection produces error, never success', async () => {
  const c = load('CodeEditor', { modelValue: 'text' }, { navigator: { clipboard: { writeText: () => Promise.reject(new Error('denied')) } } })
  await c.run('handleCopy()')
  assert.equal(c.messages[0]?.[0], 'error')
})
test('invalid stored history normalizes to an empty list', () => {
  const c = load('SearchBar', { modelValue: '', maxHistory: 10 }, { localStorage: { getItem: () => '{"bad":true}' } })
  assert.equal(c.run('Array.isArray(searchHistory.value)'), true)
})
test('suggestions use escaped literal text and native keyboard buttons', () => {
  const c = load('SearchBar', { modelValue: '[' })
  assert.equal(c.source.includes('v-html='), false)
  assert.match(c.source, /<button[\s\S]*?class="suggestion-item"/)
})
test('pending input notification ends on component disposal', () => {
  const c = load('SearchBar', { modelValue: 'x', debounce: 300 })
  c.run('handleInput()')
  c.stopped.forEach(stop => stop())
  assert.equal(c.timers.size, 0)
})
test('uploads remain busy until all concurrent requests finish', () => {
  const c = load('FileUploader', { maxSize: 100 })
  c.run("beforeUpload({ uid: 1, size: 1, name: 'a' }); beforeUpload({ uid: 2, size: 1, name: 'b' }); handleSuccess({}, { uid: 1, size: 1, name: 'a' }, [])")
  assert.equal(c.run('uploading.value'), true)
})
test('upload accepts a MIME wildcard and custom removal updates both lists', () => {
  const c = load('FileUploader', { maxSize: 100, accept: 'image/*' })
  assert.equal(c.run("beforeUpload({ uid: 1, size: 1, name: 'a.png', type: 'image/png' })"), true)
  c.run("fileList.value = [{uid: 1}]; uploadedFiles.value = [{uid: 1}]; removeFile({uid: 1})")
  assert.equal(c.run('fileList.value.length'), 0)
})
test('search highlighting treats metacharacters and HTML as literal text', () => {
  const c = load('SearchBar', { modelValue: '[' })
  assert.equal(c.run("highlightMatch('<img>[a').map(part => part.text).join('')"), '<img>[a')
  assert.equal(c.run("highlightMatch('<img>[a').filter(part => part.match)[0].text"), '[')
})
test('cleared uploads ignore late successful responses', () => {
  const c = load('FileUploader', { maxSize: 100 })
  c.run("beforeUpload({uid: 1, size: 1, name: 'a'}); clearAll(); handleSuccess({}, {uid: 1, name: 'a'}, [])")
  assert.equal(c.run('uploadedFiles.value.length'), 0)
  assert.equal(c.messages.length, 0)
})
test('session rename failure keeps the draft and dialog, without a success toast', () => {
  const c = load('SessionManager', {}, { useSessionList: () => ({ sessions: {value: [{id: 'one', title: 'old'}]}, upsertSession: () => { throw new Error('full') }, removeSession: () => {}, clearAll: () => {} }) })
  c.run("selectedSession.value = {id: 'one', title: 'old'}; newSessionTitle.value = 'draft'; renameDialogVisible.value = true; confirmRename()")
  assert.equal(c.run('renameDialogVisible.value'), true)
  assert.equal(c.run('newSessionTitle.value'), 'draft')
  assert.equal(c.messages[0]?.[0], 'error')
})
test('rename preserves message metadata updated while its dialog was open', () => {
  let saved
  const c = load('SessionManager', {}, { useSessionList: () => ({ sessions: {value: [{id: 'one', title: 'old', messageCount: 3}]}, upsertSession: session => { saved = session }, removeSession: () => {}, clearAll: () => {} }) })
  c.run("selectedSession.value = {id: 'one', title: 'old', messageCount: 1}; newSessionTitle.value = 'new'; confirmRename()")
  assert.equal(saved.messageCount, 3)
})
test('session deletion distinguishes storage errors from dialog cancellation', async () => {
  const c = load('SessionManager', {}, { useSessionList: () => ({ sessions: {value: []}, upsertSession: () => {}, removeSession: () => {throw new Error('denied')}, clearAll: () => {} }), ElMessageBox: { confirm: () => Promise.resolve() } })
  await c.run("deleteSession({id: 'one', title: 'old'})")
  assert.equal(c.messages[0]?.[0], 'error')
})
test('announcement storage failures preserve page-local reading and dismissal', () => {
  const c = load('SystemAnnouncement', {}, { localStorage: { getItem: () => {throw new Error('denied')}, setItem: () => {throw new Error('denied')} } })
  c.run('fetchAnnouncement()')
  assert.equal(c.run('visible.value'), true)
  c.run('closeAnnouncement()')
  assert.equal(c.run('visible.value'), false)
})
test('mobile theme switch has only one mutation owner', () => {
  const source = fs.readFileSync(new URL('web/src/components/MobileMenu.vue', root), 'utf8')
  assert.equal(source.includes('v-model="isDark"'), false)
  assert.match(source, /:model-value="isDark"/)
})
test('committed session deletion reports incomplete history cleanup as a warning', async () => {
  const c = load('SessionManager', {}, { useSessionList: () => ({ sessions: {value: []}, upsertSession: () => {}, removeSession: () => ({failedHistoryIds: ['one']}), clearAll: () => ({failedHistoryIds: ['two']}) }), ElMessageBox: { confirm: () => Promise.resolve() } })
  await c.run("deleteSession({id: 'one', title: 'old'})")
  assert.equal(c.messages[0]?.[0], 'warning')
  assert.equal(c.messages[0]?.[1], '会话已删除，但部分本地消息缓存未清理')
  await c.run('clearAllSessions()')
  assert.equal(c.messages[1]?.[0], 'warning')
})
test('complete session deletion retains normal success feedback', async () => {
  const c = load('SessionManager', {}, { useSessionList: () => ({ sessions: {value: []}, upsertSession: () => {}, removeSession: () => ({failedHistoryIds: []}), clearAll: () => ({failedHistoryIds: []}) }), ElMessageBox: { confirm: () => Promise.resolve() } })
  await c.run("deleteSession({id: 'one', title: 'old'})")
  await c.run('clearAllSessions()')
  assert.equal(c.messages[0]?.[0], 'success')
  assert.equal(c.messages[1]?.[0], 'success')
})
test('back-to-top uses the app scroll owner and removes its exact listener', () => {
  let mount
  let listener
  let removed
  let scrolled
  const main = { scrollTop: 450, addEventListener: (event, fn) => { listener = fn }, removeEventListener: (event, fn) => { removed = fn }, scrollTo: options => { scrolled = options.top } }
  const c = load('BackToTop', {}, { Top: {}, window: { pageYOffset: 0, addEventListener: () => {}, removeEventListener: () => {}, scrollTo: () => {} }, document: { documentElement: { scrollTop: 0 }, querySelector: () => main }, onMounted: fn => { mount = fn } })
  mount()
  assert.equal(c.run('visible.value'), true)
  main.scrollTop = 0
  listener()
  assert.equal(c.run('visible.value'), false)
  c.run('scrollToTop()')
  assert.equal(scrolled, 0)
  c.stopped.forEach(stop => stop())
  assert.equal(removed, listener)
})
test('suggestion identity uses unique query strings without mutating props', () => {
  const suggestions = ['one', 'two', 'one']
  const c = load('SearchBar', { modelValue: '', suggestions, maxHistory: 10 })
  assert.equal(c.run('suggestionItems.value.join()'), 'one,two')
  assert.equal(suggestions.length, 3)
  assert.match(c.source, /v-for="item in suggestionItems"[\s\S]*?:key="item"/)
})
test('stored duplicate history uses one stable query identity', () => {
  const c = load('SearchBar', { modelValue: '', suggestions: [], maxHistory: 10 }, { localStorage: { getItem: () => '["one","one","two"]' } })
  assert.equal(c.run('searchHistory.value.join()'), 'one,two')
  assert.match(c.source, /v-for="\(item, index\) in searchHistory"[\s\S]*?:key="item"/)
})
test('disabled upload renders no enabled inner native trigger', async () => {
  const { createSSRApp } = require('vue')
  const { renderToString } = require('@vue/server-renderer')
  const elementPlus = require('element-plus')
  const source = fs.readFileSync(new URL('web/src/components/FileUploader.vue', root), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'disabled-upload', inlineTemplate: true }).content
    .replace(/import\s+\{([\s\S]*?)\}\s+from\s+['"]([^'"]+)['"]/g, (_, names, module) => `const { ${names.replace(/\s+as\s+/g, ': ')} } = require('${module}')`)
    .replace('export default', 'return')
  const component = new Function('require', script)(require)
  const app = createSSRApp(component, { drag: false, disabled: true })
  app.use(elementPlus.default)
  const html = await renderToString(app)
  const buttons = html.match(/<button\b[^>]*>/g)
  assert.ok(buttons?.length > 0)
  assert.ok(buttons.every(button => /\sdisabled(?:[\s=>])/.test(button)), html)
})
let failed = 0
for (const [name, run] of tests) {
  try { await run(); console.log(`PASS ${name}`) } catch (error) { failed++; console.error(`FAIL ${name}: ${error.message}`) }
}
for (const name of fs.readdirSync(new URL('web/src/components/', root)).filter(name => name.endsWith('.vue'))) {
  const { descriptor, errors } = parse(fs.readFileSync(new URL(`web/src/components/${name}`, root), 'utf8'))
  assert.equal(errors.length, 0)
  const script = compileScript(descriptor, { id: name })
  const result = compileTemplate({ source: descriptor.template.content, filename: name, id: name, compilerOptions: { bindingMetadata: script.bindings } })
  assert.equal(result.errors.length, 0, `${name}: ${result.errors}`)
}
console.log('Compiled all 14 component SFCs')
process.exitCode = failed ? 1 : 0
