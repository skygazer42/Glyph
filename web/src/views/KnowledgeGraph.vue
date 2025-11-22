<template>
  <div class="graph-page">
    <div class="header">
      <div class="title">
        <h3>知识图谱可视化</h3>
        <el-tag size="small" type="info" effect="plain">数据源：resources/data/lightrag/graph_chunk_entity_relation.graphml</el-tag>
        <el-tag v-if="isFiltered" type="warning" effect="dark" closable @close="resetToFullGraph">
          当前展示：{{ searchTargetName }} 的 3-hop 邻域
        </el-tag>
        <el-tag v-else size="small" type="success" effect="plain">{{ statsText }}</el-tag>
      </div>
      <div class="actions">
        <el-select
          v-model="searchTargetId"
          placeholder="搜索实体名称..."
          filterable
          clearable
          remote
          :remote-method="filterMethod"
          :loading="searchLoading"
          @change="handleSearch"
          class="search-select"
        >
          <el-option
            v-for="item in filteredOptions"
            :key="item.id"
            :label="item.name"
            :value="item.id"
          >
            <span style="float: left">{{ item.name }}</span>
            <span style="float: right; color: #8492a6; font-size: 12px">{{ item.categoryName }}</span>
          </el-option>
        </el-select>
        <span class="hop-label">邻域</span>
        <el-input-number v-model="hopCount" :min="1" :max="5" size="small" class="hop-input" />
        <el-tag size="small" effect="plain">跳数：{{ hopCount }}</el-tag>
        <span class="hint">选择实体 + 跳数，快速聚焦局部子图</span>
        <el-button :icon="Refresh" circle @click="loadFromApi" title="重新加载数据"></el-button>
        <el-button v-if="isFiltered" @click="resetToFullGraph">显示全部</el-button>
        <el-button @click="resetZoom">复位缩放</el-button>
      </div>
    </div>

    <div class="chart-container" v-loading="loading" element-loading-text="正在渲染图谱...">
      <div ref="chartRef" class="chart-dom"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, shallowRef } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getGraphData } from '@/api'

const chartRef = ref(null)
const chartInstance = shallowRef(null)
const loading = ref(false)
const searchLoading = ref(false)
const hopCount = ref(3)

// 全量数据与邻接表
const fullGraphData = { nodes: [], links: [], categories: [] }
const adjacencyMap = new Map() // nodeId -> Set(neighborIds)

// 搜索选项
const allOptions = ref([])
const filteredOptions = ref([])

// 状态
const stats = ref({ nodes: 0, links: 0, categories: 0 })
const isFiltered = ref(false)
const searchTargetId = ref('')
const searchTargetName = ref('')

const statsText = computed(() =>
  `节点: ${stats.value.nodes} | 边: ${stats.value.links} | 类: ${stats.value.categories}`
)

// 解析与分类
const normalizeApiData = (resp) => {
  const data = resp?.data || resp || {}
  const rawNodes = Array.isArray(data.nodes) ? data.nodes : []
  const rawLinks = Array.isArray(data.links) ? data.links : []

  const categoryMap = new Map()
  let catIdx = 0

  const nodes = rawNodes.map((n, idx) => {
    const id = String(n.id ?? idx)
    const name = n.label ?? n.name ?? n.title ?? id
    const typeName = n.type || n.entity_type || '默认'
    if (!categoryMap.has(typeName)) categoryMap.set(typeName, catIdx++)
    return {
      id,
      name,
      category: categoryMap.get(typeName),
      ...n,
      symbolSize: name.length > 5 ? 25 : 30,
      label: { show: name.length < 8, fontSize: 12 },
    }
  })

  const categories = Array.from(categoryMap.keys()).map((name) => ({ name }))
  const links = rawLinks.map((l, idx) => ({
    source: String(l.source ?? l.src ?? idx),
    target: String(l.target ?? l.dst ?? idx),
    ...l,
  }))

  return { nodes, links, categories }
}

// 邻接表
const buildAdjacencyMap = (links) => {
  adjacencyMap.clear()
  links.forEach((l) => {
    const s = String(l.source)
    const t = String(l.target)
    if (!adjacencyMap.has(s)) adjacencyMap.set(s, new Set())
    if (!adjacencyMap.has(t)) adjacencyMap.set(t, new Set())
    adjacencyMap.get(s).add(t)
    adjacencyMap.get(t).add(s) // 无向视图；若强有向关系可移除此行
  })
}

// 3-hop BFS
const getSubGraph = (startId, hops = 3) => {
  if (!adjacencyMap.has(startId)) return { nodes: [], links: [] }
  const visited = new Set([startId])
  let layer = [startId]
  for (let i = 0; i < hops; i++) {
    const next = []
    layer.forEach((nid) => {
      const neighbors = adjacencyMap.get(nid)
      neighbors?.forEach((nb) => {
        if (!visited.has(nb)) {
          visited.add(nb)
          next.push(nb)
        }
      })
    })
    if (!next.length) break
    layer = next
  }
  const nodes = fullGraphData.nodes.filter((n) => visited.has(n.id))
  const links = fullGraphData.links.filter(
    (l) => visited.has(String(l.source)) && visited.has(String(l.target))
  )
  return { nodes, links }
}

// 渲染
const renderChart = (nodes, links, categories) => {
  if (!chartInstance.value) initChart()

  stats.value = { nodes: nodes.length, links: links.length, categories: categories.length }

  const option = {
    // 柔和过渡，降低闪烁感
    animationDuration: 1500,
    animationDurationUpdate: 500,
    animationEasingUpdate: 'cubicInOut',
    tooltip: {
      trigger: 'item',
      confine: true,
      enterable: true,
      formatter: (params) => {
        if (params.dataType === 'node') {
          const categoryName = categories[params.data.category]?.name || '未知'
          let html = `<div style="font-weight:bold; border-bottom:1px solid #eee; padding-bottom:5px; margin-bottom:5px;">
                        ${params.name} <span style="font-weight:normal; font-size:12px; color:#999">(${categoryName})</span>
                      </div>`
          const ignore = ['id', 'name', 'x', 'y', 'symbolSize', 'category', 'value', 'label', 'itemStyle', 'emphasis']
          Object.keys(params.data).forEach((key) => {
            if (!ignore.includes(key) && params.data[key] !== null && typeof params.data[key] !== 'object') {
              html += `<div style="font-size:12px; color:#666; line-height: 1.5">
                        <span style="color:#999">${key}:</span> ${params.data[key]}
                      </div>`
            }
          })
          return html
        }
        if (params.dataType === 'edge') {
          const relation = params.data.relation || params.data.label || '关联'
          return `${params.data.source} --[${relation}]--> ${params.data.target}`
        }
        return params.name
      },
    },
    legend: {
      data: categories.map((c) => c.name),
      top: 10,
      left: 'center',
      type: 'scroll',
      orient: 'horizontal',
      itemGap: 15,
      textStyle: { color: '#666' },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: nodes,
        links,
        categories,
        roam: true,
        draggable: true,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [4, 8],
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 1,
          shadowBlur: 0,
        },
        label: {
          position: 'right',
          formatter: '{b}',
          color: '#333',
          show: true,
        },
        // 淡出：只变暗，不消失标签
        blur: {
          itemStyle: { opacity: 0.6 },
          lineStyle: { opacity: 0.1 },
          label: { show: true, color: '#ccc' },
        },
        lineStyle: {
          color: 'source',
          curveness: 0.2,
          opacity: 0.5,
          width: 1.5,
        },
        emphasis: {
          focus: 'adjacency',
          scale: false, // 禁止缩放，避免忽大忽小
          itemStyle: {
            borderColor: '#333',
            borderWidth: 2,
            opacity: 1,
          },
          lineStyle: {
            width: 2.5,
            opacity: 1,
          },
          label: { show: true, color: '#000', fontWeight: 'bold' },
        },
        force: {
          repulsion: 500,
          edgeLength: [80, 150],
          gravity: 0.1,
          friction: 0.6,
        },
      },
    ],
  }

  chartInstance.value.setOption(option, { notMerge: true })
}

// 搜索下拉筛选
const filterMethod = (query) => {
  if (query !== '') {
    searchLoading.value = true
    setTimeout(() => {
      searchLoading.value = false
      filteredOptions.value = allOptions.value
        .filter((item) => item.name.toLowerCase().includes(query.toLowerCase()))
        .slice(0, 50)
    }, 150)
  } else {
    filteredOptions.value = allOptions.value.slice(0, 50)
  }
}

// 处理搜索
const handleSearch = (val) => {
  if (!val) {
    resetToFullGraph()
    return
  }
  const target = fullGraphData.nodes.find((n) => n.id === val)
  if (!target) return
  searchTargetName.value = target.name
  isFiltered.value = true
  loading.value = true
  const { nodes, links } = getSubGraph(val, hopCount.value || 3)
  renderChart(nodes, links, fullGraphData.categories)
  ElMessage.success(`已提取 ${hopCount.value} 跳子图：节点 ${nodes.length} / 边 ${links.length}`)
  loading.value = false
}

const resetToFullGraph = () => {
  isFiltered.value = false
  searchTargetId.value = ''
  searchTargetName.value = ''
  filteredOptions.value = allOptions.value.slice(0, 50)
  renderChart(fullGraphData.nodes, fullGraphData.links, fullGraphData.categories)
}

// 加载数据
const loadFromApi = async () => {
  loading.value = true
  try {
    const resp = await getGraphData()
    const { nodes, links, categories } = normalizeApiData(resp)
    fullGraphData.nodes = nodes
    fullGraphData.links = links
    fullGraphData.categories = categories
    buildAdjacencyMap(links)

    allOptions.value = nodes.map((n) => ({
      id: n.id,
      name: n.name,
      categoryName: categories[n.category]?.name || '',
    }))
    filteredOptions.value = allOptions.value.slice(0, 50)

    resetToFullGraph()
  } catch (err) {
    console.error(err)
    ElMessage.error('图谱加载失败')
  } finally {
    loading.value = false
  }
}

const initChart = () => {
  if (chartRef.value) {
    chartInstance.value = echarts.init(chartRef.value)
  }
}

const resetZoom = () => chartInstance.value?.dispatchAction({ type: 'restore' })

let resizeObserver = null

onMounted(() => {
  initChart()
  loadFromApi()
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => chartInstance.value?.resize())
    resizeObserver.observe(chartRef.value)
  }
})

onBeforeUnmount(() => {
  if (chartInstance.value) chartInstance.value.dispose()
  if (resizeObserver) resizeObserver.disconnect()
})
</script>

<style scoped>
.graph-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.header {
  padding: 10px 20px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  z-index: 10;
}

.title {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.title h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.search-select {
  width: 260px;
}

.chart-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  width: 100%;
  background-color: #fdfdfd;
}

.chart-dom {
  width: 100%;
  height: 100%;
  min-height: 520px;
  padding-top: 10px;
  box-sizing: border-box;
}

.hop-input {
  width: 110px;
}

.hop-label {
  font-size: 12px;
  color: #666;
  margin-right: 4px;
}

.hint {
  font-size: 12px;
  color: #8b8f97;
  margin-right: 8px;
}
</style>
