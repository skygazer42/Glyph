const PAGE_TTL_MS = 30000
const MAX_CACHED_PAGES = 24

function normalizeQuery(params = {}) {
  return {
    page: Math.max(1, Number.parseInt(params.page, 10) || 1),
    page_size: [10, 20, 50].includes(params.page_size) ? params.page_size : 10,
    query: typeof params.query === 'string' ? params.query.trim() : '',
    parsed: ['parsed', 'unparsed'].includes(params.parsed) ? params.parsed : 'all',
    indexed: ['indexed', 'pending'].includes(params.indexed) ? params.indexed : 'all',
    sort: params.sort === 'oldest' ? 'oldest' : 'newest'
  }
}

export function knowledgeListKey(params) {
  return JSON.stringify(normalizeQuery(params))
}

export function createKnowledgeListState() {
  return {
    documents: [],
    listQuery: normalizeQuery(),
    listKey: '',
    listPages: {},
    listSummary: null,
    listLoading: false,
    listError: ''
  }
}

export function getKnowledgeListPage(state) {
  return state.listPages[state.listKey] ?? null
}

export function getKnowledgeListTotal(state) {
  const current = getKnowledgeListPage(state)
  if (current) return current.total
  // A page change retains the server's matching total for the same filters.
  const filterKey = knowledgeListKey({ ...state.listQuery, page: 1 })
  return Object.values(state.listPages).find(page => knowledgeListKey({ ...page.params, page: 1 }) === filterKey)?.total ?? 0
}

export function getKnownKnowledgeDocuments(state) {
  const documents = new Map()
  for (const page of Object.values(state.listPages)) {
    for (const document of page.documents) documents.set(document.id, document)
  }
  return [...documents.values()]
}

export function invalidateKnowledgeList(state) {
  const current = getKnowledgeListPage(state)
  state.listPages = current ? { [state.listKey]: { ...current, fetchedAt: 0 } } : {}
}

function readPage(response, params, fetchedAt) {
  if (
    response?.success !== true || !Array.isArray(response.documents) ||
    !Number.isInteger(response.total) || response.total < 0 ||
    response.page !== params.page || response.page_size !== params.page_size ||
    !['total', 'parsed', 'embedded'].every(name => Number.isInteger(response.summary?.[name]) && response.summary[name] >= 0)
  ) throw new Error('文档响应无效')
  return {
    params,
    // Lists cache metadata only, even if a future response includes body fields.
    documents: response.documents.map(({ id, name, size, modified, parsed, embedded, content_length, source_version }) => ({ id, name, size, modified, parsed, embedded, content_length, source_version })),
    total: response.total,
    summary: { total: response.summary.total, parsed: response.summary.parsed, embedded: response.summary.embedded },
    fetchedAt
  }
}

export function createKnowledgeListLoader(getState, requestPage, now = Date.now) {
  let activeRequest = null

  function cancel() {
    if (!activeRequest) return
    activeRequest.controller.abort()
    if (getState() === activeRequest.state) activeRequest.state.listLoading = false
    activeRequest = null
  }

  function load(params, { refresh = false } = {}) {
    const state = getState()
    const query = normalizeQuery(params)
    const key = knowledgeListKey(query)
    if (activeRequest?.state === state && activeRequest.key === key) return activeRequest.promise
    cancel()
    const cached = state.listPages[key]
    state.listQuery = query
    state.listKey = key
    state.documents = cached?.documents ?? []
    state.listError = ''
    if (cached && cached.fetchedAt > 0 && now() - cached.fetchedAt < PAGE_TTL_MS && !refresh) {
      state.listLoading = false
      return Promise.resolve(cached)
    }
    const controller = new AbortController()
    const request = { state, key, controller, promise: null }
    activeRequest = request
    state.listLoading = true
    request.promise = (async () => {
      try {
        const response = await requestPage(query, { signal: controller.signal })
        if (controller.signal.aborted || getState() !== state) return null
        const page = readPage(response, query, now())
        // Reinsert the refreshed page to bound metadata retention by recency.
        delete state.listPages[key]
        state.listPages[key] = page
        const keys = Object.keys(state.listPages)
        while (keys.length > MAX_CACHED_PAGES) delete state.listPages[keys.shift()]
        state.listSummary = page.summary
        state.documents = page.documents
        return page
      } catch (error) {
        if (!controller.signal.aborted && getState() === state) {
          const detail = error.response?.data?.detail
          state.listError = typeof detail === 'string' ? detail : '无法读取文档资料，请检查服务连接后重试。'
        }
        return null
      } finally {
        if (activeRequest === request) {
          if (getState() === state) state.listLoading = false
          activeRequest = null
        }
      }
    })()
    return request.promise
  }

  return { load, cancel }
}
