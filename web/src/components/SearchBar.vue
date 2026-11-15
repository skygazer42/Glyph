<template>
  <div class="search-bar">
    <el-input
      ref="searchInput"
      v-model="searchValue"
      :aria-label="placeholder"
      :size="size"
      :placeholder="placeholder"
      :clearable="clearable"
      :disabled="disabled"
      @input="handleInput"
      @clear="handleClear"
      @keyup.enter="handleSearch"
      class="search-input"
    >
      <template #prefix>
        <el-icon><Search /></el-icon>
      </template>

      <template
        #append
        v-if="showButton"
      >
        <el-button
          :type="buttonType"
          :loading="loading"
          @click="handleSearch"
          :disabled="disabled || (!allowEmpty && searchValue === '')"
        >
          {{ buttonText }}
        </el-button>
      </template>
    </el-input>

    <!-- Advanced filters -->
    <el-collapse-transition>
      <div
        v-if="showFilters && filters.length > 0"
        class="search-filters"
      >
        <div class="filters-row">
          <div
            v-for="filter in filters"
            :key="filter.key"
            class="filter-item"
          >
            <span class="filter-label">{{ filter.label }}:</span>

            <!-- Select type filter -->
            <el-select
              v-if="filter.type === 'select'"
              v-model="filterValues[filter.key]"
              :placeholder="filter.placeholder || `选择${filter.label}`"
              :size="size"
              :aria-label="filter.label"
              :disabled="disabled"
              clearable
              @change="handleFilterChange"
            >
              <el-option
                v-for="option in filter.options"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>

            <!-- Date range filter -->
            <el-date-picker
              v-else-if="filter.type === 'daterange'"
              v-model="filterValues[filter.key]"
              type="daterange"
              :size="size"
              :aria-label="filter.label"
              :disabled="disabled"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              @change="handleFilterChange"
            />

            <!-- Number range filter -->
            <div
              v-else-if="filter.type === 'range'"
              class="range-filter"
            >
              <el-input-number
                v-model="filterValues[`${filter.key}_min`]"
                :placeholder="filter.minPlaceholder || '最小值'"
                :size="size"
                :aria-label="`${filter.label}最小值`"
                :disabled="disabled"
                :min="filter.min"
                :max="filter.max"
                @change="handleFilterChange"
              />
              <span class="range-separator">-</span>
              <el-input-number
                v-model="filterValues[`${filter.key}_max`]"
                :placeholder="filter.maxPlaceholder || '最大值'"
                :size="size"
                :aria-label="`${filter.label}最大值`"
                :disabled="disabled"
                :min="filter.min"
                :max="filter.max"
                @change="handleFilterChange"
              />
            </div>

            <!-- Switch type filter -->
            <el-switch
              v-else-if="filter.type === 'switch'"
              v-model="filterValues[filter.key]"
              :aria-label="filter.label"
              :disabled="disabled"
              :active-text="filter.activeText"
              :inactive-text="filter.inactiveText"
              @change="handleFilterChange"
            />
          </div>
        </div>

        <div class="filters-actions">
          <el-button
            size="small"
            :disabled="disabled"
            @click="resetFilters"
          >重置筛选</el-button>
          <el-button
            size="small"
            type="primary"
            :disabled="disabled || loading"
            @click="handleSearch"
          >
            应用筛选
          </el-button>
        </div>
      </div>
    </el-collapse-transition>

    <!-- Quick search suggestions -->
    <transition name="el-fade-in">
      <div
        v-if="showSuggestions && suggestionItems.length > 0 && searchValue !== ''"
        class="search-suggestions"
      >
        <button
          type="button"
          v-for="item in suggestionItems"
          :key="item"
          class="suggestion-item"
          :disabled="disabled || loading"
          @click="selectSuggestion(item)"
        >
          <el-icon><Search /></el-icon>
          <span>
            <template
              v-for="(part, partIndex) in highlightMatch(item)"
              :key="partIndex"
            >
              <strong v-if="part.match">{{ part.text }}</strong>
              <template v-else>{{ part.text }}</template>
            </template>
          </span>
        </button>
      </div>
    </transition>

    <!-- Search history -->
    <transition name="el-fade-in">
      <div
        v-if="showHistory && searchHistory.length > 0 && searchValue === ''"
        class="search-history"
      >
        <div class="history-header">
          <span>搜索历史</span>
          <el-button
            text
            size="small"
            @click="clearHistory"
          >清空</el-button>
        </div>
        <div class="history-list">
          <el-tag
            v-for="(item, index) in searchHistory"
            :key="item"
            closable
            @close="removeHistoryItem(index)"
          >
            <button
              type="button"
              class="history-query"
              :disabled="disabled || loading"
              @click.stop="selectHistory(item)"
            >{{ item }}</button>
          </el-tag>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { Search } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: '请输入搜索内容'
  },
  size: {
    type: String,
    default: 'default',
    validator: (value) => ['large', 'default', 'small'].includes(value)
  },
  clearable: {
    type: Boolean,
    default: true
  },
  disabled: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  },
  showButton: {
    type: Boolean,
    default: true
  },
  buttonText: {
    type: String,
    default: '搜索'
  },
  buttonType: {
    type: String,
    default: 'primary'
  },
  allowEmpty: {
    type: Boolean,
    default: false
  },
  debounce: {
    type: Number,
    default: 300
  },
  showFilters: {
    type: Boolean,
    default: false
  },
  filters: {
    type: Array,
    default: () => []
    // Example:
    // [
    //   { key: 'type', label: '类型', type: 'select', options: [{label: '全部', value: ''}] },
    //   { key: 'date', label: '日期', type: 'daterange' },
    //   { key: 'price', label: '价格', type: 'range', min: 0, max: 10000 }
    // ]
  },
  showSuggestions: {
    type: Boolean,
    default: false
  },
  suggestions: {
    type: Array,
    default: () => []
  },
  showHistory: {
    type: Boolean,
    default: false
  },
  maxHistory: {
    type: Number,
    default: 10
  }
})

const emit = defineEmits(['update:modelValue', 'search', 'input', 'clear', 'filter-change'])

const suggestionItems = computed(() => [...new Set(props.suggestions)])
const searchInput = ref(null)
const searchValue = ref(props.modelValue)
const filterValues = ref({})
const searchHistory = ref(loadHistory())
let debounceTimer = null

// Watch for external model value changes
watch(() => props.modelValue, (newVal) => {
  clearTimeout(debounceTimer)
  searchValue.value = newVal
})

// Watch for internal search value changes
watch(searchValue, (newVal) => {
  emit('update:modelValue', newVal)
})

const handleInput = () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    emit('input', searchValue.value)
  }, props.debounce)
}

const handleSearch = () => {
  if (props.disabled || props.loading || (!props.allowEmpty && searchValue.value === '')) {
    return
  }
  clearTimeout(debounceTimer)

  const searchParams = {
    query: searchValue.value,
    filters: { ...filterValues.value }
  }

  emit('search', searchParams)

  // Add to history if enabled
  if (props.showHistory && searchValue.value !== '') {
    addToHistory(searchValue.value)
  }
}

const handleClear = () => {
  clearTimeout(debounceTimer)
  searchValue.value = ''
  emit('clear')
}

const handleFilterChange = () => {
  emit('filter-change', filterValues.value)
}

const resetFilters = () => {
  filterValues.value = {}
  props.filters.forEach(filter => {
    if (filter.type === 'switch') {
      filterValues.value[filter.key] = false
    }
  })
  handleFilterChange()
}

const selectSuggestion = (suggestion) => {
  searchValue.value = suggestion
  handleSearch()
}

const highlightMatch = (text) => {
  const parts = []
  const query = searchValue.value.toLowerCase()
  let offset = 0
  let index = query !== '' ? text.toLowerCase().indexOf(query) : -1

  while (index !== -1) {
    parts.push({ text: text.slice(offset, index), match: false })
    parts.push({ text: text.slice(index, index + query.length), match: true })
    offset = index + query.length
    index = text.toLowerCase().indexOf(query, offset)
  }

  parts.push({ text: text.slice(offset), match: false })
  return parts
}

// History management
const addToHistory = (query) => {
  const history = [...searchHistory.value]
  const index = history.indexOf(query)

  if (index > -1) {
    history.splice(index, 1)
  }

  history.unshift(query)

  history.splice(Math.max(0, props.maxHistory))

  searchHistory.value = history
  saveHistory(history)
}

const selectHistory = (item) => {
  searchValue.value = item
  handleSearch()
}

const removeHistoryItem = (index) => {
  searchHistory.value.splice(index, 1)
  saveHistory(searchHistory.value)
}

const clearHistory = () => {
  searchHistory.value = []
  saveHistory([])
}

function loadHistory() {
  try {
    const history = localStorage.getItem('search-history')
    const parsedHistory = history ? JSON.parse(history) : []
    return Array.isArray(parsedHistory)
      ? [...new Set(parsedHistory.filter(item => typeof item === 'string'))].slice(0, Math.max(0, props.maxHistory))
      : []
  } catch {
    return []
  }
}

function saveHistory(history) {
  try {
    localStorage.setItem('search-history', JSON.stringify(history))
  } catch {
    // 浏览器持久化不可用时，保留当前页面内的搜索历史。
  }
}

onUnmounted(() => clearTimeout(debounceTimer))

// Expose methods
defineExpose({
  search: handleSearch,
  clear: handleClear,
  resetFilters,
  focus: () => {
    searchInput.value?.focus()
  }
})
</script>

<style scoped>
.search-bar {
  position: relative;
  width: 100%;
}

.search-input {
  width: 100%;
}

.search-filters {
  margin-top: 12px;
  padding: 16px;
  background-color: var(--el-fill-color-lighter);
  border-radius: var(--el-border-radius-base);
  border: 1px solid var(--el-border-color-lighter);
}

.filters-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 12px;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
  white-space: nowrap;
}

.range-filter {
  display: flex;
  align-items: center;
  gap: 8px;
}

.range-separator {
  color: var(--el-text-color-placeholder);
}

.filters-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.search-suggestions {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background-color: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: var(--el-border-radius-base);
  box-shadow: var(--el-box-shadow-light);
  z-index: 2000;
  max-height: 300px;
  overflow-y: auto;
}

.suggestion-item {
  width: 100%;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.suggestion-item:hover,
.suggestion-item:focus-visible {
  background-color: var(--el-fill-color-light);
}

.suggestion-item :deep(strong) {
  color: var(--el-color-primary);
  font-weight: 600;
}

.search-history {
  margin-top: 12px;
  padding: 12px;
  background-color: var(--el-fill-color-blank);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: var(--el-border-radius-base);
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.history-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.history-query {
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.history-list .el-tag {
  cursor: pointer;
}

.history-list .el-tag:hover {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
</style>