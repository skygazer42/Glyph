<template>
  <div class="knowledge-graph-container">
    <el-card class="graph-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-title">
            <el-icon class="title-icon"><Share /></el-icon>
            <span>知识图谱可视化</span>
          </div>
          <div class="header-actions">
            <el-button
              :icon="Refresh"
              circle
              @click="loadGraph"
              :loading="loading"
              size="small"
            />
            <el-button
              :icon="ZoomIn"
              circle
              @click="zoomIn"
              size="small"
            />
            <el-button
              :icon="ZoomOut"
              circle
              @click="zoomOut"
              size="small"
            />
            <el-button
              :icon="FullScreen"
              circle
              @click="resetView"
              size="small"
            />
          </div>
        </div>
      </template>

      <div class="graph-content">
        <!-- 加载状态 -->
        <div v-if="loading" class="loading-container">
          <el-icon class="loading-icon"><Loading /></el-icon>
          <p>正在加载知识图谱...</p>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="error" class="error-container">
          <el-icon class="error-icon"><CircleClose /></el-icon>
          <p>{{ error }}</p>
          <el-button @click="loadGraph" type="primary">重试</el-button>
        </div>

        <!-- 图谱展示 -->
        <div v-else class="graph-wrapper">
          <div ref="graphContainer" class="graph-canvas"></div>

          <!-- 统计信息面板 -->
          <div class="stats-panel">
            <el-card class="stats-card" shadow="never">
              <div class="stat-item">
                <el-icon><Connection /></el-icon>
                <div class="stat-info">
                  <div class="stat-value">{{ stats.nodes }}</div>
                  <div class="stat-label">实体节点</div>
                </div>
              </div>
              <el-divider />
              <div class="stat-item">
                <el-icon><Share /></el-icon>
                <div class="stat-info">
                  <div class="stat-value">{{ stats.edges }}</div>
                  <div class="stat-label">关系边</div>
                </div>
              </div>
            </el-card>
          </div>

          <!-- 搜索面板 -->
          <div class="search-panel">
            <el-input
              v-model="searchQuery"
              placeholder="搜索实体..."
              :prefix-icon="Search"
              clearable
              @input="handleSearch"
            />
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import {
  Share, Refresh, ZoomIn, ZoomOut, FullScreen,
  Loading, CircleClose, Connection, Search
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import * as d3 from 'd3'
import { getGraphData } from '@/api'

const graphContainer = ref(null)
const loading = ref(false)
const error = ref(null)
const searchQuery = ref('')
const stats = ref({
  nodes: 0,
  edges: 0
})

let simulation = null
let svg = null
let graphData = null

// 加载图谱数据
const loadGraph = async () => {
  loading.value = true
  error.value = null

  try {
    const response = await getGraphData()
    graphData = response.data
    stats.value = {
      nodes: graphData.nodes.length,
      edges: graphData.links.length
    }
    renderGraph()
    ElMessage.success('知识图谱加载成功')
  } catch (err) {
    error.value = err.message || '加载知识图谱失败'
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

// 渲染图谱
const renderGraph = () => {
  if (!graphContainer.value || !graphData) return

  // 清除旧图
  d3.select(graphContainer.value).selectAll('*').remove()

  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  // 创建SVG
  svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)

  const g = svg.append('g')

  // 添加缩放行为
  const zoom = d3.zoom()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
    })

  svg.call(zoom)

  // 创建力导向图模拟
  simulation = d3.forceSimulation(graphData.nodes)
    .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(30))

  // 绘制连线
  const link = g.append('g')
    .selectAll('line')
    .data(graphData.links)
    .enter()
    .append('line')
    .attr('class', 'graph-link')
    .attr('stroke', '#999')
    .attr('stroke-opacity', 0.6)
    .attr('stroke-width', d => Math.sqrt(d.weight || 1))

  // 绘制节点
  const node = g.append('g')
    .selectAll('g')
    .data(graphData.nodes)
    .enter()
    .append('g')
    .attr('class', 'graph-node')
    .call(d3.drag()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended))

  // 节点圆圈
  node.append('circle')
    .attr('r', 8)
    .attr('fill', d => getNodeColor(d.type))
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)

  // 节点标签
  node.append('text')
    .text(d => d.label || d.id)
    .attr('x', 12)
    .attr('y', 4)
    .attr('class', 'node-label')
    .style('font-size', '12px')
    .style('fill', '#333')

  // 添加提示
  node.append('title')
    .text(d => `${d.label || d.id}\n类型: ${d.type || '未知'}\n${d.description || ''}`)

  // 更新位置
  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)

    node.attr('transform', d => `translate(${d.x},${d.y})`)
  })
}

// 根据节点类型获取颜色
const getNodeColor = (type) => {
  const colorMap = {
    'organization': '#5470c6',
    'person': '#91cc75',
    'location': '#fac858',
    'event': '#ee6666',
    'concept': '#73c0de',
    'policy': '#3ba272',
    'default': '#9a60b4'
  }
  return colorMap[type] || colorMap.default
}

// 拖拽事件处理
const dragstarted = (event, d) => {
  if (!event.active) simulation.alphaTarget(0.3).restart()
  d.fx = d.x
  d.fy = d.y
}

const dragged = (event, d) => {
  d.fx = event.x
  d.fy = event.y
}

const dragended = (event, d) => {
  if (!event.active) simulation.alphaTarget(0)
  d.fx = null
  d.fy = null
}

// 缩放控制
const zoomIn = () => {
  svg.transition().call(d3.zoom().scaleBy, 1.3)
}

const zoomOut = () => {
  svg.transition().call(d3.zoom().scaleBy, 0.7)
}

const resetView = () => {
  svg.transition().call(
    d3.zoom().transform,
    d3.zoomIdentity
  )
}

// 搜索功能
const handleSearch = () => {
  if (!svg || !searchQuery.value) {
    // 重置所有节点
    svg.selectAll('.graph-node circle')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
    return
  }

  const query = searchQuery.value.toLowerCase()

  svg.selectAll('.graph-node')
    .each(function(d) {
      const circle = d3.select(this).select('circle')
      const matches = (d.label || d.id || '').toLowerCase().includes(query)

      circle
        .attr('stroke', matches ? '#ff4d4f' : '#fff')
        .attr('stroke-width', matches ? 4 : 2)
    })
}

// 生命周期
onMounted(() => {
  loadGraph()

  // 监听窗口大小变化
  window.addEventListener('resize', () => {
    if (graphData) {
      renderGraph()
    }
  })
})

onBeforeUnmount(() => {
  if (simulation) {
    simulation.stop()
  }
})
</script>

<style scoped>
.knowledge-graph-container {
  width: 100%;
  height: calc(100vh - 140px);
  padding: var(--spacing-md);
}

.graph-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.graph-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.title-icon {
  font-size: 1.25rem;
  color: var(--el-color-primary);
}

.header-actions {
  display: flex;
  gap: var(--spacing-xs);
}

.graph-content {
  height: 100%;
  position: relative;
}

.loading-container,
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: var(--spacing-md);
}

.loading-icon {
  font-size: 3rem;
  color: var(--el-color-primary);
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.error-icon {
  font-size: 3rem;
  color: var(--el-color-danger);
}

.graph-wrapper {
  width: 100%;
  height: 100%;
  position: relative;
}

.graph-canvas {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
  border-radius: var(--radius-md);
}

[data-theme="dark"] .graph-canvas {
  background: linear-gradient(135deg, #1a1d23 0%, #0f1419 100%);
}

.stats-panel {
  position: absolute;
  top: var(--spacing-md);
  right: var(--spacing-md);
  z-index: 10;
}

.stats-card {
  min-width: 150px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
}

[data-theme="dark"] .stats-card {
  background: rgba(26, 29, 35, 0.95);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) 0;
}

.stat-item .el-icon {
  font-size: 1.5rem;
  color: var(--el-color-primary);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
}

.search-panel {
  position: absolute;
  top: var(--spacing-md);
  left: var(--spacing-md);
  z-index: 10;
  width: 300px;
}

.search-panel .el-input {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: var(--radius-md);
}

[data-theme="dark"] .search-panel .el-input {
  background: rgba(26, 29, 35, 0.95);
}

/* D3图谱样式 */
:deep(.graph-node) {
  cursor: pointer;
  transition: all 0.3s ease;
}

:deep(.graph-node:hover circle) {
  r: 12;
}

:deep(.graph-node text) {
  pointer-events: none;
  user-select: none;
}

:deep(.graph-link) {
  transition: all 0.3s ease;
}

:deep(.graph-link:hover) {
  stroke-width: 3 !important;
  stroke-opacity: 1 !important;
}

/* 响应式 */
@media (max-width: 768px) {
  .search-panel {
    width: 200px;
  }

  .stats-card {
    min-width: 120px;
  }

  .stat-value {
    font-size: 1.25rem;
  }
}
</style>
