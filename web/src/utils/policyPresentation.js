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
  return /^\/(?:api\/uploads|resources)\//.test(path) && !path.split('/').includes('..') ? path : ''
}

export function getPolicySources(metadata) {
  const sources = Array.isArray(metadata?.sources) ? metadata.sources : []
  const normalized = sources.filter(source => source && typeof source === 'object').map(source => ({
    title: typeof source.title === 'string' ? source.title : '',
    path: typeof source.path === 'string' ? source.path : '',
    origin: typeof source.origin === 'string' ? source.origin : ''
  })).filter(source => source.title || source.path || source.origin)
  const policy = metadata?.engine_result?.policy_source
  if (!normalized.length && typeof policy?.title === 'string' && policy.title) {
    normalized.push({ title: policy.title, path: '', origin: typeof policy.doc_id === 'string' ? policy.doc_id : '' })
  }
  return normalized
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
