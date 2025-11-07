// Pinia Store - 集中状态管理
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  // 状态
  const loading = ref(false)
  const currentRoute = ref('/dsl')
  const notification = ref({
    show: false,
    type: 'success',
    message: ''
  })

  // DSL相关状态
  const dslState = ref({
    inputText: '',
    generatedYAML: '',
    dslList: [],
    generating: false,
    showExamples: false
  })

  // 知识库相关状态
  const kbState = ref({
    documents: [],
    searchQuery: '',
    searchResults: [],
    selectedDoc: null,
    uploading: false
  })

  // 计算属性
  const hasGeneratedDSL = computed(() => !!dslState.value.generatedYAML)
  const documentCount = computed(() => kbState.value.documents.length)

  // 方法
  function setLoading(value) {
    loading.value = value
  }

  function showNotification(type, message, duration = 3000) {
    notification.value = {
      show: true,
      type,
      message
    }
    setTimeout(() => {
      notification.value.show = false
    }, duration)
  }

  function resetDSLState() {
    dslState.value.inputText = ''
    dslState.value.generatedYAML = ''
    dslState.value.generating = false
  }

  function resetKBState() {
    kbState.value.searchQuery = ''
    kbState.value.searchResults = []
    kbState.value.selectedDoc = null
  }

  return {
    // 状态
    loading,
    currentRoute,
    notification,
    dslState,
    kbState,

    // 计算属性
    hasGeneratedDSL,
    documentCount,

    // 方法
    setLoading,
    showNotification,
    resetDSLState,
    resetKBState
  }
})