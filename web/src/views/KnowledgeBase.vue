<template>
  <div class="knowledge-base">
    <el-card class="page-card">
      <template #header>
        <div class="page-header">
          <h2 class="page-title">知识库管理系统</h2>
          <div class="page-actions">
            <el-button @click="rebuildIndex" :loading="rebuilding">
              重建索引
            </el-button>
            <el-button type="primary" @click="loadStats">
              刷新统计
            </el-button>
          </div>
        </div>
      </template>

      <!-- 统计信息 -->
      <div v-if="appStore.kbState.documents.length > 0" class="stats-cards">
        <el-row :gutter="20">
          <el-col :xs="12" :sm="6">
            <div class="stat-card">
              <div class="stat-value">{{ stats.total_documents || 0 }}</div>
              <div class="stat-label">文档总数</div>
            </div>
          </el-col>
          <el-col :xs="12" :sm="6">
            <div class="stat-card">
              <div class="stat-value">{{ stats.total_chunks || 0 }}</div>
              <div class="stat-label">文本块数</div>
            </div>
          </el-col>
          <el-col :xs="12" :sm="6">
            <div class="stat-card">
              <div class="stat-value">{{ stats.embedding_count || 0 }}</div>
              <div class="stat-label">已嵌入</div>
            </div>
          </el-col>
          <el-col :xs="12" :sm="6">
            <div class="stat-card">
              <div class="stat-value">{{ formatBytes(stats.total_size || 0) }}</div>
              <div class="stat-label">存储空间</div>
            </div>
          </el-col>
        </el-row>
      </div>

      <el-tabs v-model="activeTab" class="main-tabs">
        <!-- 文档管理标签页 -->
        <el-tab-pane label="文档管理" name="documents">
          <div class="tab-content">
            <!-- 上传区域 -->
            <el-card shadow="never" class="upload-card">
              <FileUploader
                ref="documentUploader"
                :upload-url="'/api/knowledge/upload'"
                :multiple="true"
                :limit="20"
                :accept="'.txt,.doc,.docx,.pdf,.md'"
                :max-size="50 * 1024 * 1024"
                :show-custom-list="true"
                tip-text="支持 TXT、Word、PDF、Markdown 格式，单个文件最大 50MB"
                @success="handleUploadSuccess"
                @error="handleUploadError"
              />

              <div v-if="uploadedFiles.length > 0" class="batch-actions">
                <el-button
                  type="primary"
                  @click="batchEmbed"
                  :loading="batchEmbedding"
                >
                  批量嵌入所有文档
                </el-button>
                <el-button @click="clearUploaded">清空上传列表</el-button>
              </div>
            </el-card>

            <!-- 文档列表 -->
            <el-card shadow="never" style="margin-top: 20px">
              <template #header>
                <div class="card-header">
                  <h3>文档列表</h3>
                  <div class="header-actions">
                    <SearchBar
                      v-model="documentSearch"
                      placeholder="搜索文档..."
                      :show-button="false"
                      size="small"
                      @input="filterDocuments"
                    />
                    <el-button size="small" @click="loadDocuments">
                      刷新
                    </el-button>
                  </div>
                </div>
              </template>

              <el-table
                :data="filteredDocuments"
                style="width: 100%"
                v-loading="tableLoading"
              >
                <el-table-column type="selection" width="55" />
                <el-table-column prop="doc_id" label="文档 ID" width="200" />
                <el-table-column prop="name" label="文档名称" show-overflow-tooltip />
                <el-table-column prop="doc_type" label="类型" width="100">
                  <template #default="scope">
                    <el-tag size="small" :type="getTypeColor(scope.row.doc_type)">
                      {{ scope.row.doc_type || 'text' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="size" label="大小" width="100">
                  <template #default="scope">
                    {{ formatBytes(scope.row.size) }}
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="100" align="center">
                  <template #default="scope">
                    <el-tag
                      :type="scope.row.embedded ? 'success' : 'warning'"
                      size="small"
                    >
                      {{ scope.row.embedded ? '已嵌入' : '待嵌入' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="created_at" label="上传时间" width="180">
                  <template #default="scope">
                    {{ formatDate(scope.row.created_at) }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="180" fixed="right">
                  <template #default="scope">
                    <el-button-group size="small">
                      <el-button
                        v-if="!scope.row.embedded"
                        type="primary"
                        @click="embedDocument(scope.row)"
                        :loading="embeddings[scope.row.doc_id]"
                      >
                        嵌入
                      </el-button>
                      <el-button @click="viewDocument(scope.row)">
                        查看
                      </el-button>
                      <el-button type="danger" @click="deleteDocument(scope.row)">
                        删除
                      </el-button>
                    </el-button-group>
                  </template>
                </el-table-column>
              </el-table>

              <!-- 分页 -->
              <el-pagination
                v-if="appStore.kbState.documents.length > pageSize"
                v-model:current-page="currentPage"
                :page-size="pageSize"
                :total="appStore.kbState.documents.length"
                layout="total, prev, pager, next, sizes"
                :page-sizes="[10, 20, 50, 100]"
                @size-change="handleSizeChange"
                style="margin-top: 20px; justify-content: center"
              />
            </el-card>
          </div>
        </el-tab-pane>

        <!-- 搜索标签页 -->
        <el-tab-pane label="智能搜索" name="search">
          <div class="tab-content">
            <el-row :gutter="20">
              <!-- 搜索区域 -->
              <el-col :span="10">
                <el-card shadow="never">
                  <template #header>
                    <h3>搜索设置</h3>
                  </template>

                  <SearchBar
                    v-model="appStore.kbState.searchQuery"
                    placeholder="输入搜索内容..."
                    :loading="searching"
                    @search="performSearch"
                    style="margin-bottom: 20px"
                  />

                  <!-- 高级选项 -->
                  <el-form label-width="100px">
                    <el-form-item label="搜索方式">
                      <el-radio-group v-model="searchMode">
                        <el-radio-button label="vector">向量搜索</el-radio-button>
                        <el-radio-button label="keyword">关键词搜索</el-radio-button>
                        <el-radio-button label="hybrid">混合搜索</el-radio-button>
                      </el-radio-group>
                    </el-form-item>

                    <el-form-item label="返回数量">
                      <el-slider
                        v-model="searchOptions.topK"
                        :min="1"
                        :max="50"
                        show-input
                      />
                    </el-form-item>

                    <el-form-item label="相似度阈值" v-if="searchMode !== 'keyword'">
                      <el-slider
                        v-model="searchOptions.threshold"
                        :min="0"
                        :max="1"
                        :step="0.05"
                        :format-tooltip="(val) => `${(val * 100).toFixed(0)}%`"
                        show-input
                      />
                    </el-form-item>

                    <el-form-item label="重排序" v-if="searchMode === 'hybrid'">
                      <el-switch v-model="searchOptions.rerank" />
                    </el-form-item>

                    <el-form-item label="文档类型">
                      <el-select
                        v-model="searchOptions.docType"
                        placeholder="全部类型"
                        clearable
                      >
                        <el-option label="政策文档" value="policy" />
                        <el-option label="操作指南" value="guide" />
                        <el-option label="常见问题" value="faq" />
                        <el-option label="其他" value="other" />
                      </el-select>
                    </el-form-item>
                  </el-form>
                </el-card>
              </el-col>

              <!-- 搜索结果 -->
              <el-col :span="14">
                <el-card shadow="never">
                  <template #header>
                    <div class="card-header">
                      <h3>搜索结果</h3>
                      <el-tag v-if="appStore.kbState.searchResults.length > 0">
                        找到 {{ appStore.kbState.searchResults.length }} 条结果
                      </el-tag>
                    </div>
                  </template>

                  <div
                    v-if="appStore.kbState.searchResults.length > 0"
                    class="search-results"
                  >
                    <div
                      v-for="(result, index) in appStore.kbState.searchResults"
                      :key="index"
                      class="result-item"
                    >
                      <div class="result-header">
                        <span class="result-title">
                          {{ result.metadata?.title || `结果 ${index + 1}` }}
                        </span>
                        <div class="result-meta">
                          <el-tag size="small" type="success">
                            相似度: {{ (result.score * 100).toFixed(1) }}%
                          </el-tag>
                          <el-tag size="small" v-if="result.metadata?.doc_type">
                            {{ result.metadata.doc_type }}
                          </el-tag>
                        </div>
                      </div>
                      <div class="result-content">
                        <p v-html="highlightKeywords(result.text)"></p>
                      </div>
                      <div class="result-footer">
                        <span class="result-source">
                          来源: {{ result.metadata?.source || '未知' }}
                        </span>
                        <el-button
                          text
                          size="small"
                          @click="showDetail(result)"
                        >
                          查看详情
                        </el-button>
                      </div>
                    </div>
                  </div>

                  <el-empty
                    v-else-if="!searching"
                    description="暂无搜索结果"
                    :image-size="100"
                  >
                    <template #extra>
                      <p style="color: var(--el-text-color-secondary); font-size: 14px">
                        请输入搜索内容并点击搜索按钮
                      </p>
                    </template>
                  </el-empty>

                  <div v-else class="loading-container">
                    <el-icon class="is-loading" :size="40">
                      <Loading />
                    </el-icon>
                    <p>正在搜索...</p>
                  </div>
                </el-card>
              </el-col>
            </el-row>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 文档详情对话框 -->
    <el-dialog
      v-model="showDocumentDialog"
      title="文档详情"
      width="800px"
    >
      <el-descriptions :column="1" border>
        <el-descriptions-item label="文档 ID">
          {{ currentDocument?.doc_id }}
        </el-descriptions-item>
        <el-descriptions-item label="文档名称">
          {{ currentDocument?.name }}
        </el-descriptions-item>
        <el-descriptions-item label="文档类型">
          {{ currentDocument?.doc_type }}
        </el-descriptions-item>
        <el-descriptions-item label="文件大小">
          {{ formatBytes(currentDocument?.size) }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ formatDate(currentDocument?.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="嵌入状态">
          <el-tag :type="currentDocument?.embedded ? 'success' : 'warning'">
            {{ currentDocument?.embedded ? '已嵌入' : '待嵌入' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="currentDocument?.content" style="margin-top: 20px">
        <h4>文档内容预览</h4>
        <CodeEditor
          :modelValue="currentDocument.content"
          mode="display"
          language="text"
          :show-copy="true"
        />
      </div>

      <template #footer>
        <el-button @click="showDocumentDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 搜索结果详情对话框 -->
    <el-dialog
      v-model="showResultDialog"
      title="搜索结果详情"
      width="700px"
    >
      <el-descriptions :column="1" border>
        <el-descriptions-item label="相似度分数">
          <el-progress
            :percentage="(currentResult?.score || 0) * 100"
            :format="(percentage) => `${percentage.toFixed(1)}%`"
          />
        </el-descriptions-item>
        <el-descriptions-item label="文档来源">
          {{ currentResult?.metadata?.source || '未知' }}
        </el-descriptions-item>
        <el-descriptions-item label="文档类型">
          {{ currentResult?.metadata?.doc_type || '未知' }}
        </el-descriptions-item>
      </el-descriptions>

      <div style="margin-top: 20px">
        <h4>内容</h4>
        <div class="detail-content">
          {{ currentResult?.text }}
        </div>
      </div>

      <template #footer>
        <el-button @click="showResultDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { knowledgeApi } from '@/api'
import { CodeEditor, FileUploader, SearchBar } from '@/components'

// Store
const appStore = useAppStore()

// Refs
const activeTab = ref('documents')
const documentSearch = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const tableLoading = ref(false)
const searching = ref(false)
const rebuilding = ref(false)
const batchEmbedding = ref(false)
const embeddings = ref({})
const uploadedFiles = ref([])
const documentUploader = ref(null)
const showDocumentDialog = ref(false)
const showResultDialog = ref(false)
const currentDocument = ref(null)
const currentResult = ref(null)

// Search options
const searchMode = ref('hybrid')
const searchOptions = reactive({
  topK: 10,
  threshold: 0.7,
  rerank: true,
  docType: ''
})

// Stats
const stats = reactive({
  total_documents: 0,
  total_chunks: 0,
  embedding_count: 0,
  total_size: 0
})

// Computed
const filteredDocuments = computed(() => {
  let docs = appStore.kbState.documents

  if (documentSearch.value) {
    const query = documentSearch.value.toLowerCase()
    docs = docs.filter(doc =>
      doc.name.toLowerCase().includes(query) ||
      doc.doc_id.toLowerCase().includes(query)
    )
  }

  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return docs.slice(start, end)
})

// Methods
const loadDocuments = async () => {
  tableLoading.value = true
  try {
    const response = await knowledgeApi.listDocuments({
      page: 1,
      page_size: 1000
    })
    appStore.kbState.documents = response.documents || []
  } catch (error) {
    appStore.showNotification('error', `加载文档失败: ${error.message}`)
  } finally {
    tableLoading.value = false
  }
}

const loadStats = async () => {
  try {
    const response = await knowledgeApi.getStats()
    Object.assign(stats, response)
  } catch (error) {
    appStore.showNotification('error', `加载统计失败: ${error.message}`)
  }
}

const handleUploadSuccess = (data) => {
  uploadedFiles.value.push(data.response)
  appStore.showNotification('success', `文档 ${data.file.name} 上传成功`)
  loadDocuments()
  loadStats()
  processUploadedDocument(data.response, data.file.name)
}

const handleUploadError = (data) => {
  appStore.showNotification('error', `文档 ${data.file.name} 上传失败`)
}

const clearUploaded = () => {
  uploadedFiles.value = []
  documentUploader.value?.clearAll()
}

const embedDocument = async (doc) => {
  embeddings.value[doc.doc_id] = true
  try {
    await knowledgeApi.embedDocument(doc.doc_id)
    appStore.showNotification('success', `文档 ${doc.name} 嵌入成功`)
    doc.embedded = true
    loadStats()
  } catch (error) {
    appStore.showNotification('error', `嵌入失败: ${error.message}`)
  } finally {
    embeddings.value[doc.doc_id] = false
  }
}

const processUploadedDocument = async (uploadInfo, fileName) => {
  const docId = uploadInfo?.doc_id
  if (!docId) return
  try {
    appStore.showNotification('info', `正在解析文档 ${fileName} ...`)
    await knowledgeApi.parseDocument(docId)
    appStore.showNotification('info', `正在嵌入文档 ${fileName} ...`)
    await knowledgeApi.embedDocument(docId)
    appStore.showNotification('success', `文档 ${fileName} 解析并嵌入完成`)
    uploadInfo.embedded = true
    loadDocuments()
    loadStats()
  } catch (error) {
    appStore.showNotification('error', `文档 ${fileName} 处理失败: ${error.message}`)
  }
}

const batchEmbed = async () => {
  if (uploadedFiles.value.length === 0) {
    appStore.showNotification('warning', '没有待嵌入的文档')
    return
  }

  batchEmbedding.value = true
  let successCount = 0
  try {
    for (const file of uploadedFiles.value) {
      await knowledgeApi.parseDocument(file.doc_id)
      await knowledgeApi.embedDocument(file.doc_id)
      successCount += 1
    }
    appStore.showNotification('success', `成功嵌入 ${successCount} 个文档`)
    clearUploaded()
    loadDocuments()
    loadStats()
  } catch (error) {
    appStore.showNotification('error', `批量嵌入过程中断在第 ${successCount + 1} 个文档: ${error.message}`)
  } finally {
    batchEmbedding.value = false
  }
}

const deleteDocument = async (doc) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档 "${doc.name}" 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await knowledgeApi.deleteDocument(doc.doc_id)
    appStore.showNotification('success', '文档删除成功')
    loadDocuments()
    loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      appStore.showNotification('error', `删除失败: ${error.message}`)
    }
  }
}

const viewDocument = async (doc) => {
  try {
    const response = await knowledgeApi.getDocument(doc.doc_id)
    currentDocument.value = response
    showDocumentDialog.value = true
  } catch (error) {
    appStore.showNotification('error', `查看失败: ${error.message}`)
  }
}

const performSearch = async (params) => {
  if (!params.query) {
    appStore.showNotification('warning', '请输入搜索内容')
    return
  }

  searching.value = true
  appStore.kbState.searchResults = []

  try {
    let response
    const options = {
      topK: searchOptions.topK,
      filters: searchOptions.docType ? { doc_type: searchOptions.docType } : {},
      rerank: searchOptions.rerank
    }

    if (searchMode.value === 'hybrid') {
      response = await knowledgeApi.hybridSearch(params.query, options)
    } else {
      response = await knowledgeApi.search(params.query, options)
    }

    appStore.kbState.searchResults = response.results || []

    if (appStore.kbState.searchResults.length === 0) {
      appStore.showNotification('info', '未找到相关结果')
    } else {
      appStore.showNotification(
        'success',
        `找到 ${appStore.kbState.searchResults.length} 条相关结果`
      )
    }
  } catch (error) {
    appStore.showNotification('error', `搜索失败: ${error.message}`)
  } finally {
    searching.value = false
  }
}

const rebuildIndex = async () => {
  try {
    await ElMessageBox.confirm(
      '重建索引将重新处理所有文档，可能需要较长时间。是否继续？',
      '重建索引确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    rebuilding.value = true
    await knowledgeApi.rebuildIndex()
    appStore.showNotification('success', '索引重建成功')
    loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      appStore.showNotification('error', `重建失败: ${error.message}`)
    }
  } finally {
    rebuilding.value = false
  }
}

const showDetail = (result) => {
  currentResult.value = result
  showResultDialog.value = true
}

const highlightKeywords = (text) => {
  if (!appStore.kbState.searchQuery) return text
  const keywords = appStore.kbState.searchQuery.split(/\s+/)
  let highlighted = text

  keywords.forEach(keyword => {
    if (keyword) {
      const regex = new RegExp(`(${keyword})`, 'gi')
      highlighted = highlighted.replace(regex, '<mark>$1</mark>')
    }
  })

  return highlighted
}

const filterDocuments = () => {
  currentPage.value = 1
}

const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1
}

const formatBytes = (bytes) => {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let index = 0
  let size = bytes

  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index++
  }

  return `${size.toFixed(2)} ${units[index]}`
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

const getTypeColor = (type) => {
  const colors = {
    pdf: 'danger',
    docx: 'primary',
    doc: 'primary',
    txt: 'info',
    md: 'success'
  }
  return colors[type] || 'info'
}

// Lifecycle
onMounted(() => {
  loadDocuments()
  loadStats()
})
</script>

<style scoped>
.knowledge-base {
  animation: fadeIn 0.4s ease;
}

.page-card {
  background: white;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  border: none;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-title {
  margin: 0;
  font-size: var(--text-2xl);
  font-weight: 700;
  background: var(--primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.page-actions {
  display: flex;
  gap: 12px;
}

/* 统计卡片 */
.stats-cards {
  margin-bottom: var(--spacing-lg);
}

.stat-card {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  padding: var(--spacing-lg);
  border-radius: var(--radius-lg);
  text-align: center;
  border: 1px solid rgba(102, 126, 234, 0.15);
  transition: all var(--transition-base);
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
}

.stat-value {
  font-size: var(--text-3xl);
  font-weight: 700;
  background: var(--primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: var(--spacing-sm);
}

.stat-label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: 500;
}

/* Tabs */
.main-tabs {
  margin-top: 20px;
}

.tab-content {
  padding: 20px 0;
}

/* Cards */
.upload-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-actions :deep(.search-bar) {
  width: 300px;
}

.batch-actions {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--el-border-color-lighter);
  display: flex;
  justify-content: center;
  gap: 12px;
}

/* Search results */
.search-results {
  max-height: 600px;
  overflow-y: auto;
}

.result-item {
  padding: var(--spacing-lg);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  margin-bottom: var(--spacing-md);
  transition: all var(--transition-base);
  background: white;
}

.result-item:hover {
  box-shadow: var(--shadow-lg);
  border-color: var(--primary-color);
  transform: translateY(-2px);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.result-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.result-meta {
  display: flex;
  gap: 8px;
}

.result-content {
  margin-bottom: 12px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}

.result-content :deep(mark) {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(251, 191, 36, 0.2) 100%);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-weight: 500;
}

.result-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.result-source {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.loading-container {
  text-align: center;
  padding: 60px 0;
  color: var(--el-text-color-secondary);
}

.detail-content {
  padding: var(--spacing-md);
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  line-height: 1.6;
  white-space: pre-wrap;
}

/* Table styles */
:deep(.el-table) {
  font-size: var(--text-sm);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

:deep(.el-table th) {
  font-weight: 600;
  background: linear-gradient(to bottom, #f9fafb, #f3f4f6);
}

:deep(.el-table tbody tr):hover {
  background-color: rgba(102, 126, 234, 0.03) !important;
}

/* Responsive design */
@media (max-width: 768px) {
  .stats-cards .el-col {
    margin-bottom: 12px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .header-actions {
    flex-direction: column;
    align-items: stretch;
    width: 100%;
  }

  .header-actions :deep(.search-bar) {
    width: 100%;
  }
}
</style>
