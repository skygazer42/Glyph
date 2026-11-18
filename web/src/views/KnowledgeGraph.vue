<template>
  <section ref="stageRef" class="workspace-module graph-page" :class="{ 'has-inspector': detailsVisible }" aria-label="政策实体关系图谱">
    <div class="graph-stage" :aria-busy="loading">
      <div ref="canvasRef" class="graph-canvas" role="img" :aria-label="`当前显示 ${graphData.nodes.length} 个实体、${graphData.links.length} 条关系；可通过搜索和实体列表使用键盘选择。`" />
      <div class="graph-hud graph-search-hud">
        <el-autocomplete v-model="searchQuery" :fetch-suggestions="searchEntities" :prefix-icon="Search" :trigger-on-focus="false" :debounce="250" clearable placeholder="搜索实体名称、类型或标识" aria-label="搜索图谱实体" class="graph-search" @select="selectSearchResult" @clear="resetSpotlight">
          <template #default="{ item }"><span class="graph-suggestion"><span>{{ item.value }}</span><small>{{ GRAPH_KINDS[graphKind(item.type, item.label)].label }}</small></span></template>
        </el-autocomplete>
        <div class="graph-hops"><span>关联</span><el-radio-group v-model="depth" aria-label="关联层级" size="small" :disabled="loading" @change="changeDepth"><el-radio-button v-for="level in 3" :key="level" :value="level">{{ level }} 层</el-radio-button></el-radio-group></div>
        <span class="graph-status-pill">只读核对</span>
      </div>
      <p v-if="searchError" class="graph-search-error" role="status">{{ searchError }}</p>
      <div v-if="loading && !graphData.nodes.length" class="graph-state" role="status"><el-icon class="is-loading"><Loading /></el-icon><strong>正在构建关系概览</strong><p>读取核心实体与直接关联</p></div>
      <UnavailableState v-else-if="loadError && !graphData.nodes.length" class="graph-state" title="暂时无法读取图谱" description="已有资料不会改变，请确认服务连接后重新读取。" :detail="loadError" @retry="loadOverview" />
      <div v-else-if="!graphData.nodes.length" class="graph-state"><el-icon><Connection /></el-icon><strong>尚未形成实体关系</strong><p>政策资料形成图谱后，可在此核对关联。</p></div>
      <div v-if="notice || (loadError && graphData.nodes.length)" class="graph-notice" role="status">{{ loadError || notice }}<button type="button" @click="notice = ''; loadError = ''" aria-label="关闭图谱提示"><el-icon><Close /></el-icon></button></div>
      <div class="graph-hud graph-summary-hud">
        <div class="graph-scope-hud"><span>{{ centerId ? '关联子图' : '核心概览' }}</span><span><strong>{{ graphData.nodes.length }}</strong> 实体 / <strong>{{ graphData.links.length }}</strong> 关系</span><span class="graph-total-count">全库 {{ graphData.total_nodes }} 实体</span><button v-if="centerId" type="button" :disabled="loading" @click="loadOverview">返回概览</button><span v-if="loading && graphData.nodes.length" role="status">正在读取…</span></div>
        <div class="graph-legend" aria-label="图谱图例"><span v-for="(kind, key) in GRAPH_KINDS" :key="key"><i :style="{ background: `var(${kind.token})` }" />{{ kind.label }}</span><span><i class="legend-edge" />关联</span></div>
        <span v-if="zoomPercent < 65" class="graph-zoom-hint">放大或搜索查看名称，点击实体查看完整关系。</span>
      </div>
      <div class="graph-hud graph-view-tools" aria-label="图谱视图工具">
        <button type="button" aria-label="缩小图谱" title="缩小" :disabled="!graphData.nodes.length || loading" @click="zoomBy(.8)"><el-icon><ZoomOut /></el-icon></button>
        <output aria-label="图谱缩放比例">{{ zoomPercent }}%</output>
        <button type="button" aria-label="放大图谱" title="放大" :disabled="!graphData.nodes.length || loading" @click="zoomBy(1.25)"><el-icon><ZoomIn /></el-icon></button>
        <button type="button" aria-label="适应画布" title="适应画布" :disabled="!graphData.nodes.length || loading" @click="fitView"><el-icon><Aim /></el-icon></button>
        <button type="button" :aria-label="fullscreen ? '退出全屏图谱' : '全屏图谱'" title="全屏" @click="toggleFullscreen"><el-icon><FullScreen /></el-icon></button>
        <button type="button" aria-label="重新读取图谱" title="重新读取" :disabled="loading" @click="loadOverview"><el-icon><Refresh /></el-icon></button>
        <button type="button" :aria-expanded="detailsVisible" aria-controls="graph-inspector" :aria-label="detailsVisible ? '收起实体详情' : '展开实体详情'" @click="detailsVisible = !detailsVisible"><el-icon><component :is="detailsVisible ? Fold : Expand" /></el-icon></button>
      </div>
    </div>
    <aside v-if="detailsVisible" id="graph-inspector" class="graph-inspector" aria-label="实体详情">
      <header><h2>实体详情</h2><button type="button" aria-label="收起实体详情" @click="detailsVisible = false"><el-icon><Close /></el-icon></button></header>
      <div v-if="selectedNode" class="entity-content">
        <span class="entity-type" :title="`原始分类：${selectedNode.type}`"><i :style="{ background: `var(${GRAPH_KINDS[graphKind(selectedNode.type, selectedNode.label)].token})` }" />{{ GRAPH_KINDS[graphKind(selectedNode.type, selectedNode.label)].label }}</span>
        <h2>{{ selectedNode.label }}</h2><p class="entity-description">{{ selectedNode.description.replaceAll('<SEP>', '\n\n') || '此实体暂未提供说明。' }}</p>
        <section><details v-if="selectedNode.source_id" class="entity-source-details"><summary>查看来源标识</summary><p class="entity-source">{{ selectedNode.source_id }}</p></details><p v-else class="entity-help">暂未提供来源标识。</p></section>
        <el-button v-if="hiddenCount" :disabled="loading || graphData.nodes.length >= MAX_NODES" @click="expandNode(selectedNode.id)">展开 {{ hiddenCount }} 个未显示关联</el-button>
        <p v-else class="entity-help">该实体的直接关联已全部显示。</p>
        <p class="entity-help">也可双击节点展开一跳；点击空白处取消聚焦。</p>
        <section>
          <h3>已显示的相邻关系 <span>{{ selectedRelations.length }}</span></h3>
          <ul class="entity-relations">
            <li v-for="relation in selectedRelations" :key="relation.id">
              <span>{{ relationLabel(relation.keywords) }}</span>
              <button type="button" @click="selectNode(relation.neighbor.id, true)">{{ relation.neighbor.label }}</button>
              <small>{{ relation.directed ? (relation.source === selectedNode.id ? '当前实体 → 关联实体' : '关联实体 → 当前实体') : '无向关联' }}</small>
              <details>
                <summary>关系详情</summary>
                <p v-if="relation.description">{{ relation.description.replaceAll('<SEP>', '\n\n') }}</p>
                <p>关系权重（原始值）：{{ relation.weight }}</p>
                <p v-if="relation.keywords" class="entity-raw-relation">原始关系字段：{{ relation.keywords }}</p>
              </details>
            </li>
          </ul>
        </section>
      </div>
      <div v-else class="inspector-empty"><el-icon><Connection /></el-icon><h2>选择一个实体</h2><p>点击节点或搜索实体，查看说明、来源与相邻关系。</p></div>
      <details v-if="graphData.nodes.length" class="graph-entity-list"><summary>当前实体列表 · {{ graphData.nodes.length }}</summary><button v-for="node in graphData.nodes" :key="node.id" type="button" @click="selectNode(node.id, true)">{{ node.label }}<span :title="node.type">{{ GRAPH_KINDS[graphKind(node.type, node.label)].label }}</span></button></details>
    </aside>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Graph, NodeEvent } from '@antv/g6'
import { Aim, Close, Connection, Expand, Fold, FullScreen, Loading, Refresh, Search, ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import { graphApi } from '@/api'
import { useTheme } from '@/composables/useTheme'
import UnavailableState from '@/components/UnavailableState.vue'
import { GRAPH_KINDS, graphKind, graphNodeSize, hiddenNeighborCount, mergeSubgraph, presentationEdges, relationLabel, shortGraphLabel, visibleNeighbors } from '@/utils/graphPresentation'

const MAX_NODES = 600
const stageRef = ref(null)
const canvasRef = ref(null)
const graphData = ref({ nodes: [], links: [], total_nodes: 0, total_links: 0, revision: '', truncated: false })
const selectedId = ref('')
const hoveredId = ref('')
const focusId = computed(() => selectedId.value || hoveredId.value)
const selectedNode = computed(() => graphData.value.nodes.find(node => node.id === selectedId.value))
const selectedRelations = computed(() => graphData.value.links.flatMap(link => {
  if (link.source !== selectedId.value && link.target !== selectedId.value) return []
  const neighbor = graphData.value.nodes.find(node => node.id === (link.source === selectedId.value ? link.target : link.source))
  return neighbor ? [{ ...link, neighbor }] : []
}))
const hiddenCount = computed(() => selectedNode.value ? hiddenNeighborCount(selectedNode.value, visibleNeighbors(graphData.value)) : 0)
const searchQuery = ref('')
const depth = ref(1)
const centerId = ref('')
const loading = ref(false)
const loadError = ref('')
const searchError = ref('')
const notice = ref('')
const detailsVisible = ref(false)
const zoomPercent = ref(100)
const fullscreen = ref(false)
const { isDark } = useTheme()
let graph = null
let request = null
let searchRequest = null
let resizeObserver = null
let resizeFrame = 0
let lodFrame = 0
let labelsVisible = true
let labelZoom = 1
let spotlightRevision = 0
let hoverFrame = 0
let disposed = false
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
const viewportAnimation = () => reducedMotion.matches ? false : { duration: 220 }
const errorDetail = (error, fallback) => typeof error.response?.data?.detail === 'string' ? error.response.data.detail : fallback

function colors() {
  const style = getComputedStyle(stageRef.value)
  return Object.fromEntries(['ink', 'muted', 'surface', 'line', 'blue', 'blue-soft', 'graph-policy', 'graph-org', 'graph-condition', 'graph-other', 'graph-label-bg', 'graph-edge', 'graph-badge-bg', 'graph-badge-text', 'graph-badge-border'].map(key => [key, style.getPropertyValue(`--wb-${key}`).trim()]))
}

function renderData(data, preservePositions) {
  const palette = colors()
  const neighbors = visibleNeighbors(data)
  const previous = new Map(preservePositions && graph ? graph.getNodeData().map(node => [node.id, node.style]) : [])
  const anchor = previous.get(selectedId.value) ?? { x: canvasRef.value.clientWidth / 2, y: canvasRef.value.clientHeight / 2 }
  let added = 0
  return {
    nodes: data.nodes.map(node => {
      const kind = graphKind(node.type, node.label)
      const meta = GRAPH_KINDS[kind]
      const hidden = hiddenNeighborCount(node, neighbors)
      const style = { size: graphNodeSize(node.neighbor_count), fill: palette[meta.token.slice(5)], labelText: shortGraphLabel(node.label, node.neighbor_count > 15 ? 14 : 11), labelFill: palette.ink, labelFontWeight: node.neighbor_count > 15 ? 600 : 400, labelOpacity: labelsVisible || node.neighbor_count > 15 || kind === 'policy' || kind === 'org' ? 1 : 0, badges: hidden ? [{ text: `+${hidden}`, placement: 'right-top', fill: palette['graph-badge-text'], fontSize: 10, backgroundFill: palette['graph-badge-bg'], backgroundStroke: palette['graph-badge-border'], backgroundLineWidth: 1, padding: [1, 3], backgroundRadius: 6 }] : [] }
      if (preservePositions) {
        if (previous.has(node.id)) Object.assign(style, { x: previous.get(node.id).x, y: previous.get(node.id).y })
        else {
          const angle = added * 2.399963
          const radius = 140 + 25 * Math.sqrt(added++)
          Object.assign(style, { x: anchor.x + Math.cos(angle) * radius, y: anchor.y + Math.sin(angle) * radius })
        }
      }
      return { id: node.id, data: { ...node, kind, degree: node.neighbor_count }, style }
    }),
    edges: renderEdges(data)
  }
}

function renderEdges(data) {
  return presentationEdges(data.links, focusId.value).map(edge => ({ id: edge.id, source: edge.source, target: edge.target, data: edge, style: { endArrow: edge.directed, labelText: edge.aggregated ? `×${edge.count}` : '', labelOpacity: edge.aggregated && labelsVisible ? .8 : 0 } }))
}

function syncLabels(instance = graph) {
  if (!instance || disposed || graph !== instance) return Promise.resolve()
  instance.updateNodeData(instance.getNodeData().map(node => ({ id: node.id, style: { labelOpacity: labelsVisible || node.data.degree > 15 || node.data.kind === 'policy' || node.data.kind === 'org' ? 1 : 0 } })))
  instance.updateEdgeData(instance.getEdgeData().map(edge => ({ id: edge.id, style: {
    labelText: edge.data.aggregated ? `×${edge.data.count}` : focusId.value && (edge.source === focusId.value || edge.target === focusId.value) ? shortGraphLabel(relationLabel(edge.data.keywords), 14) : '',
    labelOpacity: labelsVisible && graphData.value.nodes.length < MAX_NODES && (edge.data.aggregated || edge.source === focusId.value || edge.target === focusId.value) ? 1 : 0,
    labelBackground: graphData.value.nodes.length < MAX_NODES
  } })))
  return instance.draw()
}

function layoutForWidth(width) {
  const compact = width < 600
  return {
    type: 'd3-force', preventOverlap: true, nodeSize: 70, nodeSpacing: compact ? 18 : 24,
    manyBody: { strength: compact ? -380 : -650 }, link: { distance: compact ? 160 : 240, strength: .22 },
    x: { strength: compact ? .075 : .012 }, y: { strength: compact ? .012 : .055 }, iterations: 240, animation: false
  }
}

function createGraph() {
  const palette = colors()
  const compactCanvas = canvasRef.value.clientWidth < 600
  const instance = new Graph({
    container: canvasRef.value, width: canvasRef.value.clientWidth, height: canvasRef.value.clientHeight,
    padding: compactCanvas ? [140, 32, 210, 32] : [96, 64, 110, 64], animation: false, zoomRange: [.12, 3],
    layout: layoutForWidth(canvasRef.value.clientWidth),
    transforms: [{ type: 'process-parallel-edges', mode: 'bundle', distance: 22 }],
    behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', {
      type: 'auto-adapt-label', padding: 6,
      sortNode: (a, b) => Math.sign((b.id === focusId.value ? 100 : graphNodeSize(b.data.degree)) - (a.id === focusId.value ? 100 : graphNodeSize(a.data.degree)))
    }],
    plugins: [{
      type: 'tooltip', key: 'graph-entity-tooltip', trigger: 'hover', enterable: false,
      style: { '.tooltip': { color: palette.ink, background: palette['graph-label-bg'], border: `1px solid ${palette.line}`, borderRadius: '8px', padding: '10px 12px', fontSize: '12px' } },
      enable: event => !loading.value && (event.targetType === 'node' || event.targetType === 'edge'),
      getContent: async (event, items) => {
        const item = items[0].data
        const content = document.createElement('div')
        content.style.maxWidth = '300px'
        content.style.whiteSpace = 'pre-wrap'
        content.style.overflowWrap = 'anywhere'
        content.style.lineHeight = '1.7'
        content.textContent = event.targetType === 'node'
          ? `${item.label}\n${GRAPH_KINDS[item.kind].label} · 关联 ${item.degree} 个实体`
          : item.aggregated ? `${item.count} 条关系 · 点击展开查看` : relationLabel(item.keywords)
        return content
      }
    }],
    node: {
      type: 'circle',
      style: {
        size: datum => graphNodeSize(datum.data.degree), stroke: palette.surface, lineWidth: 2, cursor: 'pointer',
        halo: datum => datum.data.degree > 15 && graphData.value.nodes.length < MAX_NODES,
        haloStroke: datum => palette[GRAPH_KINDS[datum.data.kind].token.slice(5)], haloLineWidth: 8, haloStrokeOpacity: .15,
        labelPlacement: 'bottom', labelOffsetY: 7,
        labelFontSize: datum => (datum.data.degree > 15 ? 13.5 : 12.5) / Math.min(1, graph?.getZoom() ?? 1),
        labelLineHeight: datum => (datum.data.degree > 15 ? 19 : 17.5) / Math.min(1, graph?.getZoom() ?? 1),
        labelBackground: true, labelBackgroundFill: palette['graph-label-bg'], labelBackgroundFillOpacity: 1,
        labelBackgroundRadius: 4, labelPadding: [3, 6],
        badge: () => labelsVisible, badgeFill: palette['graph-badge-text'], badgeFontSize: 10,
        badgeBackgroundFill: palette['graph-badge-bg'], badgeBackgroundStroke: palette['graph-badge-border'], badgeBackgroundLineWidth: 1
      },
      state: {
        selected: { lineWidth: 3, stroke: palette.ink, labelOpacity: 1, halo: true, haloStrokeOpacity: .24, haloLineWidth: 12 },
        active: { opacity: 1 }, dim: { opacity: .15, labelOpacity: 0 }
      }
    },
    edge: {
      type: 'quadratic',
      style: {
        stroke: palette['graph-edge'], opacity: .28, lineWidth: 1.1, endArrowSize: 6,
        cursor: datum => datum.data.aggregated ? 'pointer' : 'default',
        labelAutoRotate: false, labelFontSize: () => 11 / Math.min(1, graph?.getZoom() ?? 1),
        labelLineHeight: () => 15.5 / Math.min(1, graph?.getZoom() ?? 1), labelFill: palette.ink,
        labelBackground: true, labelBackgroundFill: palette['graph-label-bg'], labelBackgroundStroke: palette.line,
        labelBackgroundLineWidth: 1, labelBackgroundRadius: 4, labelPadding: [2, 5]
      },
      state: { active: { stroke: palette['graph-policy'], lineWidth: 1.6, opacity: .9 }, dim: { opacity: .06, labelOpacity: 0 } }
    }
  })
  instance.on('node:click', event => { if (!loading.value && graph === instance) selectNode(event.target.id).catch(error => renderFailure(error, instance)) })
  instance.on('node:dblclick', event => { if (graph === instance) expandNode(event.target.id) })
  instance.on(NodeEvent.POINTER_ENTER, event => { if (event.pointerType !== 'touch') scheduleHover(event.target.id, instance) })
  instance.on(NodeEvent.POINTER_LEAVE, () => scheduleHover('', instance))
  instance.on('edge:click', event => {
    if (loading.value || disposed || graph !== instance) return
    const edge = instance.getEdgeData().find(item => item.id === event.target.id)
    if (edge?.data.aggregated) selectNode(edge.source, true).catch(error => renderFailure(error, instance))
  })
  instance.on('canvas:click', () => { if (graph === instance) resetSpotlight().catch(error => renderFailure(error, instance)) })
  instance.on('aftertransform', () => {
    zoomPercent.value = Math.round(instance.getZoom() * 100)
    const zoom = instance.getZoom()
    const visible = zoom >= .65
    if (visible === labelsVisible && zoom === labelZoom) return
    labelZoom = zoom
    labelsVisible = visible
    cancelAnimationFrame(lodFrame)
    lodFrame = requestAnimationFrame(() => {
      if (disposed || graph !== instance) return
      syncLabels(instance).catch(error => renderFailure(error, instance))
    })
  })
  return instance
}

function renderFailure(error, instance) {
  if (!disposed && graph === instance) { console.error('图谱绘制失败', error); loadError.value = '图谱绘制未完成，请重新读取。' }
}

async function loadSubgraph(nodeId = '', append = false, expectedRevision = '') {
  if (append && loading.value) return
  request?.abort()
  graph?.getPluginInstance('graph-entity-tooltip')?.hide()
  cancelAnimationFrame(hoverFrame)
  hoveredId.value = ''
  spotlightRevision += 1
  const controller = new AbortController()
  request = controller
  loading.value = true
  loadError.value = ''
  notice.value = ''
  let renderingInstance = null
  try {
    const overviewLimit = canvasRef.value.clientWidth < 600 ? 12 : 120
    const incoming = await graphApi.getSubgraph({ ...(nodeId ? { node_id: nodeId } : {}), depth: append ? 1 : depth.value, limit: append ? MAX_NODES : nodeId ? 120 : overviewLimit }, { signal: controller.signal })
    if (controller.signal.aborted || disposed) return
    const revisionChanged = (expectedRevision || graphData.value.revision) && (expectedRevision || graphData.value.revision) !== incoming.revision
    const preservePositions = append && !revisionChanged
    const next = preservePositions ? mergeSubgraph(graphData.value, incoming, MAX_NODES) : incoming
    graphData.value = next
    centerId.value = nodeId
    if (nodeId) detailsVisible.value = true
    if (!append) selectedId.value = ''
    if (!next.nodes.some(node => node.id === selectedId.value)) selectedId.value = ''
    if (revisionChanged) notice.value = '资料图谱已更新，已重新读取当前子图。'
    else if (next.truncated && nodeId) notice.value = `当前显示部分关系，可搜索实体继续核对。最多保留 ${MAX_NODES} 个实体。`
    if (!next.nodes.length) { if (graph) { graph.setData({ nodes: [], edges: [] }); await graph.draw() } return }
    await nextTick()
    if (controller.signal.aborted || disposed) return
    if (!graph) graph = createGraph()
    const instance = graph
    renderingInstance = instance
    const [width, height] = instance.getSize()
    if (width !== canvasRef.value.clientWidth || height !== canvasRef.value.clientHeight) instance.setSize(canvasRef.value.clientWidth, canvasRef.value.clientHeight)
    instance.setData(renderData(next, preservePositions))
    if (preservePositions) await instance.draw()
    else {
      instance.setLayout(layoutForWidth(canvasRef.value.clientWidth))
      await instance.render()
      if (controller.signal.aborted || disposed || graph !== instance) return
      await instance.fitView({ when: 'always' }, false)
    }
    if (controller.signal.aborted || disposed) return
    if (nodeId) await selectNode(nodeId, false, controller)
    else await resetSpotlight()
    if (controller.signal.aborted || disposed || graph !== instance) return
    zoomPercent.value = Math.round(instance.getZoom() * 100)
  } catch (error) {
    if (!controller.signal.aborted && !disposed && (renderingInstance === null || graph === renderingInstance)) loadError.value = errorDetail(error, '图谱读取未完成，请检查连接后重试。')
  } finally {
    if (request === controller) { loading.value = false; request = null }
  }
}

function loadOverview() { searchQuery.value = ''; return loadSubgraph() }
function changeDepth() { const id = selectedId.value || centerId.value; if (id) loadSubgraph(id); else notice.value = '选择实体后，按此层级读取关联子图。' }
function expandNode(id) { if (loading.value) return; if (graphData.value.nodes.length >= MAX_NODES) { notice.value = '已达到当前画布上限，请通过搜索切换到新的子图。'; return } return loadSubgraph(id, true) }

async function searchEntities(query, callback) {
  searchRequest?.abort()
  searchError.value = ''
  if (!query.trim()) { callback([]); return }
  const controller = new AbortController()
  searchRequest = controller
  try {
    const result = await graphApi.searchEntities(query.trim(), { signal: controller.signal })
    if (!controller.signal.aborted && !disposed) callback(result.nodes.map(node => ({ ...node, value: node.label, revision: result.revision })))
  } catch (error) {
    if (!controller.signal.aborted && !disposed) { searchError.value = errorDetail(error, '实体搜索暂不可用，请稍后重试。'); callback([]) }
  }
}
function selectSearchResult(item) { return loadSubgraph(item.id, false, item.revision) }

function scheduleHover(id, instance) {
  if (!id && graph === instance) instance.getPluginInstance('graph-entity-tooltip')?.hide()
  if (loading.value || selectedId.value || disposed || graph !== instance) return
  cancelAnimationFrame(hoverFrame)
  hoverFrame = requestAnimationFrame(() => {
    if (loading.value || selectedId.value || disposed || graph !== instance || hoveredId.value === id) return
    hoveredId.value = id
    applySpotlight(instance).catch(error => renderFailure(error, instance))
  })
}

async function applySpotlight(instance = graph) {
  if (!instance || disposed || graph !== instance) return
  const revision = ++spotlightRevision
  const id = focusId.value
  instance.setData({ nodes: instance.getNodeData(), edges: renderEdges(graphData.value) })
  await instance.draw()
  if (disposed || graph !== instance || revision !== spotlightRevision || focusId.value !== id) return
  const neighbors = visibleNeighbors(graphData.value).get(id) ?? new Set()
  const states = Object.fromEntries([
    ...graphData.value.nodes.map(node => [node.id, id ? [node.id === id ? 'selected' : neighbors.has(node.id) ? 'active' : 'dim'] : []]),
    ...instance.getEdgeData().map(edge => [edge.id, id ? [edge.source === id || edge.target === id ? 'active' : 'dim'] : []])
  ])
  await instance.setElementState(states, false)
  if (!disposed && graph === instance && revision === spotlightRevision) await syncLabels(instance)
}

async function selectNode(id, center = false, controller = null) {
  if (!graph || !graphData.value.nodes.some(node => node.id === id)) return
  const instance = graph
  center = center || !detailsVisible.value
  instance.getPluginInstance('graph-entity-tooltip')?.hide()
  selectedId.value = id
  hoveredId.value = ''
  cancelAnimationFrame(hoverFrame)
  detailsVisible.value = true
  await nextTick()
  if (disposed || graph !== instance || controller?.signal.aborted) return
  await applySpotlight(instance)
  if (disposed || graph !== instance || controller?.signal.aborted) return
  if (center && !disposed && graph === instance && selectedId.value === id && !controller?.signal.aborted) {
    if (instance.getZoom() < .85) await instance.zoomTo(.85, false)
    if (!disposed && graph === instance && selectedId.value === id && !controller?.signal.aborted) await instance.focusElement(id, viewportAnimation())
  }
}
async function resetSpotlight() {
  graph?.getPluginInstance('graph-entity-tooltip')?.hide()
  selectedId.value = ''
  hoveredId.value = ''
  cancelAnimationFrame(hoverFrame)
  await applySpotlight()
}
async function zoomBy(ratio) { if (graph) await graph.zoomBy(ratio, viewportAnimation()) }
async function fitView() { if (graph) await graph.fitView({ when: 'always' }, viewportAnimation()) }
async function toggleFullscreen() {
  try { if (document.fullscreenElement === stageRef.value) await document.exitFullscreen(); else await stageRef.value.requestFullscreen() }
  catch { notice.value = '当前浏览器不支持进入全屏，可收起导航扩大画布。' }
}
function fullscreenChanged() { fullscreen.value = document.fullscreenElement === stageRef.value }

watch(isDark, async () => {
  if (!graph) return
  await nextTick()
  if (disposed || !graph) return
  cancelAnimationFrame(hoverFrame)
  hoveredId.value = ''
  spotlightRevision += 1
  const data = renderData(graphData.value, true)
  const zoom = graph.getZoom()
  const [width, height] = graph.getSize()
  const center = graph.getCanvasByViewport([width / 2, height / 2])
  graph.destroy()
  graph = null
  labelsVisible = zoom >= .65
  labelZoom = zoom
  graph = createGraph()
  graph.setData(data)
  const instance = graph
  try {
    await instance.draw()
    if (disposed || graph !== instance) return
    await instance.zoomTo(zoom, false)
    if (disposed || graph !== instance) return
    const position = instance.getViewportByCanvas(center)
    const [nextWidth, nextHeight] = instance.getSize()
    await instance.translateBy([nextWidth / 2 - position[0], nextHeight / 2 - position[1]], false)
    if (!disposed && graph === instance) await applySpotlight(instance)
  } catch (error) { renderFailure(error, instance) }
})
onMounted(() => {
  resizeObserver = new ResizeObserver(() => {
    cancelAnimationFrame(resizeFrame)
    resizeFrame = requestAnimationFrame(() => {
      if (graph && canvasRef.value?.clientWidth && canvasRef.value?.clientHeight) {
        const instance = graph
        const width = canvasRef.value.clientWidth
        const height = canvasRef.value.clientHeight
        const [previousWidth, previousHeight] = instance.getSize()
        if (width === previousWidth && height === previousHeight) return
        if (loading.value) { instance.setSize(width, height); return }
        const center = instance.getCanvasByViewport([previousWidth / 2, previousHeight / 2])
        instance.setSize(width, height)
        const position = instance.getViewportByCanvas(center)
        instance.translateBy([width / 2 - position[0], height / 2 - position[1]], false).catch(error => renderFailure(error, instance))
      }
    })
  })
  resizeObserver.observe(canvasRef.value)
  document.addEventListener('fullscreenchange', fullscreenChanged)
  loadOverview()
})
onBeforeUnmount(() => {
  disposed = true
  request?.abort(); searchRequest?.abort()
  resizeObserver?.disconnect()
  cancelAnimationFrame(resizeFrame); cancelAnimationFrame(lodFrame); cancelAnimationFrame(hoverFrame)
  document.removeEventListener('fullscreenchange', fullscreenChanged)
  if (document.fullscreenElement === stageRef.value) document.exitFullscreen().catch(() => {})
  graph?.destroy(); graph = null
})
</script>

<style scoped>
.graph-page { display: grid; grid-template-columns: minmax(0, 1fr); min-width: 0; min-height: 0; height: 100%; overflow: hidden; background: var(--wb-surface); }
.graph-page.has-inspector { grid-template-columns: minmax(0, 1fr) 320px; }
.graph-page:fullscreen { width: 100vw; height: 100dvh; }
.graph-stage { min-width: 0; min-height: 0; position: relative; overflow: hidden; background-color: var(--wb-canvas); background-image: radial-gradient(color-mix(in srgb, var(--wb-border) 55%, transparent) .7px, transparent .8px); background-size: 24px 24px; }
.graph-canvas { width: 100%; height: 100%; min-height: 0; touch-action: none; }
.graph-hud { position: absolute; z-index: 2; display: flex; align-items: center; gap: 12px; border: 1px solid var(--wb-line); border-radius: 10px; background: color-mix(in srgb, var(--wb-surface) 94%, transparent); backdrop-filter: blur(8px); box-shadow: 0 4px 14px color-mix(in srgb, var(--wb-ink) 5%, transparent); color: var(--wb-muted); font-size: 12px; }
.graph-search-hud { top: 16px; left: 16px; right: 16px; max-width: 760px; padding: 10px; flex-wrap: wrap; gap: 10px; }
.graph-search-hud :deep(.el-autocomplete.graph-search) { width: 280px; flex: 1 1 240px; min-width: 180px; }
.graph-search :deep(.el-input__wrapper) { min-height: 36px; }
.graph-hops { display: flex; align-items: center; gap: 10px; }
.graph-hops :deep(.el-radio-button__inner) { padding: 8px 10px; box-shadow: none; }
.graph-search-hud .graph-hops :deep(.el-radio-button.is-active .el-radio-button__inner) { background: color-mix(in srgb, var(--wb-graph-policy) 18%, var(--wb-surface)); color: var(--wb-graph-policy); border-color: var(--wb-graph-policy); box-shadow: -1px 0 0 0 var(--wb-graph-policy); }
.graph-status-pill { display: inline-flex; align-items: center; gap: 5px; padding: 4px 8px; color: var(--wb-muted); background: var(--wb-tint); border-radius: 14px; white-space: nowrap; }
.graph-status-pill::before { content: ''; width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.graph-suggestion { display: flex; justify-content: space-between; gap: 12px; max-width: 350px; }
.graph-suggestion > span { overflow: hidden; text-overflow: ellipsis; }
.graph-suggestion small { color: var(--wb-muted); }
.graph-search-error { position: absolute; top: 82px; left: 16px; z-index: 3; max-width: calc(100% - 32px); margin: 0; padding: 8px 12px; background: var(--wb-error-soft); color: var(--wb-error); border: 1px solid var(--wb-error-border); font-size: 12px; border-radius: 7px; }
.graph-state { position: absolute; inset: 110px 16px 124px; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 12px; text-align: center; font-size: 14px; color: var(--wb-muted); }
.graph-state > .el-icon { font-size: 28px; color: var(--wb-blue); }
.graph-state strong { font-size: 16px; color: var(--wb-ink); font-weight: 500; }
.graph-state p { margin: 0; max-width: 340px; line-height: 1.8; font-size: 13px; }
.graph-summary-hud { left: 16px; bottom: 16px; max-width: calc(100% - 336px); padding: 9px 14px; flex-wrap: wrap; gap: 10px 14px; }
.graph-scope-hud { display: flex; align-items: center; padding-right: 12px; flex-wrap: wrap; gap: 8px; border-right: 1px solid var(--wb-line); }
.graph-scope-hud strong { color: var(--wb-ink); font-weight: 600; }
.graph-total-count { font-size: 12px; }
.graph-scope-hud button { padding: 0; border: 0; background: none; color: var(--wb-blue); font: inherit; cursor: pointer; }
.graph-zoom-hint { flex-basis: 100%; font-size: 12px; }
.graph-legend { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.graph-legend > span { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.graph-legend i, .entity-type i { display: inline-block; flex: none; width: 8px; height: 8px; border-radius: 50%; }
.graph-legend .legend-edge { height: 1px; width: 16px; border-radius: 0; background: var(--wb-muted); }
.graph-view-tools { right: 16px; bottom: 16px; padding: 4px; gap: 2px; }
.graph-view-tools button, .graph-inspector > header button, .graph-notice button { display: inline-grid; place-items: center; flex: none; width: 32px; height: 32px; border: 0; border-radius: 6px; background: transparent; color: var(--wb-secondary); cursor: pointer; font-size: 16px; }
.graph-view-tools button:hover, .graph-inspector > header button:hover { background: var(--wb-tint); color: var(--wb-blue); }
.graph-view-tools button:disabled { color: var(--wb-border); cursor: default; }
.graph-view-tools output { min-width: 36px; text-align: center; font: 12px var(--wb-number); }
.graph-notice { position: absolute; top: 86px; left: 16px; right: 16px; z-index: 2; display: flex; align-items: center; gap: 10px; max-width: 760px; padding: 8px 12px; color: var(--wb-warning); background: var(--wb-warning-soft); border: 1px solid var(--wb-warning-border); border-radius: 7px; font-size: 12px; line-height: 1.6; }
.graph-notice button { width: 24px; height: 24px; margin-left: auto; color: inherit; }
.graph-inspector { display: flex; flex-direction: column; min-height: 0; min-width: 0; overflow-y: auto; border-left: 1px solid var(--wb-line); background: var(--wb-surface); }
.graph-inspector > header { position: sticky; top: 0; z-index: 1; display: flex; align-items: center; justify-content: space-between; min-height: 56px; padding: 10px 18px; border-bottom: 1px solid var(--wb-line); background: var(--wb-surface); }
.graph-inspector > header h2 { margin: 0; font-size: 15px; font-weight: 600; }
.inspector-empty { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; gap: 14px; padding: 32px 24px; min-height: 220px; color: var(--wb-muted); text-align: center; }
.inspector-empty .el-icon { font-size: 28px; color: var(--wb-blue); }
.inspector-empty h2 { margin: 0; font-size: 15px; color: var(--wb-ink); font-weight: 500; }
.inspector-empty p { margin: 0; font-size: 13px; line-height: 1.8; }
.entity-content { padding: 22px 20px; }
.entity-type { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--wb-muted); }
.entity-content h2 { margin: 12px 0; font-size: 18px; font-weight: 600; line-height: 1.6; overflow-wrap: anywhere; }
.entity-description, .entity-source { margin: 0; font-size: 13px; line-height: 1.9; white-space: pre-wrap; overflow-wrap: anywhere; }
.entity-content section { margin: 24px 0; padding-top: 18px; border-top: 1px solid var(--wb-line); }
.entity-content h3 { margin: 0 0 10px; font-size: 13px; font-weight: 600; }
.entity-content h3 span { margin-left: 6px; color: var(--wb-muted); font-variant-numeric: tabular-nums; }
.entity-source { color: var(--wb-muted); font-family: var(--font-mono); }
.entity-source-details summary { color: var(--wb-muted); cursor: pointer; font-size: 12px; }
.entity-source-details p { max-height: 160px; overflow: auto; margin-top: 10px; }
.entity-help { margin: 10px 0 0; font-size: 12px; color: var(--wb-muted); line-height: 1.8; }
.entity-relations { list-style: none; padding: 0; margin: 0; }
.entity-relations li { display: grid; gap: 5px; padding: 12px 0; border-bottom: 1px solid var(--wb-line); }
.entity-relations li > span { font-size: 12px; color: var(--wb-muted); overflow-wrap: anywhere; }
.entity-relations button { padding: 0; border: 0; color: var(--wb-blue); background: none; font: 13px/1.8 var(--wb-font); text-align: left; cursor: pointer; }
.entity-relations small, .entity-relations details { font-size: 12px; color: var(--wb-muted); }
.entity-relations details p { margin-top: 8px; line-height: 1.8; }
.entity-raw-relation { overflow-wrap: anywhere; white-space: pre-wrap; font-family: var(--font-mono); }
.graph-entity-list { padding: 16px 20px; border-top: 1px solid var(--wb-line); font-size: 12px; color: var(--wb-muted); }
.graph-entity-list summary { cursor: pointer; }
.graph-entity-list > button { display: grid; gap: 4px; width: 100%; margin-top: 12px; padding: 8px; border: 0; border-radius: 5px; text-align: left; color: var(--wb-ink); background: var(--wb-tint); font: 13px/1.5 var(--wb-font); cursor: pointer; }
.graph-entity-list button span { color: var(--wb-muted); font-size: 11px; }
.graph-page button:focus-visible, .graph-page summary:focus-visible { outline: 2px solid var(--wb-blue); outline-offset: 2px; }
@media (max-width: 1199px) { .graph-summary-hud { bottom: 68px; max-width: calc(100% - 32px); } .graph-status-pill { display: none; } }
@media (max-width: 899px) {
  .graph-page.has-inspector { grid-template-columns: minmax(0, 1fr); }
  .graph-inspector { position: absolute; right: 0; top: 0; bottom: 0; z-index: 5; width: min(320px, 90%); box-shadow: -6px 0 24px color-mix(in srgb, var(--wb-ink) 10%, transparent); }
  .graph-page { position: relative; }
}
@media (max-width: 599px) {
  .graph-search-hud { top: 12px; left: 12px; right: 12px; padding: 9px; }
  .graph-search-hud :deep(.el-autocomplete.graph-search) { width: 100%; flex-basis: 100%; }
  .graph-search :deep(input) { font-size: 16px; }
  .graph-hops { width: 100%; justify-content: space-between; }
  .graph-summary-hud { left: 12px; bottom: 68px; right: 12px; max-width: none; padding: 10px 12px; gap: 10px; font-size: 12px; }
  .graph-scope-hud { width: 100%; border: 0; border-bottom: 1px solid var(--wb-line); padding: 0 0 8px; gap: 7px; }
  .graph-legend { gap: 7px 10px; }
  .graph-view-tools { bottom: 12px; left: 12px; right: auto; padding: 3px; }
  .graph-view-tools button { width: 36px; height: 36px; }
  .graph-state { inset: 136px 12px 180px; }
  .graph-search-error, .graph-notice { top: 124px; left: 12px; right: 12px; }
}
@media (prefers-reduced-motion: reduce) { .is-loading { animation: none; } }
</style>
