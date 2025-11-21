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
              title="刷新图谱"
            />
            <el-button
              :icon="ZoomIn"
              circle
              @click="zoomIn"
              size="small"
              title="放大"
            />
            <el-button
              :icon="ZoomOut"
              circle
              @click="zoomOut"
              size="small"
              title="缩小"
            />
            <el-button
              :icon="FullScreen"
              circle
              @click="resetView"
              size="small"
              title="重置视图"
            />
            <el-button
              :icon="Setting"
              circle
              @click="showSettings = !showSettings"
              size="small"
              title="设置"
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

          <!-- 左侧控制面板 -->
          <div class="control-panel" :class="{ 'collapsed': !showControls }">
            <div class="panel-toggle" @click="showControls = !showControls">
              <el-icon><ArrowLeft /></el-icon>
            </div>

            <div class="panel-content" v-show="showControls">
              <!-- 搜索面板 -->
              <div class="search-section">
                <h4>实体搜索</h4>
                <el-input
                  v-model="searchQuery"
                  placeholder="搜索实体..."
                  :prefix-icon="Search"
                  clearable
                  @input="handleSearch"
                  @keyup.enter="handleSearchAndExpand"
                >
                  <template #append>
                    <el-button @click="handleSearchAndExpand" :icon="Position" title="搜索并展开关联">
                    </el-button>
                  </template>
                </el-input>

                <div class="search-options">
                  <el-checkbox v-model="searchOptions.expandNeighbors" @change="handleSearchAndExpand">
                    展开关联节点
                  </el-checkbox>
                  <el-checkbox v-model="searchOptions.multiHop" @change="handleSearchAndExpand">
                    多跳探索 ({{ searchOptions.hopCount }}跳)
                  </el-checkbox>
                  <el-slider
                    v-if="searchOptions.multiHop"
                    v-model="searchOptions.hopCount"
                    :min="1"
                    :max="5"
                    :step="1"
                    show-stops
                    @change="handleSearchAndExpand"
                  />
                </div>
              </div>

              <!-- 节点过滤器 -->
              <div class="filter-section">
                <h4>节点类型过滤</h4>
                <el-checkbox-group v-model="selectedNodeTypes" @change="handleTypeFilter">
                  <el-checkbox
                    v-for="type in nodeTypes"
                    :key="type.value"
                    :label="type.value"
                  >
                    <div class="type-checkbox">
                      <span class="type-color" :style="{backgroundColor: type.color}"></span>
                      {{ type.label }} ({{ type.count }})
                    </div>
                  </el-checkbox>
                </el-checkbox-group>
              </div>

              <!-- 图谱布局 -->
              <div class="layout-section">
                <h4>布局设置</h4>
                <el-select v-model="layoutType" @change="changeLayout" placeholder="选择布局">
                  <el-option label="力导向布局" value="force"></el-option>
                  <el-option label="环形布局" value="circular"></el-option>
                  <el-option label="层次布局" value="hierarchical"></el-option>
                  <el-option label="树形布局" value="tree"></el-option>
                  <el-option label="网格布局" value="grid"></el-option>
                </el-select>
              </div>
            </div>
          </div>

          <!-- 右侧信息面板 -->
          <div class="info-panel" v-if="selectedNode">
            <div class="panel-header">
              <h4>{{ selectedNode.label || selectedNode.id }}</h4>
              <el-button :icon="Close" circle @click="selectedNode = null" size="small" />
            </div>

            <div class="panel-body">
              <el-descriptions :column="1" size="small" border>
                <el-descriptions-item label="类型">
                  <el-tag :color="getNodeColor(selectedNode.type)">
                    {{ selectedNode.type || '未知' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="描述" v-if="selectedNode.description">
                  {{ selectedNode.description }}
                </el-descriptions-item>
                <el-descriptions-item label="连接数">
                  {{ getNodeConnections(selectedNode.id).length }}
                </el-descriptions-item>
              </el-descriptions>

              <div class="node-actions">
                <el-button @click="expandNode(selectedNode.id, 1)" :icon="Share" size="small">
                  展开1跳
                </el-button>
                <el-button @click="expandNode(selectedNode.id, 2)" :icon="Share" size="small">
                  展开2跳
                </el-button>
                <el-button @click="highlightPaths(selectedNode.id)" :icon="Connection" size="small">
                  显示路径
                </el-button>
                <el-button @click="hideNode(selectedNode.id)" :icon="Hide" size="small" type="danger">
                  隐藏节点
                </el-button>
              </div>

              <!-- 关联节点列表 -->
              <div class="related-nodes" v-if="relatedNodes.length > 0">
                <h5>关联节点</h5>
                <el-scrollbar height="200px">
                  <div class="related-node-list">
                    <div
                      v-for="node in relatedNodes"
                      :key="node.id"
                      class="related-node-item"
                      @click="selectNode(node.id)"
                    >
                      <span class="node-color" :style="{backgroundColor: getNodeColor(node.type)}"></span>
                      <span class="node-label">{{ node.label || node.id }}</span>
                      <span class="node-type">{{ node.type }}</span>
                    </div>
                  </div>
                </el-scrollbar>
              </div>
            </div>
          </div>

          <!-- 底部统计面板 -->
          <div class="stats-panel">
            <el-card class="stats-card" shadow="never">
              <div class="stats-grid">
                <div class="stat-item">
                  <el-icon><Connection /></el-icon>
                  <div class="stat-info">
                    <div class="stat-value">{{ visibleStats.nodes }}</div>
                    <div class="stat-label">可见节点</div>
                  </div>
                </div>
                <el-divider direction="vertical" />
                <div class="stat-item">
                  <el-icon><Share /></el-icon>
                  <div class="stat-info">
                    <div class="stat-value">{{ visibleStats.edges }}</div>
                    <div class="stat-label">可见边</div>
                  </div>
                </div>
                <el-divider direction="vertical" />
                <div class="stat-item">
                  <el-icon><Position /></el-icon>
                  <div class="stat-info">
                    <div class="stat-value">{{ selectedPath.length }}</div>
                    <div class="stat-label">路径长度</div>
                  </div>
                </div>
              </div>
            </el-card>
          </div>

          <!-- 工具栏 -->
          <div class="toolbar">
            <el-button-group>
              <el-button @click="clearHighlights" :icon="Remove" size="small" title="清除高亮">
                清除高亮
              </el-button>
              <el-button @click="showAllNodes" :icon="View" size="small" title="显示所有节点">
                显示全部
              </el-button>
              <el-button @click="exportGraph" :icon="Download" size="small" title="导出图谱">
                导出
              </el-button>
              <el-button @click="toggleMiniMap" :icon="Monitor" size="small" title="小地图">
                小地图
              </el-button>
            </el-button-group>
          </div>

          <!-- 小地图 -->
          <div class="minimap" v-if="showMinimap">
            <div ref="minimapContainer" class="minimap-canvas"></div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 设置对话框 -->
    <el-dialog v-model="showSettings" title="图谱设置" width="500px">
      <el-form :model="settings" label-width="120px">
        <el-form-item label="节点大小">
          <el-slider v-model="settings.nodeSize" :min="4" :max="20" />
        </el-form-item>
        <el-form-item label="连线粗细">
          <el-slider v-model="settings.linkWidth" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="力导向强度">
          <el-slider v-model="settings.forceStrength" :min="-1000" :max="-100" />
        </el-form-item>
        <el-form-item label="标签显示">
          <el-switch v-model="settings.showLabels" />
        </el-form-item>
        <el-form-item label="动画效果">
          <el-switch v-model="settings.enableAnimation" />
        </el-form-item>
        <el-form-item label="3D效果">
          <el-switch v-model="settings.enable3D" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSettings = false">取消</el-button>
        <el-button type="primary" @click="applySettings">应用</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, nextTick } from 'vue'
import {
  Share, Refresh, ZoomIn, ZoomOut, FullScreen, Setting, ArrowLeft,
  Loading, CircleClose, Connection, Search, Position, Close, Hide,
  Remove, View, Download, Monitor
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as d3 from 'd3'
import { getGraphData } from '@/api'

// 响应式数据
const graphContainer = ref(null)
const minimapContainer = ref(null)
const loading = ref(false)
const error = ref(null)
const searchQuery = ref('')
const showControls = ref(true)
const showSettings = ref(false)
const showMinimap = ref(false)
const selectedNode = ref(null)
const selectedPath = ref([])
const layoutType = ref('force')

// 统计数据
const stats = ref({
  nodes: 0,
  edges: 0
})

const visibleStats = ref({
  nodes: 0,
  edges: 0
})

// 搜索选项
const searchOptions = ref({
  expandNeighbors: true,
  multiHop: false,
  hopCount: 1
})

// 节点类型过滤
const selectedNodeTypes = ref([])

// 图谱设置
const settings = ref({
  nodeSize: 12,
  linkWidth: 2,
  forceStrength: -300,
  showLabels: true,
  enableAnimation: true,
  enable3D: false
})

// D3相关变量
let simulation = null
let svg = null
let minimapSvg = null
let graphData = null
let currentLayout = null
let zoomBehavior = null

// 计算属性
const nodeTypes = computed(() => {
  if (!graphData?.nodes) return []

  const typeCount = {}
  graphData.nodes.forEach(node => {
    const type = node.type || 'unknown'
    typeCount[type] = (typeCount[type] || 0) + 1
  })

  return Object.entries(typeCount).map(([type, count]) => ({
    value: type,
    label: getTypeLabel(type),
    count,
    color: getNodeColor(type)
  }))
})

const relatedNodes = computed(() => {
  if (!selectedNode.value || !graphData?.nodes) return []

  const connections = getNodeConnections(selectedNode.value.id)
  return connections.map(conn => {
    const targetId = conn.source === selectedNode.value.id ? conn.target : conn.source
    return graphData.nodes.find(node => node.id === targetId)
  }).filter(Boolean)
})

// 加载图谱数据
const loadGraph = async () => {
  loading.value = true
  error.value = null

  try {
    // 使用真实的API数据
    const response = await getGraphData()
    graphData = response || { nodes: [], links: [] }

    const nodeCount = Array.isArray(graphData.nodes) ? graphData.nodes.length : 0
    const edgeCount = Array.isArray(graphData.links) ? graphData.links.length : 0

    stats.value = { nodes: nodeCount, edges: edgeCount }
    visibleStats.value = { nodes: nodeCount, edges: edgeCount }

    if (!nodeCount && !edgeCount) {
      throw new Error('知识图谱暂无可展示的数据')
    }

    // 初始化节点类型过滤
    selectedNodeTypes.value = nodeTypes.value.map(type => type.value)

    await renderGraph()
    // 使用 nextTick 确保 DOM 更新后再适应视图
    await nextTick()
    setTimeout(() => {
      fitToView()
    }, 100)
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
  return new Promise((resolve) => {
    if (!graphContainer.value || !graphData) {
      resolve()
      return
    }

    const nodes = Array.isArray(graphData.nodes) ? graphData.nodes : []
    const links = Array.isArray(graphData.links) ? graphData.links : []
    if (!nodes.length) {
      error.value = '知识图谱暂无可视化数据，请先完成 LightRAG 构建'
      resolve()
      return
    }

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

    // 添加渐变定义
    const defs = svg.append('defs')

    // 添加节点阴影效果
    const filter = defs.append('filter')
      .attr('id', 'drop-shadow')
      .attr('height', '130%')

    filter.append('feGaussianBlur')
      .attr('in', 'SourceAlpha')
      .attr('stdDeviation', 3)
      .attr('result', 'blur')

    filter.append('feOffset')
      .attr('in', 'blur')
      .attr('dx', 2)
      .attr('dy', 2)
      .attr('result', 'offsetBlur')

    const feMerge = filter.append('feMerge')
    feMerge.append('feMergeNode').attr('in', 'offsetBlur')
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic')

    // 添加箭头标记
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', settings.value.nodeSize + 5)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .append('svg:path')
      .attr('d', 'M 0,-4 L 6,0 L 0,4')
      .attr('fill', '#999')
      .attr('stroke', '#999')
      .attr('stroke-width', 1)

    const g = svg.append('g')

    // 添加缩放行为
    zoomBehavior = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })

    svg.call(zoomBehavior)

    // 初始化节点位置为随机，避免重叠
    nodes.forEach((d, i) => {
      if (!d.x || !d.y) {
        d.x = width / 2 + (Math.random() - 0.5) * 100
        d.y = height / 2 + (Math.random() - 0.5) * 100
      }
    })

    // 创建力导向模拟
    simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(settings.value.forceStrength))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(settings.value.nodeSize * 2.5))
      .alphaDecay(0.05) // 让模拟更快稳定

    // 绘制连线
    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('class', 'graph-link')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', d => Math.sqrt(d.weight || 1) * settings.value.linkWidth)
      .attr('marker-end', 'url(#arrowhead)')

    // 绘制节点组
    const node = g.append('g')
      .selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'graph-node')
      .call(d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended))
      .on('click', (event, d) => {
        event.stopPropagation()
        selectedNode.value = d
      })
      .on('mouseover', function(event, d) {
        d3.select(this)
          .select('circle')
          .transition()
          .duration(200)
          .attr('r', settings.value.nodeSize + 4)
          .attr('filter', 'url(#drop-shadow)')
      })
      .on('mouseout', function(event, d) {
        if (!selectedNode.value || selectedNode.value.id !== d.id) {
          d3.select(this)
            .select('circle')
            .transition()
            .duration(200)
            .attr('r', settings.value.nodeSize)
            .attr('filter', 'none')
        }
      })

    // 节点圆形背景
    node.append('circle')
      .attr('r', settings.value.nodeSize)
      .attr('fill', d => getNodeColor(d.type))
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)

    // 节点图标（根据类型显示不同图标）
    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .attr('font-size', '14px')
      .attr('fill', '#fff')
      .text(d => getNodeIcon(d.type))

    // 节点标签
    if (settings.value.showLabels) {
      node.append('text')
        .attr('class', 'node-label')
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('dy', settings.value.nodeSize + 15)
        .style('font-size', '12px')
        .style('fill', '#333')
        .style('font-weight', '500')
        .text(d => {
          const label = d.label || d.id
          return label.length > 10 ? label.substring(0, 10) + '...' : label
        })
        .append('title')
        .text(d => d.label || d.id)
    }

    // 添加提示
    node.append('title')
      .text(d => `${d.label || d.id}\n类型: ${d.type || '未知'}\n${d.description || ''}`)

    // 更新模拟
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    // 等待力导向布局稳定后自动缩放到合适的视图
    simulation.on('end', () => {
      setTimeout(() => {
        fitToView()
        resolve()
      }, 300)
    })

    // 如果是其他布局（非力导向），也需要适应视图
    if (layoutType.value !== 'force') {
      setTimeout(() => {
        fitToView()
      }, 100)
    }

    // 应用当前布局
    changeLayout()
  })
}

// 自动适应视图
const fitToView = () => {
  if (!svg || !graphData || !zoomBehavior) return

  const nodes = graphData.nodes
  if (!nodes || !nodes.length) return

  // 检查节点是否有有效的位置
  const validNodes = nodes.filter(d => d.x !== undefined && d.y !== undefined && !isNaN(d.x) && !isNaN(d.y))
  if (!validNodes.length) return

  // 计算所有节点的边界
  const padding = 50
  const minX = d3.min(validNodes, d => d.x) - padding
  const maxX = d3.max(validNodes, d => d.x) + padding
  const minY = d3.min(validNodes, d => d.y) - padding
  const maxY = d3.max(validNodes, d => d.y) + padding

  const nodeWidth = maxX - minX
  const nodeHeight = maxY - minY

  // 防止除零错误
  if (nodeWidth === 0 || nodeHeight === 0) return

  const container = graphContainer.value
  if (!container) return

  const containerWidth = container.clientWidth
  const containerHeight = container.clientHeight

  // 计算缩放比例，限制在合理范围内
  const scaleX = containerWidth / nodeWidth
  const scaleY = containerHeight / nodeHeight
  const scale = Math.min(scaleX, scaleY, 3) // 限制最大缩放为3倍

  // 最小缩放为0.1
  const finalScale = Math.max(scale, 0.1)

  // 计算平移距离，使图谱居中
  const translateX = (containerWidth - nodeWidth * finalScale) / 2 - minX * finalScale
  const translateY = (containerHeight - nodeHeight * finalScale) / 2 - minY * finalScale

  // 应用变换
  const transform = d3.zoomIdentity.translate(translateX, translateY).scale(finalScale)

  // 立即应用变换，不使用过渡动画
  svg.call(zoomBehavior.transform, transform)

  // 再次确保变换生效
  setTimeout(() => {
    svg.call(zoomBehavior.transform, transform)
  }, 50)
}

// 根据节点类型获取图标
const getNodeIcon = (type) => {
  const iconMap = {
    'organization': '🏢',
    'person': '👤',
    'location': '📍',
    'event': '📅',
    'concept': '💡',
    'policy': '📜',
    'unknown': '📌'
  }
  return iconMap[type] || iconMap.unknown
}

// 获取节点连接
const getNodeConnections = (nodeId) => {
  if (!graphData?.links) return []

  return graphData.links.filter(link =>
    link.source === nodeId || link.target === nodeId ||
    (link.source.id === nodeId || link.target.id === nodeId)
  )
}

// 获取多跳节点
const getMultiHopNodes = (startNodeId, hopCount) => {
  const visited = new Set([startNodeId])
  const result = new Set()
  let currentLevel = [startNodeId]

  for (let hop = 1; hop <= hopCount; hop++) {
    const nextLevel = []

    currentLevel.forEach(nodeId => {
      const connections = getNodeConnections(nodeId)
      connections.forEach(conn => {
        const targetId = conn.source === nodeId ? conn.target : conn.source
        if (!visited.has(targetId)) {
          visited.add(targetId)
          result.add(targetId)
          nextLevel.push(targetId)
        }
      })
    })

    currentLevel = nextLevel
  }

  return Array.from(result)
}

// 搜索并展开关联节点
const handleSearchAndExpand = () => {
  if (!searchQuery.value || !graphData) {
    clearHighlights()
    return
  }

  const query = searchQuery.value.toLowerCase()
  const matchedNodes = graphData.nodes.filter(node =>
    (node.label || node.id || '').toLowerCase().includes(query)
  )

  if (matchedNodes.length === 0) {
    ElMessage.warning('未找到匹配的实体')
    return
  }

  // 清除之前的高亮
  clearHighlights()

  // 如果启用展开关联节点
  if (searchOptions.value.expandNeighbors) {
    const hopCount = searchOptions.value.multiHop ? searchOptions.value.hopCount : 1
    const nodesToHighlight = new Set(matchedNodes.map(n => n.id))

    matchedNodes.forEach(node => {
      const multiHopNodes = getMultiHopNodes(node.id, hopCount)
      multiHopNodes.forEach(id => nodesToHighlight.add(id))
    })

    highlightNodes(Array.from(nodesToHighlight))
  } else {
    highlightNodes(matchedNodes.map(n => n.id))
  }

  ElMessage.success(`找到 ${matchedNodes.length} 个匹配实体`)

  // 自动聚焦到第一个匹配的节点
  if (matchedNodes.length > 0) {
    focusOnNode(matchedNodes[0].id)
  }
}

// 高亮节点
const highlightNodes = (nodeIds) => {
  if (!svg) return

  svg.selectAll('.graph-node')
    .each(function(d) {
      const isHighlighted = nodeIds.includes(d.id)
      const node = d3.select(this)

      node.select('circle')
        .attr('stroke', isHighlighted ? '#ff4d4f' : '#fff')
        .attr('stroke-width', isHighlighted ? 4 : 2)
        .attr('r', isHighlighted ? settings.value.nodeSize + 4 : settings.value.nodeSize)
        .attr('filter', isHighlighted ? 'url(#drop-shadow)' : 'none')
    })

  // 高亮相关边
  svg.selectAll('.graph-link')
    .attr('stroke', d => {
      const isHighlighted = nodeIds.includes(d.source.id || d.source) &&
                           nodeIds.includes(d.target.id || d.target)
      return isHighlighted ? '#ff4d4f' : '#999'
    })
    .attr('stroke-width', d => {
      const isHighlighted = nodeIds.includes(d.source.id || d.source) &&
                           nodeIds.includes(d.target.id || d.target)
      return isHighlighted ? settings.value.linkWidth + 2 : settings.value.linkWidth
    })
    .attr('stroke-opacity', d => {
      const isHighlighted = nodeIds.includes(d.source.id || d.source) &&
                           nodeIds.includes(d.target.id || d.target)
      return isHighlighted ? 1 : 0.3
    })
}

// 清除高亮
const clearHighlights = () => {
  if (!svg) return

  svg.selectAll('.graph-node circle')
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)
    .attr('r', settings.value.nodeSize)
    .attr('filter', d => selectedNode.value && selectedNode.value.id === d.id ? 'url(#drop-shadow)' : 'none')

  svg.selectAll('.graph-link')
    .attr('stroke', '#999')
    .attr('stroke-width', d => Math.sqrt(d.weight || 1) * settings.value.linkWidth)
    .attr('stroke-opacity', 0.6)
}

// 展开节点
const expandNode = (nodeId, hopCount = 1) => {
  const multiHopNodes = getMultiHopNodes(nodeId, hopCount)
  highlightNodes([nodeId, ...multiHopNodes])

  // 聚焦到该节点
  focusOnNode(nodeId)
}

// 聚焦到指定节点
const focusOnNode = (nodeId) => {
  if (!svg || !graphData) return

  const node = graphData.nodes.find(n => n.id === nodeId)
  if (!node || !node.x || !node.y) return

  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  const scale = 2 // 放大到2倍
  const translate = [width/2 - scale * node.x, height/2 - scale * node.y]

  svg.transition()
    .duration(750)
    .call(zoomBehavior.transform, d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale))
}

// 高亮路径
const highlightPaths = (nodeId) => {
  if (!graphData) return

  // 使用BFS找到从nodeId到所有其他节点的最短路径
  const paths = bfsShortestPaths(nodeId)
  selectedPath.value = paths

  // 高亮路径上的边
  const pathEdges = new Set()
  Object.values(paths).forEach(path => {
    for (let i = 0; i < path.length - 1; i++) {
      pathEdges.add(`${path[i]}-${path[i+1]}`)
      pathEdges.add(`${path[i+1]}-${path[i]}`)
    }
  })

  svg.selectAll('.graph-link')
    .attr('stroke', d => {
      const edgeKey = `${d.source.id || d.source}-${d.target.id || d.target}`
      return pathEdges.has(edgeKey) ? '#52c41a' : '#999'
    })
    .attr('stroke-width', d => {
      const edgeKey = `${d.source.id || d.source}-${d.target.id || d.target}`
      return pathEdges.has(edgeKey) ? settings.value.linkWidth + 2 : settings.value.linkWidth
    })
}

// BFS最短路径算法
const bfsShortestPaths = (startId) => {
  const paths = {}
  const queue = [[startId]]
  const visited = new Set([startId])

  while (queue.length > 0) {
    const currentPath = queue.shift()
    const currentId = currentPath[currentPath.length - 1]

    const connections = getNodeConnections(currentId)
    connections.forEach(conn => {
      const nextId = conn.source === currentId ? conn.target : conn.source

      if (!visited.has(nextId)) {
        visited.add(nextId)
        const newPath = [...currentPath, nextId]
        paths[nextId] = newPath
        queue.push(newPath)
      }
    })
  }

  return paths
}

// 隐藏节点
const hideNode = (nodeId) => {
  if (!graphData) return

  const nodeIndex = graphData.nodes.findIndex(n => n.id === nodeId)
  if (nodeIndex === -1) return

  // 移除节点和相关边
  graphData.nodes.splice(nodeIndex, 1)
  graphData.links = graphData.links.filter(link =>
    link.source !== nodeId && link.target !== nodeId
  )

  // 重新渲染
  renderGraph()
  ElMessage.success('节点已隐藏')
}

// 选择节点
const selectNode = (nodeId) => {
  const node = graphData.nodes.find(n => n.id === nodeId)
  if (node) {
    selectedNode.value = node
    focusOnNode(nodeId)
  }
}

// 显示所有节点
const showAllNodes = () => {
  loadGraph()
}

// 导出图谱
const exportGraph = async () => {
  try {
    const exportData = {
      nodes: graphData.nodes,
      links: graphData.links,
      stats: stats.value,
      exportTime: new Date().toISOString()
    }

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json'
    })

    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `knowledge-graph-${Date.now()}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    ElMessage.success('图谱导出成功')
  } catch (error) {
    ElMessage.error('导出失败: ' + error.message)
  }
}

// 切换小地图
const toggleMiniMap = () => {
  showMinimap.value = !showMinimap.value
  if (showMinimap.value) {
    renderMinimap()
  }
}

// 渲染小地图
const renderMinimap = () => {
  if (!minimapContainer.value || !graphData) return

  const container = minimapContainer.value
  const width = 200
  const height = 150

  // 清除旧图
  d3.select(container).selectAll('*').remove()

  minimapSvg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height)

  const g = minimapSvg.append('g')

  // 缩放比例
  const xScale = d3.scaleLinear()
    .domain([0, graphContainer.value.clientWidth])
    .range([0, width])

  const yScale = d3.scaleLinear()
    .domain([0, graphContainer.value.clientHeight])
    .range([0, height])

  // 简化的节点和边
  const miniNodes = g.selectAll('.mini-node')
    .data(graphData.nodes)
    .enter()
    .append('circle')
    .attr('class', 'mini-node')
    .attr('r', 2)
    .attr('fill', d => getNodeColor(d.type))

  const miniLinks = g.selectAll('.mini-link')
    .data(graphData.links)
    .enter()
    .append('line')
    .attr('class', 'mini-link')
    .attr('stroke', '#999')
    .attr('stroke-width', 1)
}

// 应用设置
const applySettings = () => {
  renderGraph()
  showSettings.value = false
  ElMessage.success('设置已应用')
}

// 改变布局
const changeLayout = () => {
  if (!graphData) return

  switch (layoutType.value) {
    case 'circular':
      applyCircularLayout()
      break
    case 'hierarchical':
      applyHierarchicalLayout()
      break
    case 'tree':
      applyTreeLayout()
      break
    case 'grid':
      applyGridLayout()
      break
    default:
      applyForceLayout()
  }
}

// 应用力导向布局
const applyForceLayout = () => {
  if (!simulation) return

  simulation
    .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(settings.value.forceStrength))
    .force('center', d3.forceCenter(graphContainer.value.clientWidth / 2, graphContainer.value.clientHeight / 2))
    .force('collision', d3.forceCollide().radius(settings.value.nodeSize * 2.5))

  simulation.alpha(1).restart()
}

// 应用环形布局
const applyCircularLayout = () => {
  if (!graphData) return

  const container = graphContainer.value
  const centerX = container.clientWidth / 2
  const centerY = container.clientHeight / 2
  const radius = Math.min(centerX, centerY) * 0.8

  graphData.nodes.forEach((node, i) => {
    const angle = (i / graphData.nodes.length) * 2 * Math.PI
    node.x = centerX + radius * Math.cos(angle)
    node.y = centerY + radius * Math.sin(angle)
    node.fx = node.x
    node.fy = node.y
  })

  if (simulation) {
    simulation.alpha(0.3).restart()
  }

  // 延迟适应视图
  setTimeout(() => fitToView(), 100)
}

// 应用层次布局
const applyHierarchicalLayout = () => {
  if (!graphData) return

  // 简单的层次布局实现
  const levels = {}
  const visited = new Set()

  // 找到根节点（入度最小的节点）
  const inDegree = {}
  graphData.nodes.forEach(node => {
    inDegree[node.id] = 0
  })

  graphData.links.forEach(link => {
    inDegree[link.target] = (inDegree[link.target] || 0) + 1
  })

  const roots = graphData.nodes.filter(node => inDegree[node.id] === 0)
  if (roots.length === 0) roots.push(graphData.nodes[0])

  // BFS分配层次
  const queue = roots.map(node => ({ node, level: 0 }))

  while (queue.length > 0) {
    const { node, level } = queue.shift()

    if (visited.has(node.id)) continue
    visited.add(node.id)

    if (!levels[level]) levels[level] = []
    levels[level].push(node)

    const connections = getNodeConnections(node.id)
    connections.forEach(conn => {
      const targetId = conn.source === node.id ? conn.target : conn.source
      if (!visited.has(targetId)) {
        const targetNode = graphData.nodes.find(n => n.id === targetId)
        queue.push({ node: targetNode, level: level + 1 })
      }
    })
  }

  // 布局节点
  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight
  const levelHeight = height / (Object.keys(levels).length + 1)

  Object.entries(levels).forEach(([level, nodes]) => {
    const levelY = (parseInt(level) + 1) * levelHeight
    const nodeWidth = width / (nodes.length + 1)

    nodes.forEach((node, i) => {
      node.x = (i + 1) * nodeWidth
      node.y = levelY
      node.fx = node.x
      node.fy = node.y
    })
  })

  if (simulation) {
    simulation.alpha(0.3).restart()
  }

  // 延迟适应视图
  setTimeout(() => fitToView(), 100)
}

// 应用树形布局
const applyTreeLayout = () => {
  if (!graphData) return

  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight

  // 创建层次结构
  const root = d3.stratify()
    .id(d => d.id)
    .parentId(d => {
      const link = graphData.links.find(l => l.target === d.id)
      return link ? link.source : null
    })(graphData.nodes)

  // 创建树形布局
  const treeLayout = d3.tree()
    .size([width - 100, height - 100])
    .separation((a, b) => (a.parent == b.parent ? 1 : 2) / a.depth)

  treeLayout(root)

  // 更新节点位置
  root.descendants().forEach(d => {
    const node = d.data
    node.x = d.x + width / 2 - (width - 100) / 2
    node.y = d.y + 50
    node.fx = node.x
    node.fy = node.y
  })

  if (simulation) {
    simulation.alpha(0.3).restart()
  }

  // 延迟适应视图
  setTimeout(() => fitToView(), 100)
}

// 应用网格布局
const applyGridLayout = () => {
  if (!graphData) return

  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight
  const cols = Math.ceil(Math.sqrt(graphData.nodes.length))
  const rows = Math.ceil(graphData.nodes.length / cols)
  const cellWidth = width / cols
  const cellHeight = height / rows

  graphData.nodes.forEach((node, i) => {
    const col = i % cols
    const row = Math.floor(i / cols)
    node.x = (col + 0.5) * cellWidth
    node.y = (row + 0.5) * cellHeight
    node.fx = node.x
    node.fy = node.y
  })

  if (simulation) {
    simulation.alpha(0.3).restart()
  }

  // 延迟适应视图
  setTimeout(() => fitToView(), 100)
}

// 节点类型过滤
const handleTypeFilter = () => {
  if (!graphData) return

  const filteredNodes = graphData.nodes.filter(node =>
    selectedNodeTypes.value.includes(node.type || 'unknown')
  )
  const filteredNodeIds = new Set(filteredNodes.map(n => n.id))
  const filteredLinks = graphData.links.filter(link =>
    filteredNodeIds.has(link.source.id || link.source) &&
    filteredNodeIds.has(link.target.id || link.target)
  )

  visibleStats.value = {
    nodes: filteredNodes.length,
    edges: filteredLinks.length
  }

  // 重新渲染过滤后的数据
  renderFilteredGraph(filteredNodes, filteredLinks)
}

// 渲染过滤后的图谱
const renderFilteredGraph = (filteredNodes, filteredLinks) => {
  if (!graphContainer.value) return

  // 临时更新数据并重新渲染
  const originalData = graphData
  graphData = { nodes: filteredNodes, links: filteredLinks }
  renderGraph()
  graphData = originalData
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
    'unknown': '#9a60b4'
  }
  return colorMap[type] || colorMap.unknown
}

// 获取类型标签
const getTypeLabel = (type) => {
  const labelMap = {
    'organization': '组织机构',
    'person': '人物',
    'location': '地理位置',
    'event': '事件',
    'concept': '概念',
    'policy': '政策',
    'unknown': '未知'
  }
  return labelMap[type] || type
}

// 拖拽事件处理
const dragstarted = (event, d) => {
  if (simulation && !event.active) simulation.alphaTarget(0.3).restart()
  d.fx = d.x
  d.fy = d.y
}

const dragged = (event, d) => {
  d.fx = event.x
  d.fy = event.y
}

const dragended = (event, d) => {
  if (simulation && !event.active) simulation.alphaTarget(0)
  d.fx = null
  d.fy = null
}

// 缩放控制
const zoomIn = () => {
  if (svg) {
    svg.transition().call(zoomBehavior.scaleBy, 1.3)
  }
}

const zoomOut = () => {
  if (svg) {
    svg.transition().call(zoomBehavior.scaleBy, 0.7)
  }
}

const resetView = () => {
  if (svg) {
    svg.transition().call(zoomBehavior.transform, d3.zoomIdentity)
    // 延迟一下再适应视图
    setTimeout(() => fitToView(), 800)
  }
}

// 搜索功能
const handleSearch = () => {
  if (!searchQuery.value) {
    clearHighlights()
    return
  }

  const query = searchQuery.value.toLowerCase()
  const matchedNodes = graphData.nodes.filter(node =>
    (node.label || node.id || '').toLowerCase().includes(query)
  )

  if (matchedNodes.length === 0) {
    ElMessage.warning('未找到匹配的实体')
    return
  }

  highlightNodes(matchedNodes.map(n => n.id))
}

// 生命周期
onMounted(() => {
  loadGraph()

  // 监听窗口大小变化
  const handleResize = () => {
    if (graphData) {
      renderGraph()
    }
  }

  window.addEventListener('resize', handleResize)

  // 清理函数
  onBeforeUnmount(() => {
    window.removeEventListener('resize', handleResize)
    if (simulation) {
      simulation.stop()
    }
  })
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
  position: relative;
  height: 100%;
  min-height: 600px;
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
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
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
  min-height: 600px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
  border-radius: var(--radius-md);
  position: relative;
  overflow: hidden;
}

.graph-canvas::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image:
    radial-gradient(circle at 20% 20%, rgba(0,0,0,0.03) 0%, transparent 50%),
    radial-gradient(circle at 80% 80%, rgba(0,0,0,0.03) 0%, transparent 50%);
  pointer-events: none;
}

[data-theme="dark"] .graph-canvas {
  background: linear-gradient(135deg, #1a1d23 0%, #0f1419 100%);
}

[data-theme="dark"] .graph-canvas::before {
  background-image:
    radial-gradient(circle at 20% 20%, rgba(255,255,255,0.03) 0%, transparent 50%),
    radial-gradient(circle at 80% 80%, rgba(255,255,255,0.03) 0%, transparent 50%);
}

/* 左侧控制面板 */
.control-panel {
  position: absolute;
  top: var(--spacing-md);
  left: 0;
  width: 320px;
  max-height: 80vh;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 20;
}

.control-panel.collapsed {
  transform: translateX(-280px);
}

.panel-toggle {
  position: absolute;
  right: -40px;
  top: var(--spacing-md);
  width: 40px;
  height: 40px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.panel-toggle:hover {
  background: var(--el-color-primary);
  color: white;
  transform: translateX(5px);
}

.panel-content {
  padding: var(--spacing-md);
  height: 100%;
  overflow-y: auto;
}

.search-section,
.filter-section,
.layout-section {
  margin-bottom: var(--spacing-lg);
}

.search-section h4,
.filter-section h4,
.layout-section h4 {
  margin: 0 0 var(--spacing-md) 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.search-options {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background: rgba(0, 0, 0, 0.03);
  border-radius: var(--radius-sm);
}

.search-options .el-checkbox {
  display: block;
  margin-bottom: var(--spacing-sm);
}

.type-checkbox {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.type-color {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* 右侧信息面板 */
.info-panel {
  position: absolute;
  top: var(--spacing-md);
  right: var(--spacing-md);
  width: 320px;
  max-height: 80vh;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-radius: var(--radius-md);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  z-index: 20;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--el-border-color-light);
}

.panel-header h4 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.panel-body {
  padding: var(--spacing-md);
  height: calc(100% - 60px);
  overflow-y: auto;
}

.node-actions {
  margin: var(--spacing-md) 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.related-nodes {
  margin-top: var(--spacing-lg);
}

.related-nodes h5 {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.related-node-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.related-node-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: rgba(0, 0, 0, 0.03);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s ease;
}

.related-node-item:hover {
  background: var(--el-color-primary-light-9);
  transform: translateX(5px);
}

.node-color {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.node-label {
  flex: 1;
  font-size: 0.875rem;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-type {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

/* 底部统计面板 */
.stats-panel {
  position: absolute;
  bottom: var(--spacing-md);
  right: var(--spacing-md);
  z-index: 15;
}

.stats-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  min-width: 280px;
}

.stats-grid {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: var(--spacing-sm) var(--spacing-md);
}

.stats-grid .stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
}

.stats-grid .stat-item .el-icon {
  font-size: 1.25rem;
  color: var(--el-color-primary);
}

.stats-grid .stat-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}

.stats-grid .stat-label {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
}

/* 工具栏 */
.toolbar {
  position: absolute;
  top: var(--spacing-md);
  left: 50%;
  transform: translateX(-50%);
  z-index: 15;
}

/* 小地图 */
.minimap {
  position: absolute;
  bottom: var(--spacing-md);
  left: var(--spacing-md);
  width: 200px;
  height: 150px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border: 1px solid var(--el-border-color);
  border-radius: var(--radius-md);
  z-index: 15;
}

.minimap-canvas {
  width: 100%;
  height: 100%;
  border-radius: var(--radius-sm);
}

/* D3图谱样式 */
:deep(.graph-node) {
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

:deep(.graph-node:hover circle) {
  filter: brightness(1.2) url(#drop-shadow);
}

:deep(.graph-link) {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  cursor: pointer;
}

:deep(.graph-link:hover) {
  stroke-width: 3 !important;
  stroke-opacity: 1 !important;
}

:deep(.node-label) {
  pointer-events: none;
  user-select: none;
}

/* 暗色主题适配 */
[data-theme="dark"] .control-panel,
[data-theme="dark"] .info-panel,
[data-theme="dark"] .stats-card {
  background: rgba(26, 29, 35, 0.95);
}

[data-theme="dark"] .panel-toggle {
  background: rgba(26, 29, 35, 0.95);
  color: var(--el-text-color-primary);
}

[data-theme="dark"] .search-options {
  background: rgba(255, 255, 255, 0.05);
}

[data-theme="dark"] .related-node-item {
  background: rgba(255, 255, 255, 0.05);
}

[data-theme="dark"] .related-node-item:hover {
  background: rgba(255, 255, 255, 0.1);
}

[data-theme="dark"] .minimap {
  background: rgba(26, 29, 35, 0.95);
  border-color: var(--el-border-color);
}

/* 响应式 */
@media (max-width: 768px) {
  .control-panel {
    width: 280px;
  }

  .control-panel.collapsed {
    transform: translateX(-240px);
  }

  .info-panel {
    width: 280px;
    right: var(--spacing-sm);
  }

  .stats-card {
    min-width: 240px;
  }

  .toolbar {
    left: var(--spacing-sm);
    transform: none;
  }
}

@media (max-width: 640px) {
  .knowledge-graph-container {
    padding: var(--spacing-sm);
  }

  .control-panel {
    width: 260px;
    top: var(--spacing-sm);
  }

  .info-panel {
    width: 260px;
    top: 50%;
    right: var(--spacing-sm);
    transform: translateY(-50%);
    max-height: 60vh;
  }

  .stats-panel {
    bottom: var(--spacing-sm);
    right: var(--spacing-sm);
  }

  .minimap {
    display: none;
  }
}
</style>