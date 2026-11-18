export const GRAPH_KINDS = {
  policy: { label: '政策文件', token: '--wb-graph-policy' },
  org: { label: '机构主体', token: '--wb-graph-org' },
  condition: { label: '适用条件', token: '--wb-graph-condition' },
  other: { label: '其他实体', token: '--wb-graph-other' }
}

function unquote(value) {
  return String(value ?? '').trim().replace(/^["']+|["']+$/g, '').trim()
}

export function graphKind(type, label = '') {
  const value = unquote(type).toLowerCase()
  if (/政策|法规|条例|policy|regulation/.test(value)) return 'policy'
  if (/机构|部门|组织|政府|organization|organisation|government|agency|^(org|department|institution)$/.test(value)) return 'org'
  if (/条件|标准|资格|分类|condition|criteria|category|requirement/.test(value)) return 'condition'
  if (/^(website|webpage|url|location|region|city|province|application|app|platform|system)$/.test(value)) return 'other'
  const name = unquote(label)
  if (/细则|方案|公告|通知|政策/.test(name)) return 'policy'
  if (/发票|行驶证|登记证|消费者|购车人|能效门槛/.test(name)) return 'condition'
  if (/机构|局|厅|企业|事业单位/.test(name)) return 'org'
  return 'other'
}

export function graphNodeSize(degree) {
  return degree > 15 ? 44 : degree >= 5 ? 32 : 22
}

export function mergeSubgraph(current, incoming, maxNodes = 600) {
  const previous = current.revision === incoming.revision ? current : { nodes: [], links: [] }
  const nodes = new Map(previous.nodes.map(node => [node.id, node]))
  for (const node of incoming.nodes) {
    if (nodes.has(node.id) || nodes.size < maxNodes) nodes.set(node.id, node)
  }
  const links = new Map(previous.links.map(link => [link.id, link]))
  for (const link of incoming.links) {
    if (nodes.has(link.source) && nodes.has(link.target)) links.set(link.id, link)
  }
  return { ...incoming, nodes: [...nodes.values()], links: [...links.values()], truncated: incoming.truncated || nodes.size < new Set([...previous.nodes, ...incoming.nodes].map(node => node.id)).size }
}

export function visibleNeighbors(data) {
  const neighbors = new Map(data.nodes.map(node => [node.id, new Set()]))
  for (const link of data.links) {
    if (link.source !== link.target) {
      neighbors.get(link.source)?.add(link.target)
      neighbors.get(link.target)?.add(link.source)
    }
  }
  return neighbors
}

export function hiddenNeighborCount(node, neighbors) {
  return Math.max(0, node.neighbor_count - (neighbors.get(node.id)?.size ?? 0))
}

export function shortGraphLabel(label, maxLength = 11) {
  const text = String(label ?? '').replace(/\s+/gu, ' ').trim()
  const chars = Array.from(text)
  return chars.length <= maxLength ? text : chars.slice(0, maxLength).join('') + '…'
}

const RELATION_LABELS = {
  document_rel: '关联材料',
  publish_by: '发文机构',
  apply_to: '适用对象',
  subsidy_rule: '补贴标准'
}

export function relationLabel(raw) {
  const labels = unquote(raw).split(/[,，、;；|\/\r\n]+/u).filter(part => part.trim()).map(part => {
    const value = unquote(part)
    const key = value.toLowerCase()
    return Object.hasOwn(RELATION_LABELS, key) ? RELATION_LABELS[key] : /\p{Script=Han}/u.test(value) ? value : '关联关系'
  })
  return [...new Set(labels)].join('、') || '关联关系'
}

export function presentationEdges(links, focusId = '') {
  const groups = new Map()
  for (const link of links) {
    let { source, target } = link
    const directed = Boolean(link.directed)
    if (!directed && source > target) [source, target] = [target, source]
    const key = JSON.stringify([source, target, directed])
    if (!groups.has(key)) groups.set(key, { source, target, directed, members: [] })
    groups.get(key).members.push(link)
  }
  return [...groups].flatMap(([key, group]) => {
    if (focusId && (group.source === focusId || group.target === focusId)) {
      return group.members.map(link => ({
        id: `graph:edge:${JSON.stringify(link.id)}`,
        source: link.source,
        target: link.target,
        directed: Boolean(link.directed),
        keywords: link.keywords,
        members: [link],
        aggregated: false,
        count: 1
      }))
    }
    return [{
      id: `graph:group:${key}`,
      ...group,
      keywords: group.members[0].keywords,
      aggregated: group.members.length > 1,
      count: group.members.length
    }]
  })
}
