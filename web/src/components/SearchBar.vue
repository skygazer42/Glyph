<template>
  <div class="search-bar">
    <el-input
      v-model="searchValue"
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

      <template #append v-if="showButton">
        <el-button
          :type="buttonType"
          :loading="loading"
          @click="handleSearch"
          :disabled="disabled || (!allowEmpty && !searchValue)"
        >
          {{ buttonText }}
        </el-button>
      </template>
    </el-input>

    <!-- Advanced filters -->
    <el-collapse-transition>
      <div v-if="showFilters && filters.length > 0" class="search-filters">
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
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              @change="handleFilterChange"
            />

            <!-- Number range filter -->
            <div v-else-if="filter.type === 'range'" class="range-filter">
              <el-input-number
                v-model="filterValues[`${filter.key}_min`]"
                :placeholder="filter.minPlaceholder || '最小值'"
                :size="size"
                :min="filter.min"
                :max="filter.max"
                @change="handleFilterChange"
              />
              <span class="range-separator">-</span>
              <el-input-number
                v-model="filterValues[`${filter.key}_max`]"
                :placeholder="filter.maxPlaceholder || '最大值'"
                :size="size"
                :min="filter.min"
                :max="filter.max"
                @change="handleFilterChange"
              />
            </div>

            <!-- Switch type filter -->
            <el-switch
              v-else-if="filter.type === 'switch'"
              v-model="filterValues[filter.key]"
              :active-text="filter.activeText"
              :inactive-text="filter.inactiveText"
              @change="handleFilterChange"
            />
          </div>
        </div>

        <div class="filters-actions">
          <el-button size="small" @click="resetFilters">重置筛选</el-button>
          <el-button size="small" type="primary" @click="handleSearch">
            应用筛选
          </el-button>
        </div>
      </div>
    </el-collapse-transition>

    <!-- Quick search suggestions -->
    <transition name="el-fade-in">
      <div
        v-if="showSuggestions && suggestions.length > 0 && searchValue"
        class="search-suggestions"
      >
        <div
          v-for="(item, index) in suggestions"
          :key="index"
          class="suggestion-item"
          @click="selectSuggestion(item)"
        >
          <el-icon><Search /></el-icon>
          <span v-html="highlightMatch(item)"></span>
        </div>
      </div>
    </transition>

    <!-- Search history -->
    <transition name="el-fade-in">
      <div
        v-if="showHistory && searchHistory.length > 0 && !searchValue"
        class="search-history"
      >
        <div class="history-header">
          <span>搜索历史</span>
          <el-button text size="small" @click="clearHistory">清空</el-button>
        </div>
        <div class="history-list">
          <el-tag
            v-for="(item, index) in searchHistory"
            :key="index"
            closable
            @close="removeHistoryItem(index)"
            @click="selectHistory(item)"
          >
            {{ item }}
          </el-tag>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
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

const searchValue = ref(props.modelValue)
const filterValues = ref({})
const searchHistory = ref(loadHistory())
let debounceTimer = null

// Watch for external model value changes
watch(() => props.modelValue, (newVal) => {
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
  if (!props.allowEmpty && !searchValue.value) return

  const searchParams = {
    query: searchValue.value,
    filters: { ...filterValues.value }
  }

  emit('search', searchParams)

  // Add to history if enabled
  if (props.showHistory && searchValue.value) {
    addToHistory(searchValue.value)
  }
}

const handleClear = () => {
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
  if (!searchValue.value) return text
  const regex = new RegExp(`(${searchValue.value})`, 'gi')
  return text.replace(regex, '<strong>$1</strong>')
}

// History management
const addToHistory = (query) => {
  const history = [...searchHistory.value]
  const index = history.indexOf(query)

  if (index > -1) {
    history.splice(index, 1)
  }

  history.unshift(query)

  if (history.length > props.maxHistory) {
    history.pop()
  }

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
    return history ? JSON.parse(history) : []
  } catch {
    return []
  }
}

function saveHistory(history) {
  try {
    localStorage.setItem('search-history', JSON.stringify(history))
  } catch {
    // Handle storage error
  }
}

// Expose methods
defineExpose({
  search: handleSearch,
  clear: handleClear,
  resetFilters,
  focus: () => {
    // Focus the input element
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
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.suggestion-item:hover {
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

.history-list .el-tag {
  cursor: pointer;
}

.history-list .el-tag:hover {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
</style>