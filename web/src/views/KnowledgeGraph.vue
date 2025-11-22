<template>
  <div class="graph-page">
    <div class="header">
      <div class="title">
        <h3>知识图谱可视化</h3>
        <el-tag size="small" type="info">数据源：resources/data/lightrag/graph_chunk_entity_relation.graphml</el-tag>
        <el-tag v-if="statsText" size="small" type="success">{{ statsText }}</el-tag>
      </div>
      <div class="actions">
        <el-button :loading="loading" :icon="Refresh" @click="loadFromApi">刷新</el-button>
        <el-button @click="resetZoom">复位视图</el-button>
      </div>
    </div>

    <div class="chart-container" v-loading="loading" element-loading-text="正在渲染图谱...">
      <div v-if="!hasData" class="empty-state">
        <p>自动加载后端图谱数据失败，请点击“刷新”重试</p>
      </div>
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
const hasData = ref(false)
const stats = ref({ nodes: 0, links: 0 })
const statsText = computed(() =>
  stats.value.nodes ? `节点 ${stats.value.nodes} | 边 ${stats.value.links}` : ''
)

const renderChart = (nodes, links) => {
  if (!chartInstance.value) initChart()

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.dataType === 'node') {
          let html = `<div style="font-weight:bold">${params.name}</div>`
          const ignore = ['id', 'name', 'x', 'y', 'symbolSize', 'category', 'value']
          Object.keys(params.data).forEach((key) => {
            if (!ignore.includes(key) && typeof params.data[key] !== 'object') {
              html += `<div style="font-size:12px; color:#ccc">${key}: ${params.data[key]}</div>`
            }
          })
          return html
        }
        return params.name
      },
    },
    animationDuration: 1200,
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: nodes,
        links,
        roam: true,
        draggable: true,
        label: {
          position: 'right',
          formatter: '{b}',
        },
        lineStyle: {
          color: 'source',
          curveness: 0.3,
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 4 },
        },
        force: {
          repulsion: 300,
          edgeLength: 120,
          gravity: 0.1,
        },
      },
    ],
  }

  chartInstance.value.setOption(option, true)
}

const normalizeApiData = (resp) => {
  const data = resp?.data || resp || {}
  const rawNodes = Array.isArray(data.nodes) ? data.nodes : []
  const rawLinks = Array.isArray(data.links) ? data.links : []

  const nodes = rawNodes.map((n, idx) => {
    const id = String(n.id ?? idx)
    const name = n.label ?? n.name ?? n.title ?? id
    return {
      id,
      name,
      value: 1,
      category: 0,
      ...n,
      symbolSize: 20,
      label: { show: name.length < 8 },
    }
  })

  const links = rawLinks.map((l, idx) => ({
    source: String(l.source ?? l.src ?? l.from ?? l.u ?? idx),
    target: String(l.target ?? l.dst ?? l.to ?? l.v ?? idx),
    label: { show: false },
    ...l,
  }))

  return { nodes, links }
}

const loadFromApi = async () => {
  loading.value = true
  hasData.value = false
  try {
    const resp = await getGraphData()
    const { nodes, links } = normalizeApiData(resp)
    if (!nodes.length) throw new Error('图谱数据为空')
    stats.value = { nodes: nodes.length, links: links.length }
    renderChart(nodes, links)
    hasData.value = true
    ElMessage.success('图谱加载成功')
  } catch (err) {
    console.error(err)
    ElMessage.error(err.message || '图谱加载失败')
  } finally {
    loading.value = false
  }
}

const initChart = () => {
  if (chartRef.value) {
    chartInstance.value = echarts.init(chartRef.value)
  }
}

const resetZoom = () => {
  if (chartInstance.value) {
    chartInstance.value.dispatchAction({ type: 'restore' })
  }
}

let resizeObserver = null

onMounted(() => {
  initChart()
  loadFromApi()
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => {
      chartInstance.value?.resize()
    })
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
  padding: 12px 20px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #f8f9fa;
}

.title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.actions {
  display: flex;
  gap: 10px;
}

.chart-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  width: 100%;
}

.chart-dom {
  width: 100%;
  height: 100%;
  min-height: 520px;
}

.empty-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  pointer-events: none;
}
</style>
