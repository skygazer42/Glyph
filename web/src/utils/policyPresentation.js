// Only the standard appliance result contract carries these monetary units.
export function getSubsidyResult(metadata) {
  const engine = metadata?.engine_result
  if (!engine || !['QUALIFIED', 'SUCCESS'].includes(engine.status)) return null
  const result = engine.calculation_details?.result
  if (!result || (result.status && !['QUALIFIED', 'SUCCESS'].includes(result.status))) return null
  const fields = ['price', 'rate', 'raw_subsidy', 'final_subsidy']
  if (!fields.every(field => typeof result[field] === 'number' && Number.isFinite(result[field]) && result[field] >= 0)) return null
  if (result.rate > 1) return null
  return {
    price: result.price,
    rate: result.rate,
    rawAmount: result.raw_subsidy,
    amount: result.final_subsidy,
    cap: typeof result.per_item_cap === 'number' && Number.isFinite(result.per_item_cap) && result.per_item_cap >= 0 ? result.per_item_cap : null,
    energyLevel: result.energy_level,
    traces: Array.isArray(engine.explainability_trace)
      ? engine.explainability_trace.map(step => typeof step === 'string' ? step : step?.description).filter(text => typeof text === 'string' && text.trim())
      : []
  }
}

export function formatPolicyNumber(value) {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)
}

export function getSourceUrl(path) {
  if (typeof path !== 'string' || path.trim() !== path || /[\u0000-\u0020\\]/.test(path)) return ''
  if (/^https?:\/\//i.test(path)) {
    try {
      const url = new URL(path)
      return url.username || url.password ? '' : url.href
    } catch {
      return ''
    }
  }
  try {
    const decoded = decodeURIComponent(path.split(/[?#]/, 1)[0])
    if (decoded.split('/').includes('..') || /[\u0000-\u0020\\]/.test(decoded)) return ''
  } catch {
    return ''
  }
  return /^\/(?:api\/uploads|resources)\//.test(path) || /^\/api\/knowledge\/documents\/[^/]+\/source(?:[?#]|$)/.test(path) ? path : ''
}

export function getPolicySources(metadata) {
  const sources = Array.isArray(metadata?.sources) ? metadata.sources : []
  const normalized = []
  for (const [citationIndex, source] of sources.entries()) {
    if (!source || typeof source !== 'object' || Array.isArray(source)) continue
    const record = {
      title: typeof source.title === 'string' ? source.title : '',
      path: typeof source.path === 'string' ? source.path : '',
      origin: typeof source.origin === 'string' ? source.origin : '',
      citation_index: citationIndex
    }
    const details = source.metadata && typeof source.metadata === 'object' ? source.metadata : {}
    for (const name of ['id', 'document_id', 'doc_id', 'source_id', 'document_title', 'source_version', 'parsed_version']) {
      const value = source[name] ?? details[name]
      if (typeof value === 'string' && value) record[name] = value
    }
    const url = [source.url, source.source_url, details.source_url, details.url].find(value => typeof value === 'string' && value)
    if (typeof url === 'string') record.url = url
    const excerpt = source.excerpt ?? source.content ?? details.excerpt ?? details.source_quote
    if (typeof excerpt === 'string' && excerpt) record.excerpt = excerpt
    const chunk = source.chunk_index ?? source.chunk_idx ?? details.chunk_index ?? details.chunk_idx
    if (typeof chunk === 'number' && Number.isFinite(chunk) || typeof chunk === 'string' && chunk) record.chunk_index = chunk
    for (const name of ['chunk_number', 'chunk_total']) {
      const value = source[name] ?? details[name]
      if (Number.isInteger(value) && value > 0) record[name] = value
    }
    const page = source.page ?? source.page_number ?? details.page ?? details.page_number
    if (typeof page === 'number' && Number.isFinite(page) || typeof page === 'string' && page) record.page = page
    if (record.title || record.path || record.origin || record.url || record.id || record.document_id || record.doc_id || record.excerpt) normalized.push(record)
  }
  const policy = metadata?.engine_result?.policy_source
  if (!normalized.length && typeof policy?.title === 'string' && policy.title) {
    const fallback = { title: policy.title, path: '', origin: typeof policy.doc_id === 'string' ? policy.doc_id : '', citation_index: 0 }
    if (typeof policy.url === 'string') fallback.url = policy.url
    if (typeof policy.doc_id === 'string') fallback.document_id = policy.doc_id
    if (typeof policy.clause === 'string') fallback.excerpt = policy.clause
    normalized.push(fallback)
  }
  return normalized
}

export function getPolicySourceUrl(source) {
  if (!source || typeof source !== 'object') return ''
  return getSourceUrl(source.url) || getSourceUrl(source.source_url) || getSourceUrl(source.origin) || getSourceUrl(source.path)
}

export function getPolicySourceLocation(source) {
  if (source.page !== undefined && source.page !== null && source.page !== '') return `第 ${source.page} 页`
  if (Number.isInteger(source.chunk_number) && source.chunk_number > 0) return `第 ${source.chunk_number} 段`
  const fragment = /[（(]\s*第?\s*(\d+)\s*\/\s*\d+\s*(?:段|片段|块)\s*[）)]\s*$/.exec(source.title || '')
  return fragment ? `第 ${fragment[1]} 段` : '引用摘录'
}

function sourceTitle(source) {
  return (source.document_title || source.title || '未命名政策资料').replace(/\s*[（(]\s*第?\s*\d+\s*\/\s*\d+\s*(?:段|片段|块)\s*[）)]\s*$/, '').trim()
}

function sourceIdentity(source, index) {
  const url = getPolicySourceUrl(source)
  const documentId = source.document_id || source.doc_id || source.source_id
  let identity
  if (url) {
    const parsed = new URL(url, 'https://glyph.invalid')
    parsed.hash = ''
    identity = `url:${parsed.href}|document:${documentId || ''}`
  } else if (documentId) {
    identity = `document:${documentId}`
  } else if (typeof source.path === 'string' && /\.(?:pdf|docx?|txt|md|html?)(?:$|[?#])/i.test(source.path)) {
    identity = `path:${source.path}`
  } else {
    identity = source.id ? `id:${source.id}` : `unidentified:${index}`
  }
  return `${identity}|version:${source.source_version || ''}`
}

export function groupPolicySources(sources) {
  const groups = new Map()
  for (const [index, source] of sources.entries()) {
    const key = sourceIdentity(source, index)
    if (!groups.has(key)) {
      groups.set(key, { key, title: sourceTitle(source), url: getPolicySourceUrl(source), sources: [], originalIndices: [], citationNumbers: [], primaryIndex: index })
    }
    const group = groups.get(key)
    group.sources.push(source)
    group.originalIndices.push(index)
    group.citationNumbers.push((source.citation_index ?? index) + 1)
  }
  return [...groups.values()]
}

function articleNumber(text) {
  const value = text.replace(/\s/g, '').replace(/[０-９]/g, character => String(character.charCodeAt(0) - 0xff10))
  if (/^\d+$/.test(value)) return Number(value)
  const digits = { 零: 0, 〇: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 }
  if (/^[零〇一二两三四五六七八九]+$/.test(value)) return Number([...value].map(character => digits[character]).join(''))
  if (!/^[零〇一二两三四五六七八九十百千万]+$/.test(value)) return null
  const units = { 十: 10, 百: 100, 千: 1000 }
  let total = 0
  let section = 0
  let digit = 0
  for (const character of value) {
    if (Object.hasOwn(digits, character)) {
      digit = digits[character]
    } else if (character === '万') {
      total += (section + digit) * 10000
      section = 0
      digit = 0
    } else {
      section += (digit || 1) * units[character]
      digit = 0
    }
  }
  return total + section + digit
}

export function resolveCitationSource(sources, sourceIndex, article) {
  const unresolved = { sourceIndex, matched: false, start: -1, end: -1, article: '' }
  const requested = /第\s*([\d０-９零〇一二两三四五六七八九十百千万\s]+?)\s*条/.exec(article || '')
  if (!requested || !sources[sourceIndex]) return unresolved
  const number = articleNumber(requested[1])
  if (number === null) return unresolved
  const group = groupPolicySources(sources).find(item => item.originalIndices.includes(sourceIndex))
  const indices = [sourceIndex, ...group.originalIndices.filter(index => index !== sourceIndex)]
  for (const index of indices) {
    const excerpt = sources[index].excerpt
    if (typeof excerpt !== 'string') continue
    for (const match of excerpt.matchAll(/第\s*([\d０-９零〇一二两三四五六七八九十百千万\s]+?)\s*条/g)) {
      if (articleNumber(match[1]) === number) return { sourceIndex: index, matched: true, start: match.index, end: match.index + match[0].length, article: match[0] }
    }
  }
  return unresolved
}

const inputLabels = { price: '购买金额', energy_level: '能效等级', category: '家电品类', city: '城市', region: '地区' }

export function getPolicyConditions(metadata) {
  const inputs = metadata?.inputs
  if (!inputs || typeof inputs !== 'object' || Array.isArray(inputs)) return []
  return Object.entries(inputs).filter(([, value]) => ['string', 'number', 'boolean'].includes(typeof value)).map(([name, value]) => ({
    name,
    label: inputLabels[name] || name,
    value: name === 'price' && typeof value === 'number' ? `${formatPolicyNumber(value)} 元` : String(value)
  }))
}
