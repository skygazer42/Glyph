<template>
  <section class="workspace-module graph-page" aria-label="政策实体关系图谱">
    <div class="graph-toolbar">
      <div class="graph-query">
        <label class="graph-field-label" for="graph-entity-search">查找实体</label>
        <el-select
          id="graph-entity-search"
          v-model="searchTargetId"
          placeholder="输入政策、机构或事项名称"
          aria-label="搜索图谱实体"
          filterable
          clearable
          remote
          :disabled="loading || !!loadError || !allOptions.length"
          :remote-method="filterMethod"
          @change="handleSearch"
          class="search-select"
          no-match-text="未找到匹配实体"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
          <el-option
            v-for="item in filteredOptions"
            :key="item.id"
            :label="item.name"
            :value="item.id"
          >
            <span class="graph-option-name">{{ item.name }}</span>
            <span class="graph-option-category">{{ item.categoryName }}</span>
          </el-option>
        </el-select>
        <div class="graph-hop-field">
          <label for="graph-hop-count">关联层级</label>
          <el-input-number
            id="graph-hop-count"
            v-model="hopCount"
            aria-label="关联层级"
            :min="1"
            :max="5"
            :disabled="loading || !!loadError || !allOptions.length"
            controls-position="right"
            class="hop-input"
            @change="handleHopChange"
          />
        </div>
      </div>
      <el-tooltip content="重新加载图谱数据" placement="bottom">
        <el-button :icon="Refresh" :loading="loading" aria-label="重新加载图谱数据" @click="loadFromApi">刷新</el-button>
      </el-tooltip>
    </div>

    <div class="graph-canvas-panel" :aria-busy="loading">
      <div class="graph-context">
        <div class="graph-scope">
          <span class="graph-scope-indicator" aria-hidden="true"></span>
          <strong>{{ isFiltered ? searchTargetName : '全部实体关系' }}</strong>
          <span v-if="isFiltered" class="graph-scope-note">{{ hopCount }} 层关联</span>
          <el-button v-if="isFiltered" link type="primary" :disabled="loading || !!loadError" @click="resetToFullGraph">查看全图</el-button>
        </div>
        <dl class="graph-stats" aria-label="当前图谱数量">
          <div><dt>实体</dt><dd>{{ loading || loadError ? '—' : stats.nodes }}</dd></div>
          <div><dt>关系</dt><dd>{{ loading || loadError ? '—' : stats.links }}</dd></div>
          <div><dt>分类</dt><dd>{{ loading || loadError ? '—' : stats.categories }}</dd></div>
        </dl>
      </div>

      <div class="chart-container">
        <div
          ref="chartRef"
          class="chart-dom"
          :class="{ 'is-unavailable': loading || loadError || !stats.nodes }"
          role="img"
          :aria-label="statsText"
          :aria-hidden="loading || !!loadError || !stats.nodes"
        ></div>
        <div v-if="loading" class="graph-state" role="status" aria-live="polite">
          <span class="graph-state-icon is-loading" aria-hidden="true"><el-icon><Loading /></el-icon></span>
          <strong>正在加载图谱</strong>
          <p>正在读取实体与关联关系，请稍候。</p>
        </div>
        <div v-else-if="loadError" class="graph-state" role="alert">
          <span class="graph-state-icon is-error" aria-hidden="true"><el-icon><Warning /></el-icon></span>
          <strong>图谱暂时无法加载</strong>
          <p>{{ loadError }}</p>
          <el-button type="primary" plain :icon="Refresh" @click="loadFromApi">重新加载</el-button>
        </div>
        <div v-else-if="!stats.nodes" class="graph-state" role="status">
          <span class="graph-state-icon" aria-hidden="true"><el-icon><Connection /></el-icon></span>
          <strong>暂无可展示的实体关系</strong>
          <p>当前知识资料尚未形成图谱。资料更新后，可刷新查看。</p>
          <el-button :icon="Refresh" @click="loadFromApi">刷新图谱</el-button>
        </div>
        <div v-else class="graph-view-tools" aria-label="图谱视图工具">
          <el-tooltip content="放大图谱" placement="left">
            <button type="button" aria-label="放大图谱" @click="zoomGraph(1.2)"><el-icon><ZoomIn /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="缩小图谱" placement="left">
            <button type="button" aria-label="缩小图谱" @click="zoomGraph(0.8)"><el-icon><ZoomOut /></el-icon></button>
          </el-tooltip>
          <el-tooltip content="复位视图" placement="left">
            <button type="button" aria-label="复位图谱视图" @click="resetZoom"><el-icon><FullScreen /></el-icon></button>
          </el-tooltip>
        </div>
      </div>
      <div class="graph-footer">
        <span>搜索实体以聚焦关联关系</span>
        <span class="graph-gesture-hint">拖动平移 · 滚轮缩放 · 悬停查看详情</span>
        <span class="graph-touch-hint">拖动查看 · 双指缩放</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, shallowRef, watch } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { Connection, FullScreen, Loading, Refresh, Search, Warning, ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import { getGraphData } from '@/api'
import { useTheme } from '@/composables/useTheme'

const chartRef = ref(null)
const chartInstance = shallowRef(null)
const loading = ref(false)
const loadError = ref('')
const hopCount = ref(3)
const { isDark } = useTheme()

// 全量数据与邻接表；筛选只改变画布，不修改接口返回的数据。
const fullGraphData = { nodes: [], links: [], categories: [] }
const adjacencyMap = new Map()
const allOptions = ref([])
const filteredOptions = ref([])
const stats = ref({ nodes: 0, links: 0, categories: 0 })
const isFiltered = ref(false)
const searchTargetId = ref('')
const searchTargetName = ref('')

const statsText = computed(() => {
  const { nodes, links, categories } = stats.value
  return `政策知识图谱，包含 ${nodes} 个实体、${links} 条关系、${categories} 个分类。搜索实体可查看关联关系。`
})

const normalizeApiData = (response) => {
  const graphData = response?.data || response || {}
  if (!Array.isArray(graphData.nodes) || !Array.isArray(graphData.links)) {
    throw new Error('图谱返回的数据不完整，请稍后重试。')
  }
  const categoryMap = new Map()
  let categoryIndex = 0
  const nodes = graphData.nodes.map((node, nodeIndex) => {
    const id = String(node.id ?? nodeIndex)
    const name = String(node.label ?? node.name ?? node.title ?? id)
    const typeName = String(node.type || node.entity_type || '其他实体')
    if (!categoryMap.has(typeName)) categoryMap.set(typeName, categoryIndex++)
    return {
      ...node,
      id,
      name,
      category: categoryMap.get(typeName),
      symbolSize: name.length > 5 ? 24 : 28,
      label: { show: name.length < 12 },
    }
  })
  const categories = Array.from(categoryMap.keys()).map((name) => ({ name }))
  const links = graphData.links.map((link, linkIndex) => ({
    ...link,
    source: String(link.source ?? link.src ?? linkIndex),
    target: String(link.target ?? link.dst ?? linkIndex),
  }))
  return { nodes, links, categories }
}

const buildAdjacencyMap = (links) => {
  adjacencyMap.clear()
  links.forEach(({ source, target }) => {
    const sourceId = String(source)
    const targetId = String(target)
    if (!adjacencyMap.has(sourceId)) adjacencyMap.set(sourceId, new Set())
    if (!adjacencyMap.has(targetId)) adjacencyMap.set(targetId, new Set())
    adjacencyMap.get(sourceId).add(targetId)
    adjacencyMap.get(targetId).add(sourceId)
  })
}

// 当前图谱按无向关系查询邻域；孤立的起点仍属于结果。
const getSubGraph = (startId, hops = 3) => {
  if (!fullGraphData.nodes.some((node) => node.id === startId)) return { nodes: [], links: [] }
  const visited = new Set([startId])
  let layer = [startId]
  for (let hopIndex = 0; hopIndex < hops; hopIndex++) {
    const nextLayer = []
    layer.forEach((nodeId) => {
      adjacencyMap.get(nodeId)?.forEach((neighborId) => {
        if (!visited.has(neighborId)) {
          visited.add(neighborId)
          nextLayer.push(neighborId)
        }
      })
    })
    if (nextLayer.length === 0) break
    layer = nextLayer
  }
  const nodes = fullGraphData.nodes.filter((node) => visited.has(node.id))
  const links = fullGraphData.links.filter((link) => visited.has(String(link.source)) && visited.has(String(link.target)))
  return { nodes, links }
}

const readChartColors = () => {
  const styles = getComputedStyle(chartRef.value)
  return {
    ink: styles.getPropertyValue('--wb-ink').trim(),
    muted: styles.getPropertyValue('--wb-muted').trim(),
    line: styles.getPropertyValue('--wb-line').trim(),
    surface: styles.getPropertyValue('--wb-surface').trim(),
    blue: styles.getPropertyValue('--wb-blue').trim(),
    font: styles.getPropertyValue('--wb-font').trim(),
    palette: isDark.value
      ? ['#9bbde5', '#80bbb3', '#a8a1ce', '#c7ad79', '#ba94a5', '#9cabbb']
      : ['#35689e', '#49877e', '#7a70a1', '#9a793e', '#9c697f', '#687e95'],
  }
}

const fitGraphToViewport = () => {
  const chart = chartInstance.value
  if (!chart || chart.isDisposed()) return
  const data = chart.getModel()?.getSeriesByIndex(0)?.getData()
  if (!data?.count()) return
  // 图例与操作工具拥有自己的安全区，不能只按节点中心计算可见范围。
  const plot = { left: 24, top: 64, right: chart.getWidth() - 64, bottom: chart.getHeight() - 24 }
  if (plot.right <= plot.left || plot.bottom <= plot.top) return
  for (let attempt = 0; attempt < 4; attempt++) {
    chart.getZr().flush()
    const bounds = { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity }
    const includeElement = (element) => {
      if (!element || element.ignore || element.invisible) return
      const rect = element.getBoundingRect().clone()
      const transform = element.getComputedTransform()
      if (transform) rect.applyTransform(transform)
      bounds.left = Math.min(bounds.left, rect.x)
      bounds.top = Math.min(bounds.top, rect.y)
      bounds.right = Math.max(bounds.right, rect.x + rect.width)
      bounds.bottom = Math.max(bounds.bottom, rect.y + rect.height)
    }
    data.eachItemGraphicEl((symbol) => {
      includeElement(symbol)
      symbol.traverse((element) => includeElement(element.getTextContent?.()))
    })
    if (!Number.isFinite(bounds.left + bounds.top + bounds.right + bounds.bottom)) return
    const centerX = (bounds.left + bounds.right) / 2
    const centerY = (bounds.top + bounds.bottom) / 2
    const ratio = Math.min(1, (plot.right - plot.left) / Math.max(bounds.right - bounds.left, 1), (plot.bottom - plot.top) / Math.max(bounds.bottom - bounds.top, 1))
    chart.dispatchAction({ type: 'graphRoam', zoom: ratio, originX: centerX, originY: centerY })
    chart.dispatchAction({ type: 'graphRoam', dx: (plot.left + plot.right) / 2 - centerX, dy: (plot.top + plot.bottom) / 2 - centerY })
    if (ratio > 0.999) break
  }
}

const renderChart = (nodes, links, categories) => {
  if (!chartInstance.value) initChart()
  if (!chartInstance.value) return
  const visibleCategoryIds = new Set(nodes.map((node) => node.category))
  stats.value = { nodes: nodes.length, links: links.length, categories: visibleCategoryIds.size }
  const colors = readChartColors()
  const option = {
    color: colors.palette,
    textStyle: { fontFamily: colors.font },
    // 先收敛再展示，避免动画中的零尺寸符号干扰边界测量。
    animation: false,
    tooltip: {
      trigger: 'item',
      confine: true,
      backgroundColor: colors.surface,
      borderColor: colors.line,
      textStyle: { color: colors.ink, fontSize: 13, fontFamily: colors.font },
      extraCssText: 'max-width: min(340px, 80vw); white-space: normal; overflow-wrap: anywhere; box-shadow: 0 4px 18px rgba(24, 43, 66, 0.08);',
      formatter: (params) => {
        const { data: graphItem, dataType, name } = params
        if (dataType === 'node') {
          const categoryName = categories[graphItem.category]?.name || '其他实体'
          let html = `<div style="font-weight:600; margin-bottom:6px">${echarts.format.encodeHTML(name)}</div><div>${echarts.format.encodeHTML(categoryName)}</div>`
          const description = graphItem.description || graphItem.desc
          if (description) html += `<div style="margin-top:8px;line-height:1.7">${echarts.format.encodeHTML(String(description))}</div>`
          return html
        }
        if (dataType === 'edge') {
          const relation = graphItem.relation || graphItem.label || graphItem.keywords || '关联'
          const sourceName = fullGraphData.nodes.find((node) => node.id === String(graphItem.source))?.name || graphItem.source
          const targetName = fullGraphData.nodes.find((node) => node.id === String(graphItem.target))?.name || graphItem.target
          const description = graphItem.description ? `<div style="margin-top:8px;line-height:1.7">${echarts.format.encodeHTML(String(graphItem.description))}</div>` : ''
          return `${echarts.format.encodeHTML(String(sourceName))} → ${echarts.format.encodeHTML(String(targetName))}<br>${echarts.format.encodeHTML(String(relation))}${description}`
        }
        return echarts.format.encodeHTML(name)
      },
    },
    legend: {
      data: categories.filter((category, index) => visibleCategoryIds.has(index)).map((category) => category.name),
      top: 18,
      left: 20,
      right: 20,
      type: 'scroll',
      orient: 'horizontal',
      itemWidth: 9,
      itemHeight: 9,
      icon: 'circle',
      itemGap: 20,
      textStyle: { color: colors.muted, fontSize: 12 },
      pageTextStyle: { color: colors.muted },
      pageIconColor: colors.blue,
      pageIconInactiveColor: colors.line,
    },
    series: [{
      type: 'graph',
      layout: 'force',
      top: 64,
      bottom: 36,
      left: 44,
      right: 64,
      preserveAspect: 'contain',
      // 力布局使用自己的初始坐标，接口附带的旧坐标不决定画布缩放。
      data: nodes.map((node) => ({ ...node, x: undefined, y: undefined })),
      links,
      categories,
      roam: true,
      draggable: true,
      scaleLimit: { min: 0.02, max: 5 },
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [4, 6],
      itemStyle: { borderColor: colors.surface, borderWidth: 2 },
      labelLayout: { hideOverlap: true },
      label: {
        position: 'right',
        formatter: '{b}',
        color: colors.ink,
        fontSize: 13,
        fontFamily: colors.font,
        textBorderColor: colors.surface,
        textBorderWidth: 3,
        show: true,
      },
      blur: { itemStyle: { opacity: 0.4 }, lineStyle: { opacity: 0.1 }, label: { show: true, color: colors.muted } },
      lineStyle: { color: 'source', curveness: 0.12, opacity: 0.3, width: 1.2 },
      emphasis: {
        focus: 'adjacency',
        scale: false,
        itemStyle: { borderColor: colors.blue, borderWidth: 2, opacity: 1 },
        lineStyle: { width: 2, opacity: 0.8 },
        label: { show: true, color: colors.ink, fontWeight: 600 },
      },
      force: { initLayout: 'circular', repulsion: 420, edgeLength: [90, 150], gravity: 0.1, friction: 0.6, layoutAnimation: false },
    }],
  }
  chartInstance.value.setOption(option, { notMerge: true })
  fitGraphToViewport()
}

const filterMethod = (query) => {
  filteredOptions.value = allOptions.value.filter((item) => item.name.toLowerCase().includes(query.toLowerCase())).slice(0, 50)
}

const handleSearch = (nodeId) => {
  if (!nodeId) {
    resetToFullGraph()
    return
  }
  const target = fullGraphData.nodes.find((node) => node.id === nodeId)
  if (!target) return
  searchTargetName.value = target.name
  isFiltered.value = true
  const { nodes, links } = getSubGraph(nodeId, hopCount.value ?? 3)
  renderChart(nodes, links, fullGraphData.categories)
  ElMessage.success(`已展示 ${hopCount.value} 层关联：${nodes.length} 个实体、${links.length} 条关系`)
}

const handleHopChange = () => {
  if (searchTargetId.value) handleSearch(searchTargetId.value)
}

const resetToFullGraph = () => {
  isFiltered.value = false
  searchTargetId.value = ''
  searchTargetName.value = ''
  filteredOptions.value = allOptions.value.slice(0, 50)
  renderChart(fullGraphData.nodes, fullGraphData.links, fullGraphData.categories)
}

let graphRequest = null
const loadFromApi = async () => {
  const request = {}
  graphRequest = request
  loading.value = true
  loadError.value = ''
  try {
    const response = await getGraphData()
    if (graphRequest !== request) return
    const { nodes, links, categories } = normalizeApiData(response)
    fullGraphData.nodes = nodes
    fullGraphData.links = links
    fullGraphData.categories = categories
    buildAdjacencyMap(links)
    allOptions.value = nodes.map(({ id, name, category }) => ({ id, name, categoryName: categories[category]?.name || '' }))
    filteredOptions.value = allOptions.value.slice(0, 50)
    resetToFullGraph()
  } catch (error) {
    if (graphRequest !== request) return
    console.error(error)
    loadError.value = '无法取得图谱数据，请检查服务连接后重试。'
  } finally {
    if (graphRequest === request) loading.value = false
  }
}

const initChart = () => {
  if (chartRef.value) {
    chartInstance.value = echarts.init(chartRef.value)
    chartInstance.value.on('legendselectchanged', fitGraphToViewport)
  }
}
const zoomGraph = (factor) => {
  const chart = chartInstance.value
  chart?.dispatchAction({ type: 'graphRoam', zoom: factor, originX: chart.getWidth() / 2, originY: chart.getHeight() / 2 })
}
const resetZoom = () => {
  chartInstance.value?.dispatchAction({ type: 'restore' })
  fitGraphToViewport()
}
const refreshAppearance = () => {
  if (!chartInstance.value || loadError.value || loading.value) return
  const graph = isFiltered.value ? getSubGraph(searchTargetId.value, hopCount.value ?? 3) : fullGraphData
  renderChart(graph.nodes, graph.links, fullGraphData.categories)
}
watch(isDark, refreshAppearance, { flush: 'post' })
let resizeObserver = null
onMounted(() => {
  initChart()
  loadFromApi()
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => {
      chartInstance.value?.resize()
      fitGraphToViewport()
    })
    resizeObserver.observe(chartRef.value)
  }
})
onBeforeUnmount(() => {
  graphRequest = null
  chartInstance.value?.dispose()
  chartInstance.value = null
  resizeObserver?.disconnect()
})
</script>

<style scoped>
.graph-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
}
.graph-toolbar,
.graph-query,
.graph-hop-field {
  display: flex;
  align-items: center;
  gap: 12px;
}
.graph-toolbar {
  justify-content: space-between;
}
.graph-query {
  min-width: 0;
  flex: 1;
}
.graph-field-label,
.graph-hop-field label {
  flex-shrink: 0;
  font-size: 13px;
  color: var(--wb-muted);
}
.search-select {
  width: min(360px, 40vw);
}
.search-select :deep(.el-select__wrapper.is-disabled .el-select__placeholder) {
  color: var(--wb-muted);
}
.graph-hop-field {
  gap: 10px;
  margin-left: 8px;
}
.hop-input {
  width: 88px;
}
.graph-option-name {
  display: inline-block;
  max-width: 75%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: bottom;
}
.graph-option-category {
  float: right;
  font-size: 12px;
  color: var(--wb-muted);
}
.graph-canvas-panel {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  background: var(--wb-surface);
  border: 1px solid var(--wb-line);
  border-radius: var(--wb-radius);
}
.graph-context {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 64px;
  padding: 12px 22px;
  border-bottom: 1px solid var(--wb-line);
}
.graph-scope {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  min-width: 0;
  font-size: 14px;
}
.graph-scope strong {
  font-weight: 500;
  overflow-wrap: anywhere;
}
.graph-scope-indicator {
  flex-shrink: 0;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--wb-blue);
}
.graph-scope-note {
  color: var(--wb-muted);
  font-size: 12px;
}
.graph-stats {
  display: flex;
  flex-shrink: 0;
  margin: 0;
}
.graph-stats > div {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding-left: 20px;
  margin-left: 20px;
  border-left: 1px solid var(--wb-line);
}
.graph-stats > div:first-child {
  border: 0;
  margin: 0;
  padding: 0;
}
.graph-stats dt {
  color: var(--wb-muted);
  font-size: 12px;
}
.graph-stats dd {
  margin: 0;
  font-family: var(--wb-number);
  font-size: 19px;
  font-variant-numeric: tabular-nums;
}
.chart-container {
  flex: 1;
  position: relative;
  min-height: 0;
  overflow: hidden;
}
.chart-dom {
  width: 100%;
  height: 100%;
}
.chart-dom.is-unavailable {
  visibility: hidden;
}
.graph-state {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  padding: 28px;
  text-align: center;
}
.graph-state-icon {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  margin-bottom: 4px;
  border: 1px solid var(--wb-border);
  border-radius: 12px;
  background: var(--wb-blue-soft);
  color: var(--wb-blue);
  font-size: 23px;
}
.graph-state-icon.is-error {
  background: var(--wb-tint);
  color: var(--wb-muted);
  border-color: var(--wb-line);
}
.graph-state-icon.is-loading .el-icon {
  animation: graph-loading-spin 1.2s linear infinite;
}
.graph-state strong {
  color: var(--wb-ink);
  font-size: 16px;
  font-weight: 500;
}
.graph-state p {
  max-width: 360px;
  margin: 0 0 8px;
  color: var(--wb-muted);
  font-size: 13px;
  line-height: 1.8;
}
.graph-view-tools {
  position: absolute;
  right: 18px;
  bottom: 18px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--wb-surface);
  border: 1px solid var(--wb-line);
  border-radius: 6px;
}
.graph-view-tools button {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--wb-muted);
  cursor: pointer;
  font-size: 18px;
}
.graph-view-tools button + button {
  border-top: 1px solid var(--wb-line);
}
.graph-view-tools button:hover {
  color: var(--wb-blue);
  background: var(--wb-blue-soft);
}
.graph-view-tools button:focus-visible {
  outline-offset: -3px;
}
.graph-footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px;
  border-top: 1px solid var(--wb-line);
  padding: 12px 20px;
  color: var(--wb-muted);
  font-size: 12px;
}
.graph-touch-hint {
  display: none;
}
@keyframes graph-loading-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (max-width: 1099px) {
  .graph-field-label {
    display: none;
  }
  .search-select {
    width: min(340px, 40vw);
  }
  .graph-stats > div {
    gap: 6px;
    padding-left: 12px;
    margin-left: 12px;
  }
}
@media (max-width: 699px) {
  .graph-page {
    gap: 14px;
  }
  .graph-toolbar {
    align-items: flex-start;
    gap: 10px;
  }
  .graph-query {
    flex-wrap: wrap;
    gap: 12px;
  }
  .search-select {
    width: 100%;
  }
  .graph-hop-field {
    margin: 0;
  }
  .graph-context {
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
    padding: 16px;
  }
  .graph-stats {
    width: 100%;
  }
  .graph-stats > div {
    flex: 1;
    padding-left: 16px;
    margin-left: 16px;
  }
  .graph-stats dd {
    font-size: 18px;
  }
  .graph-footer {
    padding: 12px 16px;
    font-size: 11px;
  }
  .graph-gesture-hint {
    display: none;
  }
  .graph-touch-hint {
    display: inline;
  }
  .graph-view-tools {
    right: 12px;
    bottom: 12px;
  }
  .graph-view-tools button {
    width: 40px;
    height: 40px;
  }
  .graph-state {
    padding: 20px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .graph-state-icon.is-loading .el-icon {
    animation: none;
  }
}
</style>
