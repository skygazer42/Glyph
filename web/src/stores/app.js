// Pinia Store - 集中状态管理
import { defineStore } from 'pinia'
import { ref, computed, onScopeDispose } from 'vue'
import { ElMessage } from 'element-plus'

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
    generatedRuleId: '',
    generatedInputs: [],
    savedRule: null,
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
  const hasGeneratedDSL = computed(() => dslState.value.generatedYAML.length > 0)
  const documentCount = computed(() => kbState.value.documents.length)
  let notificationTimer = null
  onScopeDispose(() => {
    clearTimeout(notificationTimer)
  })

  // 方法
  function setLoading(value) {
    loading.value = value
  }

  function showNotification(type, message, duration = 3000) {
    clearTimeout(notificationTimer)
    ElMessage({ type, message, duration })
    notification.value = {
      show: true,
      type,
      message
    }
    notificationTimer = setTimeout(() => {
      notification.value.show = false
      notificationTimer = null
    }, duration)
  }

  function resetDSLState() {
    dslState.value.inputText = ''
    dslState.value.generatedYAML = ''
    dslState.value.generatedRuleId = ''
    dslState.value.generatedInputs = []
    dslState.value.savedRule = null
    dslState.value.generating = false
  }

  function resetKBState() {
    kbState.value.searchQuery = ''
    kbState.value.searchResults = []
    kbState.value.selectedDoc = null
  }

  function resetPrivateState() {
    resetDSLState()
    dslState.value.dslList = []
    dslState.value.showExamples = false
    resetKBState()
    kbState.value.documents = []
    kbState.value.uploading = false
    loading.value = false
    clearTimeout(notificationTimer)
    notification.value = { show: false, type: 'success', message: '' }
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
    resetKBState,
    resetPrivateState
  }
})
