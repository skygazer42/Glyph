import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  createKnowledgeListLoader,
  createKnowledgeListState,
  getKnowledgeListPage,
  getKnowledgeListTotal,
  invalidateKnowledgeList,
  knowledgeListKey
} from '../src/utils/knowledgeList.js'

function deferred() {
  let resolve, reject
  const promise = new Promise((accept, fail) => { resolve = accept; reject = fail })
  return { promise, resolve, reject }
}

function pageResponse(params, id = `page-${params.page}`) {
  return {
    success: true,
    documents: [{ id, name: `${id}.pdf`, parsed: true, embedded: false, content: 'private body', attachment: 'private file' }],
    total: 43,
    page: params.page,
    page_size: params.page_size,
    summary: { total: 203, parsed: 103, embedded: 53 }
  }
}

function fixture() {
  let state = createKnowledgeListState()
  let time = 1000
  const requests = []
  const loader = createKnowledgeListLoader(() => state, (params, options) => {
    const request = { ...deferred(), params, signal: options.signal }
    requests.push(request)
    return request.promise
  }, () => time)
  return { loader, requests, get state() { return state }, advance(milliseconds) { time += milliseconds }, reset() { state = createKnowledgeListState() } }
}

test('complete query identity distinguishes every server filter, sort and page', () => {
  const defaults = { page: 1, page_size: 10, query: '', parsed: 'all', indexed: 'all', sort: 'newest' }
  const keys = [defaults, ...Object.entries({ page: 2, page_size: 20, query: '补贴', parsed: 'parsed', indexed: 'pending', sort: 'oldest' }).map(([name, value]) => ({ ...defaults, [name]: value }))].map(knowledgeListKey)
  assert.equal(new Set(keys).size, keys.length)
  assert.equal(knowledgeListKey({ ...defaults, query: '  补贴  ' }), knowledgeListKey({ ...defaults, query: '补贴' }))
})

test('uncached page gives immediate loading feedback without relabeling prior rows', async () => {
  const run = fixture()
  const first = run.loader.load({ page: 1 })
  run.requests[0].resolve(pageResponse(run.requests[0].params))
  await first
  const next = run.loader.load({ page: 2 })
  assert.equal(run.state.listLoading, true)
  assert.deepEqual(run.state.documents, [])
  assert.equal(getKnowledgeListPage(run.state), null)
  assert.equal(getKnowledgeListTotal(run.state), 43, 'total comes from the server response for the same filters')
  run.requests[1].resolve(pageResponse(run.requests[1].params))
  await next
  assert.equal(run.state.documents[0].id, 'page-2')
  assert.equal(run.state.listSummary.total, 203)
  assert.equal(getKnowledgeListTotal(run.state), 43)
  assert.equal('content' in run.state.documents[0], false)
  assert.equal('attachment' in run.state.documents[0], false)
})

test('visited pages render synchronously, expire after thirty seconds and refresh in place', async () => {
  const run = fixture()
  const first = run.loader.load({ page: 1 })
  run.requests[0].resolve(pageResponse(run.requests[0].params))
  await first
  const second = run.loader.load({ page: 2 })
  run.requests[1].resolve(pageResponse(run.requests[1].params))
  await second
  await run.loader.load({ page: 1 })
  assert.equal(run.requests.length, 2, 'fresh page does not request again on pagination')
  assert.equal(run.state.documents[0].id, 'page-1')
  run.advance(30000)
  const refresh = run.loader.load({ page: 1 })
  assert.equal(run.state.documents[0].id, 'page-1', 'expired metadata remains visible during revalidation')
  assert.equal(run.state.listLoading, true)
  run.requests[2].resolve(pageResponse(run.requests[2].params, 'updated'))
  await refresh
  const revisit = run.loader.load({ page: 1 }, { refresh: true })
  assert.equal(run.state.documents[0].id, 'updated')
  assert.equal(run.requests.length, 4, 'return-to-list can revalidate even a fresh page')
  run.requests[3].resolve(pageResponse(run.requests[3].params, 'latest'))
  await revisit
})

test('same query deduplicates and canceled old results cannot overwrite the active page', async () => {
  const run = fixture()
  const old = run.loader.load({ query: '旧资料' })
  assert.equal(run.loader.load({ query: '旧资料' }), old)
  assert.equal(run.requests.length, 1)
  const current = run.loader.load({ query: '新资料' })
  assert.equal(run.requests[0].signal.aborted, true)
  run.requests[1].resolve(pageResponse(run.requests[1].params, 'new'))
  await current
  run.requests[0].resolve(pageResponse(run.requests[0].params, 'old'))
  await old
  assert.equal(run.state.documents[0].id, 'new')
  assert.equal(Object.keys(run.state.listPages).length, 1)
  assert.equal(run.state.listLoading, false)
})

test('logout state replacement prevents late successes and failures from polluting another session', async () => {
  const run = fixture()
  const old = run.loader.load({})
  run.reset()
  const current = run.loader.load({})
  run.requests[0].resolve(pageResponse(run.requests[0].params, 'previous-user'))
  await old
  assert.deepEqual(run.state.documents, [])
  assert.equal(run.state.listLoading, true)
  run.requests[1].resolve(pageResponse(run.requests[1].params, 'current-user'))
  await current
  assert.equal(run.state.documents[0].id, 'current-user')
  const failed = run.loader.load({ page: 2 })
  run.reset()
  run.requests[2].reject(new Error('old session failure'))
  await failed
  assert.equal(run.state.listError, '')
  assert.deepEqual(run.state.listPages, {})
})

test('mutation invalidation retains the displayed page while invalidating other cached pages', async () => {
  const run = fixture()
  for (const page of [1, 2]) {
    const pending = run.loader.load({ page })
    run.requests.at(-1).resolve(pageResponse(run.requests.at(-1).params))
    await pending
  }
  invalidateKnowledgeList(run.state)
  assert.equal(Object.keys(run.state.listPages).length, 1)
  const reload = run.loader.load({ page: 2 })
  assert.equal(run.state.documents[0].id, 'page-2')
  assert.equal(run.state.listLoading, true)
  run.requests.at(-1).reject({ response: { data: { detail: '读取未完成' } } })
  await reload
  assert.equal(run.state.listError, '读取未完成')
  assert.equal(run.state.documents[0].id, 'page-2', 'a failed refresh preserves confirmed metadata')
})
