import assert from 'node:assert/strict'
import { GRAPH_KINDS, graphKind, graphNodeSize, mergeSubgraph, visibleNeighbors, hiddenNeighborCount, shortGraphLabel, relationLabel, presentationEdges } from '../src/utils/graphPresentation.js'
assert.equal(graphKind('"ORGANIZATION"'), 'org')
assert.equal(graphKind('未知'), 'other')
assert.equal(graphKind(' "POLICY" ', '消费者'), 'policy')
assert.equal(graphKind(" 'org' ", '补贴实施细则'), 'org')
assert.equal(graphKind('condition', '省财政厅'), 'condition')
const rawNode = Object.freeze({ id: 'raw', type: ' "CONTENT" ', label: " '购车人' " })
assert.equal(graphKind(rawNode.type, rawNode.label), 'condition')
assert.deepEqual(rawNode, { id: 'raw', type: ' "CONTENT" ', label: " '购车人' " })
for (const type of ['document', 'CONTENT', 'unknown', '未知', '']) {
  assert.equal(graphKind(type, '新能源汽车补贴实施细则'), 'policy')
  assert.equal(graphKind(type, '消费者购车发票'), 'condition')
  assert.equal(graphKind(type, '市商务局'), 'org')
}
for (const label of ['实施方案', '财政公告', '申报通知', '支持政策']) assert.equal(graphKind('document', label), 'policy')
for (const label of ['机动车行驶证', '车辆登记证', '购车人', '能效门槛']) assert.equal(graphKind('content', label), 'condition')
for (const label of ['省财政厅', '审批机构', '企事业单位']) assert.equal(graphKind('unknown', label), 'org')
assert.equal(graphKind('unknown', '补贴金额'), 'other')
assert.equal(graphKind('website', '济南市商务局官方网站'), 'other')
assert.equal(graphKind('location', '政策试点地区'), 'other')
assert.equal(graphKind('unknown', '补贴对象'), 'other')
assert.ok(Object.values(GRAPH_KINDS).every(kind => !Object.hasOwn(kind, 'size')))
assert.deepEqual([0, 4, 5, 15, 16, 99].map(graphNodeSize), [22, 22, 32, 32, 44, 44])
assert.equal(shortGraphLabel('  甲\n乙\t丙  '), '甲 乙 丙')
assert.equal(shortGraphLabel('甲乙丙丁戊己庚辛壬癸子'), '甲乙丙丁戊己庚辛壬癸子')
assert.equal(shortGraphLabel('甲乙丙丁戊己庚辛壬癸子丑'), '甲乙丙丁戊己庚辛壬癸子…')
assert.equal(shortGraphLabel('😀𠮷政策文件', 3), '😀𠮷政…')
assert.equal(shortGraphLabel('短名'), '短名')
assert.equal(relationLabel(' "DOCUMENT_REL" '), '关联材料')
assert.equal(relationLabel('publish_by, apply_to；subsidy_rule'), '发文机构、适用对象、补贴标准')
assert.equal(relationLabel('document_rel|publish_by/apply_to'), '关联材料、发文机构、适用对象')
assert.equal(relationLabel('共同发文、适用范围'), '共同发文、适用范围')
assert.equal(relationLabel('unknown_relation'), '关联关系')
assert.equal(relationLabel('constructor,__proto__'), '关联关系')
assert.equal(relationLabel('unknown_relation,apply_to'), '关联关系、适用对象')
assert.equal(relationLabel(''), '关联关系')
const current = { revision: 'a', nodes: [{ id: 'a', neighbor_count: 2 }, { id: 'b', neighbor_count: 1 }], links: [{ id: 'ab-1', source: 'a', target: 'b' }] }
const next = { revision: 'a', nodes: [{ id: 'a', neighbor_count: 2 }, { id: 'c', neighbor_count: 1 }], links: [{ id: 'ab-2', source: 'a', target: 'b' }, { id: 'ac', source: 'a', target: 'c' }, { id: 'aa', source: 'a', target: 'a' }], truncated: false }
const merged = mergeSubgraph(current, next)
assert.equal(merged.nodes.length, 3)
assert.equal(merged.links.length, 4)
assert.equal(hiddenNeighborCount(merged.nodes[0], visibleNeighbors(merged)), 0)
const capped = mergeSubgraph(current, next, 2)
assert.equal(capped.nodes.length, 2)
assert.ok(capped.links.every(link => link.source !== 'c' && link.target !== 'c'))
assert.ok(capped.truncated)
assert.deepEqual(mergeSubgraph(current, { ...next, revision: 'b' }).nodes.map(node => node.id), ['a', 'c'])
assert.equal(hiddenNeighborCount({ id: 'a', neighbor_count: 5 }, visibleNeighbors(merged)), 3)
assert.equal(visibleNeighbors(merged).get('a').size, 2)
const distinctOrganizations = [
  { id: 'org-full', label: '某市商务局', type: 'org' },
  { id: 'org-same', label: '某市商务局', type: 'org' },
  { id: 'org-short', label: '市商务局', type: 'org' }
]
assert.deepEqual(mergeSubgraph({ revision: 'a', nodes: [], links: [] }, {
  revision: 'a', nodes: distinctOrganizations, links: []
}).nodes, distinctOrganizations)

const links = Object.freeze([
  { id: 'ab-zero', source: 'a', target: 'b', directed: false, keywords: 'document_rel', weight: 0 },
  { id: 'ba-undirected', source: 'b', target: 'a', directed: false, keywords: '关联材料', weight: 0.7 },
  { id: 'ab-directed-1', source: 'a', target: 'b', directed: true, keywords: 'apply_to', weight: 1 },
  { id: 'ab-directed-2', source: 'a', target: 'b', directed: true, keywords: 'subsidy_rule', weight: 2 },
  { id: 'ba-directed-1', source: 'b', target: 'a', directed: true, keywords: 'publish_by', weight: 0.3 },
  { id: 'ba-directed-2', source: 'b', target: 'a', directed: true, keywords: 'unknown_relation', weight: 0.4 },
  { id: 'self-undirected-1', source: 'a', target: 'a', directed: false, keywords: '关联自身', weight: 0 },
  { id: 'self-undirected-2', source: 'a', target: 'a', directed: false, keywords: 'document_rel', weight: 2 },
  { id: 'self-directed', source: 'a', target: 'a', directed: true, keywords: 'apply_to', weight: 0 },
  { id: 'cd-1', source: 'c', target: 'd', directed: false, keywords: 'publish_by', weight: 7 },
  { id: 'cd-2', source: 'd', target: 'c', directed: false, keywords: 'apply_to', weight: 8 }
].map(link => Object.freeze(link)))
const before = JSON.stringify(links)
const overview = presentationEdges(links)
assert.equal(overview.length, 6)
assert.deepEqual(overview.map(edge => edge.count), [2, 2, 2, 2, 1, 2])
assert.equal(overview.find(edge => !edge.directed && edge.source === 'a' && edge.target === 'b').keywords, 'document_rel')
assert.ok(overview.some(edge => edge.directed && edge.source === 'a' && edge.target === 'b'))
assert.ok(overview.some(edge => edge.directed && edge.source === 'b' && edge.target === 'a'))
assert.equal(overview.filter(edge => edge.source === edge.target).length, 2)
assert.deepEqual(presentationEdges([...links].reverse()).map(edge => edge.id).sort(), overview.map(edge => edge.id).sort())
assert.deepEqual(presentationEdges(links, 'absent'), overview)

const focused = presentationEdges(links, 'a')
assert.equal(focused.length, 10)
const adjacent = focused.filter(edge => edge.source === 'a' || edge.target === 'a')
assert.equal(adjacent.length, 9)
assert.ok(adjacent.every(edge => !edge.aggregated && edge.count === 1))
assert.equal(focused.find(edge => edge.source === 'c').count, 2)
assert.equal(focused.find(edge => edge.source === 'c').aggregated, true)
for (const edge of adjacent) {
  const original = edge.members[0]
  assert.equal(edge.source, original.source)
  assert.equal(edge.target, original.target)
  assert.equal(edge.directed, original.directed)
  assert.equal(edge.keywords, original.keywords)
}
for (const edges of [overview, focused]) {
  assert.equal(new Set(edges.map(edge => edge.id)).size, edges.length)
  assert.ok(edges.every(edge => !links.some(link => link.id === edge.id)))
  assert.deepEqual(edges.flatMap(edge => edge.members).map(link => link.id).sort(), links.map(link => link.id).sort())
  for (const member of edges.flatMap(edge => edge.members)) assert.equal(member, links.find(link => link.id === member.id))
  assert.equal(edges.reduce((sum, edge) => sum + edge.count, 0), links.length)
  assert.deepEqual(edges.flatMap(edge => edge.members).filter(link => link.weight === 0).map(link => link.id).sort(), ['ab-zero', 'self-directed', 'self-undirected-1'])
}
assert.deepEqual(presentationEdges([...links].reverse(), 'a').map(edge => edge.id).sort(), focused.map(edge => edge.id).sort())
assert.deepEqual(presentationEdges([]), [])
assert.equal(JSON.stringify(links), before)
