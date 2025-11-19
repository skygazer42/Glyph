<template>
  <div class="text2sql-result" v-if="hasRows || hasError">
    <div class="text2sql-header">
      <el-tag size="small" type="success">Text2SQL</el-tag>
      <span class="text2sql-summary">
        <span v-if="hasError">SQL 执行失败</span>
        <span v-else>返回 {{ rowCount }} 条记录</span>
      </span>
    </div>

    <div v-if="sql" class="text2sql-sql">
      <span class="text2sql-label">SQL：</span>
      <code class="text2sql-code">{{ sql }}</code>
    </div>

    <div v-if="hasError" class="text2sql-error">
      <el-alert
        type="error"
        :closable="false"
        show-icon
        :title="errorMessage"
      />
    </div>

    <div v-else-if="hasRows">
      <div class="text2sql-table">
        <el-table
          :data="previewRows"
          size="small"
          border
          style="width: 100%"
        >
          <el-table-column
            v-for="col in columns"
            :key="col"
            :prop="col"
            :label="col"
          />
        </el-table>
        <div v-if="rowCount > maxPreview" class="text2sql-hint">
          仅预览前 {{ maxPreview }} 条，其余 {{ rowCount - maxPreview }} 条已省略。
        </div>
      </div>

      <div v-if="chartConfig" class="text2sql-chart">
        <div class="text2sql-chart-header">
          <span class="text2sql-label">可视化：</span>
          <span class="text2sql-chart-desc">
            按 {{ chartConfig.categoryKey }} 统计 {{ chartConfig.valueKey }}
          </span>
        </div>
        <div class="bar-chart">
          <div
            v-for="row in chartConfig.rows"
            :key="row[chartConfig.categoryKey]"
            class="bar-row"
          >
            <div class="bar-label">
              {{ row[chartConfig.categoryKey] }}
            </div>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{ width: row[chartConfig.valueKey] / chartConfig.maxValue * 100 + '%' }"
              />
              <span class="bar-value">
                {{ row[chartConfig.valueKey] }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  metadata: {
    type: Object,
    required: true
  }
})

const rows = computed(() => props.metadata?.rows || [])
const sql = computed(() => props.metadata?.sql || '')
const errorMessage = computed(() => props.metadata?.error || '')
const hasError = computed(() => !!errorMessage.value)
const hasRows = computed(() => Array.isArray(rows.value) && rows.value.length > 0)
const rowCount = computed(() => (hasRows.value ? rows.value.length : 0))

const maxPreview = 20
const previewRows = computed(() => {
  if (!hasRows.value) return []
  return rows.value.slice(0, maxPreview)
})

const columns = computed(() => {
  if (!hasRows.value) return []
  const first = rows.value[0] || {}
  return Object.keys(first)
})

const chartConfig = computed(() => {
  if (!hasRows.value) return null
  if (!columns.value.length) return null

  const cols = columns.value
  const sampleRows = rows.value

  const isNumberColumn = (key) =>
    sampleRows.every((row) => typeof row[key] === 'number')

  const isStringColumn = (key) =>
    sampleRows.every((row) => typeof row[key] === 'string')

  const numericCols = cols.filter(isNumberColumn)
  const stringCols = cols.filter(isStringColumn)

  if (!numericCols.length || !stringCols.length) {
    return null
  }

  const categoryKey = stringCols[0]
  const valueKey = numericCols[0]

  const chartRows = sampleRows.slice(0, maxPreview)
  const maxValue =
    chartRows.reduce((max, row) => {
      const v = row[valueKey]
      return typeof v === 'number' && v > max ? v : max
    }, 0) || 0

  if (!maxValue) {
    return null
  }

  return {
    categoryKey,
    valueKey,
    rows: chartRows,
    maxValue
  }
})
</script>

<style scoped>
.text2sql-result {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.text2sql-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.text2sql-summary {
  font-size: 12px;
  color: #4b5563;
}

.text2sql-sql {
  margin-bottom: 6px;
  font-size: 12px;
  display: flex;
  align-items: flex-start;
  gap: 4px;
}

.text2sql-label {
  font-weight: 500;
  color: #4b5563;
}

.text2sql-code {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  background: #0f172a;
  color: #e5e7eb;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

.text2sql-error {
  margin-top: 4px;
}

.text2sql-table {
  margin-top: 4px;
}

.text2sql-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}

.text2sql-chart {
  margin-top: 10px;
}

.text2sql-chart-header {
  margin-bottom: 4px;
  font-size: 12px;
  color: #4b5563;
  display: flex;
  align-items: center;
  gap: 4px;
}

.text2sql-chart-desc {
  color: #6b7280;
}

.bar-chart {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 4px;
}

.bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar-label {
  flex: 0 0 120px;
  font-size: 12px;
  color: #4b5563;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bar-track {
  position: relative;
  flex: 1;
  height: 16px;
  border-radius: 999px;
  background: #e5e7eb;
  overflow: hidden;
}

.bar-fill {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  background: linear-gradient(90deg, #6366f1, #22c55e);
  transition: width 0.3s ease;
}

.bar-value {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 11px;
  color: #111827;
}
</style>

