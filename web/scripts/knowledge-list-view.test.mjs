import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { compileScript, parse } from '@vue/compiler-sfc'
import * as Vue from 'vue'
import { createPinia, defineStore } from 'pinia'
import * as knowledgeList from '../src/utils/knowledgeList.js'

// Exercise the actual SFC setup and Pinia store with Vue's renderer. The host
// has no DOM: this checks request/watch/lifecycle behavior, not browser layout.
const storeSource = readFileSync(new URL('../src/stores/app.js', import.meta.url), 'utf8')
const useAppStore = new Function('defineStore', 'ref', 'computed', 'onScopeDispose', 'ElMessage', 'createKnowledgeListState', `${storeSource.replace(/^import .*$/gm, '').replace('export const useAppStore', 'const useAppStore')}\nreturn useAppStore`)(defineStore, Vue.ref, Vue.computed, Vue.onScopeDispose, () => {}, knowledgeList.createKnowledgeListState)
const descriptor = parse(readFileSync(new URL('../src/views/KnowledgeBase.vue', import.meta.url), 'utf8')).descriptor
const script = compileScript(descriptor, { id: 'knowledge-list-test', genDefaultAs: 'KnowledgeBase' })
const renderer = Vue.createRenderer({
  createComment: text => ({ text }),
  insert() {}, remove() {}, parentNode() {}, nextSibling() {},
  createElement: () => ({}), createText: text => ({ text }),
  setText() {}, setElementText() {}, patchProp() {}
})

function pageResponse(params, total = 43) {
  return { success: true, documents: total ? [{ id: `page-${params.page}.pdf`, name: `page-${params.page}.pdf`, size: 100, modified: 1, parsed: true, embedded: false }] : [], total, page: params.page, page_size: params.page_size, summary: { total: 203, parsed: 103, embedded: 53 } }
}

async function flush() {
  await Promise.resolve()
  await Vue.nextTick()
  await Promise.resolve()
}

function fixture() {
  const pinia = createPinia()
  const store = useAppStore(pinia)
  const route = Vue.reactive({ path: '/knowledge', query: {} })
  const requests = []
  const timers = new Map()
  let clock = 0
  let timerId = 0
  const setTimeout = (callback, milliseconds) => { const id = ++timerId; timers.set(id, { callback, at: clock + milliseconds }); return id }
  const clearTimeout = id => { timers.delete(id) }
  const knowledgeApi = {
    getCapabilities: async () => ({ capabilities: {} }),
    listDocuments(params, options) {
      let resolve
      const promise = new Promise(accept => { resolve = accept })
      requests.push({ params, signal: options.signal, resolve })
      return promise
    }
  }
  const router = { async push({ query }) { route.query = query }, async replace({ query }) { route.query = query } }
  const modules = { vue: Vue, 'vue-router': { useRoute: () => route, useRouter: () => router }, '@/api': { knowledgeApi }, '@/stores/app': { useAppStore: () => store }, '@/utils/knowledgeList': knowledgeList }
  const bindings = Object.fromEntries(Object.entries(script.imports).map(([name, entry]) => [name, modules[entry.source]?.[entry.imported] ?? {}]))
  const component = new Function(...Object.keys(bindings), 'setTimeout', 'clearTimeout', `${script.content.replace(/^import .*$/gm, '').replaceAll('import.meta.env.DEV', 'false')}\nreturn KnowledgeBase`)(...Object.values(bindings), setTimeout, clearTimeout)
  let app, view
  function mount() {
    app = renderer.createApp({ ...component, render: () => null })
    app.use(pinia)
    view = app.mount({}).$.setupState
  }
  mount()
  return {
    store, route, requests, get view() { return view }, mount,
    unmount() { app.unmount() },
    async finish(total) { const request = requests.at(-1); request.resolve(pageResponse(request.params, total)); await flush() },
    async advance(milliseconds) {
      clock += milliseconds
      for (const [id, timer] of timers) {
        if (timer.at <= clock) { timers.delete(id); timer.callback() }
      }
      await flush()
    }
  }
}

test('actual view sends server pagination and filters, resetting the page in one request', async () => {
  const run = fixture()
  try {
    assert.deepEqual(run.requests[0].params, { page: 1, page_size: 10, query: '', parsed: 'all', indexed: 'all', sort: 'newest' })
    await run.finish()
    assert.equal(run.view.matchingTotal, 43)
    assert.equal(run.view.listSummary.total, 203)
    run.view.currentPage = 2
    await flush()
    assert.equal(run.requests.length, 2)
    assert.equal(run.view.loaded, false)
    assert.deepEqual(run.view.documents, [])
    await run.finish()
    run.view.documentStatus = 'parsed'
    run.view.documentIndexStatus = 'pending'
    run.view.documentSortDirection = 1
    run.view.pageSize = 20
    await flush()
    assert.equal(run.requests.length, 3)
    assert.deepEqual(run.requests[2].params, { page: 1, page_size: 20, query: '', parsed: 'parsed', indexed: 'pending', sort: 'oldest' })
    await run.finish(0)
    assert.equal(run.view.loaded, true)
    assert.equal(run.view.matchingTotal, 0)
    assert.equal(run.view.listSummary.total, 203, 'filtered empty state retains global summary')
  } finally { run.unmount() }
})

test('filename search waits for the final input and sends it after the debounce', async () => {
  const run = fixture()
  try {
    await run.finish()
    run.view.documentQuery = '旧词'
    await flush()
    await run.advance(60)
    run.view.documentQuery = '补贴'
    await flush()
    await run.advance(119)
    assert.equal(run.requests.length, 1)
    await run.advance(1)
    assert.equal(run.requests.length, 2)
    assert.equal(run.requests[1].params.query, '补贴')
    await run.finish()
  } finally { run.unmount() }
})

test('pagination and detail return show cached rows; remount refreshes and logout clears metadata', async () => {
  const run = fixture()
  try {
    await run.finish()
    run.view.currentPage = 2
    await flush()
    await run.finish()
    run.view.currentPage = 1
    await flush()
    assert.equal(run.requests.length, 2)
    assert.equal(run.view.documents[0].id, 'page-1.pdf')
    assert.equal(run.view.findResultDocument({ source: '/uploads/uncached.pdf' }).id, 'uncached.pdf')
    run.route.query = { doc: 'page-1.pdf' }
    await flush()
    run.route.query = {}
    await flush()
    assert.equal(run.requests.length, 3)
    assert.equal(run.view.documents[0].id, 'page-1.pdf')
    assert.equal(run.view.loading, true)
    await run.finish()
    run.unmount()
    run.mount()
    assert.equal(run.view.documents[0].id, 'page-1.pdf')
    assert.equal(run.requests.length, 4)
    run.store.resetPrivateState()
    await run.finish()
    assert.equal(run.store.documentCount, 0)
    assert.deepEqual(run.store.kbState.documents, [])
    assert.deepEqual(run.store.kbState.listPages, {})
  } finally { run.unmount() }
})

test('mutation refresh invalidates visited pages and moves an emptied final page to a valid page', async () => {
  const run = fixture()
  try {
    await run.finish()
    run.view.currentPage = 5
    await flush()
    await run.finish()
    const reload = run.view.loadDocuments()
    assert.equal(run.requests.length, 3)
    assert.equal(Object.keys(run.store.kbState.listPages).length, 1)
    run.requests[2].resolve({ ...pageResponse(run.requests[2].params, 3), documents: [] })
    await reload
    await flush()
    assert.equal(run.view.currentPage, 1)
    assert.equal(run.requests.length, 4)
    assert.equal(run.requests[3].params.page, 1)
    await run.finish(3)
    assert.equal(run.view.matchingTotal, 3)
    assert.equal(run.view.documents[0].id, 'page-1.pdf')
  } finally { run.unmount() }
})
