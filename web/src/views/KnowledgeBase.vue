<template>
  <div class="workspace-module knowledge-base">
    <KnowledgeDocumentWorkspace
      v-if="activeDocId"
      :doc-id="activeDocId"
      :view="documentView"
      :page="documentPage"
      @back="backToLibrary"
      @navigate="navigateDocument"
      @updated="loadDocuments"
    />
    <template v-else>
      <header class="kb-page-heading">
        <div><h1>知识库</h1><p>从政策原文到可检索知识，每一步都有据可查。</p></div>
        <el-button id="kb-add-doc" type="primary" :icon="Plus" @click="importVisible = true">导入资料</el-button>
      </header>
      <section class="kb-overview" aria-label="资料概览" :aria-busy="loading">
        <dl>
          <div><dt>文档资料</dt><dd>{{ loaded ? documents.length : '—' }}<small>份</small></dd></div>
          <div><dt>已提取正文</dt><dd>{{ loaded ? parsedDocuments.length : '—' }}<small>份</small></dd></div>
          <div><dt>入库完成标记</dt><dd>{{ loaded ? indexedCount : '—' }}<small>份</small></dd></div>
          <div><dt>原始文件大小</dt><dd class="kb-size-total">{{ loaded ? formatBytes(totalSize) : '—' }}</dd></div>
        </dl>
        <el-tooltip content="重新读取资料列表" placement="bottom"><el-button :icon="Refresh" text :loading="loading" aria-label="刷新资料列表" @click="loadDocuments" /></el-tooltip>
      </section>
      <div v-if="listError" class="kb-error" role="alert"><el-icon><Warning /></el-icon><span>{{ listError }}</span><el-button text @click="loadDocuments">重新读取</el-button></div>
      <div v-if="capabilityError" class="kb-error" role="alert"><span>{{ capabilityError }}</span><el-button text @click="loadCapabilities">重新读取处理能力</el-button></div>
      <el-tabs :model-value="libraryTab" class="kb-library-tabs" @update:model-value="setLibraryTab">
        <el-tab-pane label="文档资料" name="documents">
          <section aria-labelledby="kb-document-list-heading" v-loading="loading">
            <div class="kb-list-tools">
              <div><h2 id="kb-document-list-heading">全部资料 <span>· {{ matchingDocuments.length }} 份</span></h2><p>打开文档，连续核对原文、解析、切块与索引方案。</p></div>
              <div class="kb-filters">
                <el-input id="kb-document-query" v-model="documentQuery" :prefix-icon="Search" placeholder="搜索文件名称" clearable aria-label="搜索文件名称" />
                <el-select id="kb-document-status" v-model="documentStatus" aria-label="按处理状态筛选"><el-option label="全部处理状态" value="all" /><el-option label="已提取正文" value="parsed" /><el-option label="待解析" value="unparsed" /></el-select>
              </div>
            </div>
            <div v-if="!loading && !listError && !matchingDocuments.length" class="kb-empty">
              <el-icon><Document /></el-icon><h3>{{ documents.length ? '没有匹配的资料' : '还没有政策资料' }}</h3>
              <p>{{ documents.length ? '换一个文件名称，或清除筛选条件。' : '导入 PDF、Word 或文本，开始核对和整理。' }}</p>
              <el-button v-if="documents.length" @click="clearFilters">清除筛选</el-button><el-button v-else type="primary" @click="importVisible = true">导入第一份资料</el-button>
            </div>
            <template v-else>
            <el-table id="kb-document-table" :data="visibleDocuments" row-key="id" highlight-current-row :current-row-key="selectedDocId" aria-label="知识库文档资料" @current-change="selectDocument">
              <el-table-column label="文档名称" min-width="300">
                <template #default="{ row }"><div class="kb-doc-identity"><span class="kb-file-icon"><el-icon><Document /></el-icon></span><div><button type="button" class="kb-doc-title" :data-document-id="row.id" @click="openDocument(row.id)">{{ row.name }}</button><span class="kb-doc-meta">{{ fileExtension(row.name) }} · {{ formatBytes(row.size) }}</span></div></div></template>
              </el-table-column>
              <el-table-column label="正文提取" width="140"><template #default="{ row }"><span class="kb-status"><el-icon><component :is="row.parsed ? CircleCheck : Clock" /></el-icon>{{ row.parsed ? '正文已提取' : '待解析' }}</span><span v-if="row.parsed" class="kb-doc-meta">{{ row.content_length.toLocaleString() }} 字符</span></template></el-table-column>
              <el-table-column label="索引" width="120"><template #default="{ row }"><span class="kb-doc-meta">{{ row.embedded ? '已有入库标记' : '待确认方案' }}</span></template></el-table-column>
              <el-table-column label="文件更新时间" width="166"><template #default="{ row }"><time class="kb-doc-meta">{{ formatDate(row.modified) }}</time></template></el-table-column>
              <el-table-column label="操作" width="110" align="right"><template #default="{ row }"><el-button link type="primary" @click="openDocument(row.id, 'parsed')">查看解析<el-icon><ArrowRight /></el-icon></el-button></template></el-table-column>
            </el-table>
            <div class="kb-document-cards" aria-label="知识库文档资料">
              <article v-for="document in visibleDocuments" :key="document.id" class="kb-document-card">
                <div class="kb-doc-identity"><span class="kb-file-icon"><el-icon><Document /></el-icon></span><div><button type="button" class="kb-doc-title" :data-document-id="document.id" @click="openDocument(document.id)">{{ document.name }}</button><span class="kb-doc-meta">{{ fileExtension(document.name) }} · {{ formatBytes(document.size) }}</span></div></div>
                <div class="kb-card-state"><span class="kb-status"><el-icon><component :is="document.parsed ? CircleCheck : Clock" /></el-icon>{{ document.parsed ? '正文已提取' : '待解析' }}</span><span class="kb-doc-meta">{{ document.embedded ? '已有入库标记' : '待确认方案' }}</span></div>
                <footer><time class="kb-doc-meta">{{ formatDate(document.modified) }}</time><el-button link type="primary" @click="openDocument(document.id, 'parsed')">查看解析<el-icon><ArrowRight /></el-icon></el-button></footer>
              </article>
            </div>
            </template>
            <div class="kb-list-footer"><span>资料处理状态与政策有效性分别核对</span><el-pagination v-if="matchingDocuments.length > 10" v-model:current-page="currentPage" :page-size="10" :total="matchingDocuments.length" layout="prev, pager, next" small /></div>
          </section>
          <section v-if="draft.count" class="kb-pending-task" aria-label="待提交资料"><el-icon><FolderOpened /></el-icon><div><strong>{{ draft.count }} 份资料的导入草稿</strong><p>文件清单和处理选项已保留，可继续核对。</p></div><el-button @click="importVisible = true">继续导入<el-icon><ArrowRight /></el-icon></el-button></section>
          <section v-if="selectedDocument" class="kb-selection" aria-labelledby="kb-selected-title">
            <header><div><h2 id="kb-selected-title">{{ selectedDocument.name }}</h2><p>选中文档 · {{ fileExtension(selectedDocument.name) }} · {{ formatBytes(selectedDocument.size) }}</p></div><el-button id="kb-open-workspace" @click="openDocument(selectedDocument.id)">进入文档工作区<el-icon><ArrowRight /></el-icon></el-button></header>
            <ol class="kb-processing-chain">
              <li><span>01</span><div><strong>原始资料</strong><small>{{ selectionDetail?.page_count ? selectionDetail.page_count + ' 页 · ' : '' }}原始文件可查阅</small></div></li>
              <li><span>02</span><div><strong>解析正文</strong><small>{{ selectedDocument.parsed ? selectedDocument.content_length.toLocaleString() + ' 字符 · 可核对正文' : '待提取 · 保留原文件' }}</small></div></li>
              <li><span>03</span><div><strong>切块检查</strong><small>核对条款边界与重叠</small></div></li>
              <li><span>04</span><div><strong>索引方案</strong><small>{{ selectedDocument.embedded ? '已有入库完成标记' : '核对后手动入库' }}</small></div></li>
            </ol>
            <div class="kb-selection-body">
              <div><h3>正文与来源</h3><p v-if="selectionError" class="kb-inline-error" role="status">{{ selectionError }} <el-button link @click="loadSelection">重试</el-button></p><p v-else-if="selectionLoading" class="kb-muted">正在读取正文…</p><p v-else-if="selectionDetail?.parsed.available" class="kb-excerpt">{{ selectionExcerpt }}</p><p v-else class="kb-muted">尚未取得有效解析正文。原始文件可先行查阅，确认解析方案后再提取。</p><el-button link type="primary" @click="openDocument(selectedDocument.id, 'parsed')">对照原文核对解析<el-icon><ArrowRight /></el-icon></el-button></div>
              <aside><h3>{{ selectedDocument.parsed ? '下一步：核对切块边界' : '下一步：核对解析方案' }}</h3><p>{{ selectedDocument.parsed ? '调整目标长度与重叠范围，确认完整条款，再保存处理方案。' : '先打开原文件确认资料完整，再按实际可用的解析方式提取正文。' }}</p><el-button link type="primary" @click="openDocument(selectedDocument.id, selectedDocument.parsed ? 'chunks' : 'index')">{{ selectedDocument.parsed ? '查看切块' : '查看处理方案' }}<el-icon><ArrowRight /></el-icon></el-button></aside>
            </div>
          </section>
        </el-tab-pane>
        <el-tab-pane label="知识检索" name="search">
          <div class="kb-search-layout">
            <section class="kb-search-controls"><h2>检索知识</h2><p>在已入库内容中查找相关政策依据。</p><el-form label-position="top" @submit.prevent="performSearch"><el-form-item label="问题或关键词"><el-input id="kb-knowledge-query" v-model="appStore.kbState.searchQuery" type="textarea" :rows="4" placeholder="例如：家电补贴的申请条件是什么？" /></el-form-item><el-form-item label="返回数量"><el-input-number v-model="searchOptions.topK" :min="1" :max="50" controls-position="right" /></el-form-item><el-form-item label="相似度阈值"><el-slider v-model="searchOptions.threshold" :min="0" :max="1" :step="0.05" :format-tooltip="value => Math.round(value * 100) + '%'" /><small>只显示达到阈值的语义检索结果</small></el-form-item><el-button id="kb-run-search" native-type="submit" type="primary" :icon="Search" :loading="searching">检索知识库</el-button></el-form></section>
            <section class="kb-search-results" aria-labelledby="kb-results-heading" :aria-busy="searching"><header><h2 id="kb-results-heading">检索结果</h2><span v-if="searchCompleted">{{ searchResults.length }} 条</span></header><div v-if="searchError" class="kb-error" role="alert"><span>{{ searchError }}</span><el-button text @click="performSearch">重试</el-button></div><div v-if="!searchCompleted && !searching && !searchError" class="kb-empty"><el-icon><Search /></el-icon><h3>从一个问题开始</h3><p>结果显示实际返回的内容与来源，可继续打开文档核对全文。</p></div><div v-if="searching" class="kb-empty" role="status"><el-icon class="is-loading"><Loading /></el-icon><p>正在检索知识库…</p></div><div v-else-if="searchCompleted && !searchResults.length" class="kb-empty"><h3>没有符合条件的结果</h3><p>尝试更具体的关键词，或适当降低相似度阈值。</p></div><article v-for="(result, index) in searchResults" v-else :key="result.id" class="kb-result"><header><span>{{ String(index + 1).padStart(2, '0') }}</span><h3>{{ result.title }}</h3><span v-if="Number.isFinite(result.score)">{{ (result.score * 100).toFixed(1) }}%<small>相似度</small></span></header><p>{{ result.content }}</p><footer><span>{{ sourceName(result.source) || '未提供来源' }}</span><el-button v-if="findResultDocument(result)" link type="primary" @click="openDocument(findResultDocument(result).id, 'parsed')">核对来源文档<el-icon><ArrowRight /></el-icon></el-button></footer></article></section>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>
    <KnowledgeImportDialog v-model="importVisible" :documents="documents" :capabilities="capabilities" @uploaded="onUploaded" @draft-change="draft = $event" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, CircleCheck, Clock, Document, FolderOpened, Loading, Plus, Refresh, Search, Warning } from '@element-plus/icons-vue'
import { knowledgeApi } from '@/api'
import { useAppStore } from '@/stores/app'
import KnowledgeDocumentWorkspace from '@/components/knowledge/KnowledgeDocumentWorkspace.vue'
import KnowledgeImportDialog from '@/components/knowledge/KnowledgeImportDialog.vue'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const documents = computed(() => appStore.kbState.documents)
const activeDocId = computed(() => typeof route.query.doc === 'string' ? route.query.doc : '')
const documentView = computed(() => ['parsed', 'chunks', 'index'].includes(route.query.view) ? route.query.view : 'source')
const documentPage = computed(() => Math.max(1, Number.parseInt(route.query.page, 10) || 1))
const libraryTab = computed(() => route.query.tab === 'search' ? 'search' : 'documents')
const documentQuery = ref('')
const documentStatus = ref('all')
const currentPage = ref(1)
const selectedDocId = ref('')
const selectedDocument = computed(() => matchingDocuments.value.find(document => document.id === selectedDocId.value) || null)
const selectionDetail = ref(null)
const selectionLoading = ref(false)
const selectionError = ref('')
const loading = ref(false)
const loaded = ref(false)
const listError = ref('')
const importVisible = ref(false)
const draft = ref({ count: 0, savedAt: null })
const capabilities = ref(null)
const capabilityError = ref('')
const parsedDocuments = computed(() => documents.value.filter(document => document.parsed))
const indexedCount = computed(() => documents.value.filter(document => document.embedded).length)
const totalSize = computed(() => documents.value.reduce((total, document) => total + document.size, 0))
const matchingDocuments = computed(() => documents.value.filter(document => {
  const matchesName = document.name.toLocaleLowerCase().includes(documentQuery.value.trim().toLocaleLowerCase())
  const matchesStatus = documentStatus.value === 'all' || document.parsed === (documentStatus.value === 'parsed')
  return matchesName && matchesStatus
}))
const visibleDocuments = computed(() => matchingDocuments.value.slice((currentPage.value - 1) * 10, currentPage.value * 10))
const selectionExcerpt = computed(() => {
  const text = selectionDetail.value?.parsed.text || ''
  const excerpt = text.replace(/\s+/g, ' ').slice(0, 170)
  return excerpt + (text.length > 170 ? '…' : '')
})
const searchOptions = reactive({ topK: 10, threshold: 0.5 })
const searchResults = ref([])
const searching = ref(false)
const searchCompleted = ref(false)
const searchError = ref('')
let listRequest, selectionRequest, searchRequest, capabilityRequest

function errorMessage(error, fallback) {
  const detail = error.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}
function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}
function formatDate(seconds) {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short', hour12: false }).format(new Date(seconds * 1000))
}
function fileExtension(name) { return name.includes('.') ? name.split('.').at(-1).toUpperCase() : '文件' }
function sourceName(source) { return typeof source === 'string' ? source.split(/[\\/]/).at(-1) : '' }
function findResultDocument(result) { return documents.value.find(document => document.id === sourceName(result.source)) }
async function loadDocuments() {
  listRequest?.abort()
  const controller = new AbortController()
  listRequest = controller
  loading.value = true
  listError.value = ''
  try {
    const response = await knowledgeApi.listDocuments({}, { signal: controller.signal })
    if (controller.signal.aborted) return
    if (!response.success || !Array.isArray(response.documents)) throw new Error('文档响应无效')
    appStore.kbState.documents = [...response.documents].sort((a, b) => b.modified - a.modified)
    loaded.value = true
    const nextSelection = matchingDocuments.value.some(document => document.id === selectedDocId.value) ? selectedDocId.value : matchingDocuments.value[0]?.id || ''
    if (selectedDocId.value !== nextSelection) selectedDocId.value = nextSelection
    else if (selectedDocId.value) await loadSelection()
  } catch (error) {
    if (!controller.signal.aborted) listError.value = errorMessage(error, '无法读取文档资料，请检查服务连接后重试。')
  } finally {
    if (listRequest === controller) loading.value = false
  }
}
async function loadSelection() {
  selectionRequest?.abort()
  selectionDetail.value = null
  selectionError.value = ''
  if (!selectedDocId.value || activeDocId.value) return
  const controller = new AbortController()
  const id = selectedDocId.value
  selectionRequest = controller
  selectionLoading.value = true
  try {
    const response = await knowledgeApi.getDocumentWorkspace(id, { signal: controller.signal })
    if (!controller.signal.aborted && selectedDocId.value === id) selectionDetail.value = response
  } catch (error) {
    if (!controller.signal.aborted) selectionError.value = errorMessage(error, '正文暂时无法读取，可重试或打开工作区。')
  } finally {
    if (selectionRequest === controller) selectionLoading.value = false
  }
}
function selectDocument(document) { if (document) selectedDocId.value = document.id }
function clearFilters() { documentQuery.value = ''; documentStatus.value = 'all' }
function setLibraryTab(tab) { router.replace({ query: { ...(tab === 'search' ? { tab } : {}) } }) }
function openDocument(id, view = 'source') {
  selectionRequest?.abort()
  router.push({ query: { doc: id, ...(view === 'source' ? {} : { view }), page: '1' } })
}
function navigateDocument({ view, page }) { router.replace({ query: { doc: activeDocId.value, ...(view === 'source' ? {} : { view }), page: String(page) } }) }
function backToLibrary() { router.push({ query: {} }) }
async function onUploaded() { await loadDocuments() }
async function loadCapabilities() {
  capabilityRequest?.abort()
  const controller = new AbortController()
  capabilityRequest = controller
  capabilityError.value = ''
  try {
    const response = await knowledgeApi.getCapabilities({ signal: controller.signal })
    if (!controller.signal.aborted) capabilities.value = response.capabilities
  } catch (error) {
    if (!controller.signal.aborted) capabilityError.value = '处理能力读取失败，导入文件和草稿会保留。请重新读取后提交。'
  }
}
async function performSearch() {
  const query = appStore.kbState.searchQuery.trim()
  searchRequest?.abort()
  searchResults.value = []
  searchCompleted.value = false
  searchError.value = ''
  if (!query) { searchError.value = '请输入需要查找的问题或关键词。'; return }
  const controller = new AbortController()
  searchRequest = controller
  searching.value = true
  try {
    const response = await knowledgeApi.search(query, { ...searchOptions, signal: controller.signal })
    if (controller.signal.aborted) return
    if (!response.success || !Array.isArray(response.results)) throw new Error('检索响应无效')
    searchResults.value = response.results
    searchCompleted.value = true
  } catch (error) {
    if (!controller.signal.aborted) searchError.value = errorMessage(error, '检索未完成，请检查服务连接后重试。')
  } finally {
    if (searchRequest === controller) searching.value = false
  }
}
watch([documentQuery, documentStatus], () => { currentPage.value = 1 })
watch(matchingDocuments, items => {
  currentPage.value = Math.min(currentPage.value, Math.max(1, Math.ceil(items.length / 10)))
  if (!items.some(document => document.id === selectedDocId.value)) selectedDocId.value = items[0]?.id || ''
})
watch(selectedDocId, loadSelection)
watch(activeDocId, id => { if (!id) loadSelection() })
onMounted(() => {
  loadDocuments()
  loadCapabilities()
})
onBeforeUnmount(() => { listRequest?.abort(); selectionRequest?.abort(); searchRequest?.abort(); capabilityRequest?.abort() })
</script>

<style scoped>
.knowledge-base { min-width: 0; }
.kb-page-heading { display: flex; align-items: center; justify-content: space-between; gap: var(--spacing-md); margin-bottom: var(--spacing-lg); }
.kb-page-heading h1 { margin: 0 0 var(--spacing-sm); font-size: var(--text-2xl); font-weight: 500; }
.kb-page-heading p, .kb-selection header p { margin: 0; font-size: var(--text-xs); color: var(--wb-muted); line-height: 1.8; }
.kb-page-heading > .el-button { height: 38px; }
.kb-overview { display: flex; align-items: center; border: 1px solid var(--wb-line); border-radius: var(--wb-radius); background: var(--wb-tint); padding: var(--spacing-lg) var(--spacing-sm); margin-bottom: var(--spacing-md); }
.kb-overview dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); flex: 1; margin: 0; }
.kb-overview dl > div { padding: 0 var(--spacing-lg); border-right: 1px solid var(--wb-line); }
.kb-overview dl > div:last-child { border: 0; }
.kb-overview dt { font-size: var(--text-xs); color: var(--wb-muted); margin-bottom: var(--spacing-sm); }
.kb-overview dd { margin: 0; font: 500 var(--text-2xl)/1.1 var(--wb-number); color: var(--wb-ink); }
.kb-overview dd small { margin-left: var(--spacing-sm); font: 400 var(--text-xs) var(--wb-font); color: var(--wb-muted); }
.kb-overview .kb-size-total { font-size: var(--text-xl); }
.kb-library-tabs :deep(.el-tabs__header) { margin-bottom: var(--spacing-lg); }
.kb-library-tabs :deep(.el-tabs__item) { font-weight: 400; font-size: var(--text-sm); }
.kb-library-tabs :deep(.el-tabs__nav-wrap::after) { height: 1px; background: var(--wb-line); }
.kb-list-tools { display: flex; align-items: center; justify-content: space-between; gap: var(--spacing-md); padding-bottom: var(--spacing-md); }
.kb-list-tools h2, .kb-selection h2, .kb-search-layout h2 { font-size: var(--text-base); font-weight: 500; margin: 0; line-height: 1.7; }
.kb-list-tools h2 span { color: var(--wb-muted); font-size: var(--text-xs); font-weight: 400; }
.kb-list-tools p, .kb-search-controls > p { color: var(--wb-muted); font-size: var(--text-xs); margin: var(--spacing-xs) 0 0; }
.kb-filters { display: flex; gap: var(--spacing-sm); width: 440px; max-width: 55%; }
.kb-filters .el-input { flex: 1; min-width: 0; }
.kb-filters .el-select { width: 155px; flex: none; }
.kb-doc-identity { display: flex; gap: var(--spacing-sm); align-items: center; min-width: 0; }
.kb-doc-identity > div { min-width: 0; }
.kb-file-icon { display: grid; place-items: center; flex: 0 0 34px; height: 40px; background: var(--wb-tint); border: 1px solid var(--wb-line); border-radius: var(--radius-sm); color: var(--wb-blue); font-size: var(--text-xl); }
.kb-doc-title { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; text-align: left; background: none; border: 0; color: var(--wb-ink); padding: 0; font: 500 var(--text-sm)/1.8 var(--wb-font); cursor: pointer; overflow: hidden; overflow-wrap: anywhere; }
.kb-doc-title:hover { color: var(--wb-blue); }
.kb-doc-title:focus-visible { outline: 2px solid var(--wb-blue); outline-offset: 3px; }
.kb-doc-meta { display: block; color: var(--wb-muted); font-size: var(--text-xs); line-height: 1.9; overflow-wrap: anywhere; }
.kb-document-cards { display: none; }
.kb-document-card { padding: var(--spacing-md) 0; border-bottom: 1px solid var(--wb-line); }
.kb-card-state, .kb-document-card footer { display: flex; align-items: center; justify-content: space-between; gap: var(--spacing-sm); margin-top: var(--spacing-sm); }
.kb-document-card .kb-doc-title { display: block; overflow: visible; }
.kb-status { display: inline-flex; gap: var(--spacing-xs); align-items: center; font-size: var(--text-xs); color: var(--wb-blue); white-space: nowrap; }
.kb-list-footer { display: flex; justify-content: space-between; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-md) 0; color: var(--wb-muted); font-size: var(--text-xs); }
.kb-selection { margin-top: var(--spacing-md); border: 1px solid var(--wb-line); border-radius: var(--wb-radius); overflow: hidden; }
.kb-selection > header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--spacing-md); padding: var(--spacing-lg); }
.kb-selection h2 { overflow-wrap: anywhere; }
.kb-selection header .el-button { flex: none; }
.kb-processing-chain { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); padding: var(--spacing-md) var(--spacing-lg); margin: 0; list-style: none; background: var(--wb-tint); }
.kb-processing-chain li { display: flex; align-items: flex-start; gap: var(--spacing-sm); padding: 0 var(--spacing-md); border-right: 1px solid var(--wb-line); }
.kb-processing-chain li:first-child { padding-left: 0; }
.kb-processing-chain li:last-child { border: 0; }
.kb-processing-chain li > span { color: var(--wb-muted); font: 400 var(--text-xs)/1.8 var(--wb-number); }
.kb-processing-chain strong, .kb-processing-chain small { display: block; font-size: var(--text-xs); line-height: 1.8; }
.kb-processing-chain strong { font-weight: 500; color: var(--wb-blue); }
.kb-processing-chain small { margin-top: var(--spacing-xs); color: var(--wb-muted); }
.kb-selection-body { display: grid; grid-template-columns: 1.4fr 1fr; }
.kb-selection-body > * { padding: var(--spacing-lg); }
.kb-selection-body aside { border-left: 1px solid var(--wb-line); background: var(--wb-tint); }
.kb-selection-body h3 { font-size: var(--text-sm); font-weight: 500; margin: 0 0 var(--spacing-sm); }
.kb-selection-body p { font-size: var(--text-sm); line-height: 1.9; margin: 0 0 var(--spacing-sm); }
.kb-selection-body aside p, .kb-muted { color: var(--wb-muted); }
.kb-excerpt { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.kb-pending-task { display: flex; gap: var(--spacing-md); align-items: center; padding: var(--spacing-md); margin-top: var(--spacing-md); background: var(--wb-tint); border: 1px solid var(--wb-line); border-radius: var(--wb-radius); }
.kb-pending-task > .el-icon { color: var(--wb-blue); font-size: var(--text-xl); }
.kb-pending-task > div { flex: 1; }
.kb-pending-task strong { font-size: var(--text-sm); font-weight: 500; }
.kb-pending-task p { font-size: var(--text-xs); color: var(--wb-muted); margin: var(--spacing-xs) 0 0; }
.kb-empty { min-height: 230px; padding: var(--spacing-xl); display: flex; align-items: center; justify-content: center; flex-direction: column; text-align: center; color: var(--wb-muted); gap: var(--spacing-sm); }
.kb-empty > .el-icon { font-size: var(--text-2xl); color: var(--wb-blue); }
.kb-empty h3 { font-size: var(--text-base); font-weight: 500; color: var(--wb-ink); margin: var(--spacing-sm) 0 0; }
.kb-empty p { font-size: var(--text-sm); line-height: 1.8; max-width: 350px; margin: 0; }
.kb-error { display: flex; align-items: center; gap: var(--spacing-sm); padding: var(--spacing-sm) var(--spacing-md); margin-bottom: var(--spacing-md); border: 1px solid var(--wb-line); border-radius: var(--radius-sm); font-size: var(--text-sm); background: var(--wb-tint); color: var(--wb-error); }
.kb-error > span { flex: 1; }
.kb-inline-error { color: var(--wb-error); }
.kb-search-layout { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: var(--spacing-lg); align-items: start; }
.kb-search-controls, .kb-search-results { border: 1px solid var(--wb-line); border-radius: var(--wb-radius); }
.kb-search-controls { padding: var(--spacing-lg); }
.kb-search-controls .el-form { margin-top: var(--spacing-lg); }
.kb-search-controls small { display: block; color: var(--wb-muted); font-size: var(--text-xs); }
.kb-search-controls .el-button { width: 100%; }
.kb-search-results { min-width: 0; min-height: 440px; }
.kb-search-results > header { padding: var(--spacing-md) var(--spacing-lg); border-bottom: 1px solid var(--wb-line); display: flex; justify-content: space-between; align-items: center; }
.kb-search-results > header > span { color: var(--wb-muted); font-size: var(--text-xs); }
.kb-search-results > .kb-error { margin: var(--spacing-md); }
.kb-result { padding: var(--spacing-lg); border-bottom: 1px solid var(--wb-line); }
.kb-result:last-child { border: 0; }
.kb-result header { display: flex; gap: var(--spacing-sm); align-items: flex-start; }
.kb-result header > span { color: var(--wb-muted); font: 400 var(--text-sm)/1.8 var(--wb-number); }
.kb-result header > span:last-child { color: var(--wb-blue); text-align: right; }
.kb-result header h3 { flex: 1; margin: 0; font-size: var(--text-base); font-weight: 500; overflow-wrap: anywhere; }
.kb-result header small { display: block; font: 400 var(--text-xs) var(--wb-font); color: var(--wb-muted); }
.kb-result > p { white-space: pre-wrap; font-size: var(--text-sm); line-height: 1.9; overflow-wrap: anywhere; }
.kb-result footer { display: flex; justify-content: space-between; gap: var(--spacing-sm); color: var(--wb-muted); font-size: var(--text-xs); }
.kb-result footer > span { overflow-wrap: anywhere; }
@media(max-width: 1000px) { .kb-list-tools { flex-direction: column; align-items: stretch; } .kb-filters { max-width: none; width: 100%; } .kb-selection > header { flex-direction: column; } .kb-processing-chain { grid-template-columns: repeat(2,minmax(0,1fr)); gap: var(--spacing-md); } .kb-processing-chain li:nth-child(2) { border: 0; } .kb-processing-chain li:nth-child(3) { padding-left: 0; } }
@media(max-width: 699px) { .kb-page-heading { align-items: flex-start; } .kb-page-heading h1 { font-size: var(--text-xl); } .kb-page-heading p { max-width: 210px; } .kb-overview { padding: var(--spacing-md) 0; align-items: flex-start; } .kb-overview dl { grid-template-columns: repeat(2,minmax(0,1fr)); gap: var(--spacing-md) 0; } .kb-overview dl > div { padding: 0 var(--spacing-md); } .kb-overview dl > div:nth-child(even) { border: 0; } .kb-selection-body, .kb-search-layout { grid-template-columns: 1fr; } .kb-selection-body aside { border-left: 0; border-top: 1px solid var(--wb-line); } .kb-selection > header, .kb-selection-body > * { padding: var(--spacing-md); } .kb-selection .el-button { max-width: 100%; } .kb-selection h2 { font-size: var(--text-sm); } .kb-processing-chain { padding: var(--spacing-md); } .kb-processing-chain li { padding: 0 var(--spacing-sm); } .kb-processing-chain strong, .kb-processing-chain small { font-size: var(--text-xs); } .kb-list-footer { flex-wrap: wrap; } .kb-pending-task { flex-wrap: wrap; } .kb-pending-task .el-button { margin-left: auto; } .kb-error { flex-wrap: wrap; } }
@media(max-width: 699px) { #kb-document-table { display: none; } .kb-document-cards { display: block; } }
</style>
