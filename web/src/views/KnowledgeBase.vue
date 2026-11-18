<template>
  <div class="workspace-module knowledge-base" :class="{ 'is-document-open': activeDocId }">
    <KnowledgeDocumentWorkspace
      v-if="activeDocId"
      :doc-id="activeDocId"
      :view="documentView"
      :page="documentPage"
      :return-label="libraryTab === 'search' ? '返回检索结果' : '返回资料列表'"
      @back="backToLibrary"
      @navigate="navigateDocument"
      @updated="loadDocuments"
    />
    <template v-else>
      <header class="kb-page-heading">
        <div>
          <h1>政策资料</h1>
          <p v-if="loaded" class="kb-page-stats"><span><b>{{ documents.length }}</b> 份资料</span><span><b>{{ parsedDocuments.length }}</b> 份有正文</span><span><b>{{ indexedCount }}</b> 份已入库</span></p>
          <p v-else class="kb-page-stats">集中管理政策文件，核对正文与入库状态。</p>
        </div>
        <el-button id="kb-add-doc" type="primary" :icon="Upload" @click="importVisible = true">上传资料</el-button>
      </header>
      <div v-if="capabilityError && !listError" class="kb-capability-notice" role="status"><el-icon><InfoFilled /></el-icon><span>处理选项暂不可用，资料查看与导入草稿不受影响。</span><el-button link @click="loadCapabilities">重新读取处理选项</el-button></div>
      <el-tabs :model-value="libraryTab" class="kb-library-tabs" @update:model-value="setLibraryTab">
        <el-tab-pane label="资料管理" name="documents">
          <section class="kb-collection" aria-labelledby="kb-document-list-heading" :aria-busy="loading">
            <h2 id="kb-document-list-heading" class="kb-visually-hidden">政策资料列表</h2>
            <header v-if="!loaded" class="kb-unloaded-toolbar" aria-label="资料读取后可使用筛选">
              <span class="kb-unloaded-caption">资料列表<small>PDF、Word 和文本</small></span>
              <el-input :prefix-icon="Search" placeholder="搜索文件名" aria-label="搜索文件名称，资料读取后可用" disabled />
              <el-select model-value="all" aria-label="正文筛选，资料读取后可用" disabled><el-option label="全部正文" value="all" /></el-select>
            </header>
            <div v-if="loaded && documents.length" class="kb-collection-toolbar">
              <div class="kb-scope-tabs" role="group" aria-label="按入库范围筛选">
                <button id="kb-document-index-status" type="button" :class="{ 'is-active': documentIndexStatus === 'all' }" :aria-pressed="documentIndexStatus === 'all'" @click="documentIndexStatus = 'all'">全部资料 <span>{{ loaded ? documents.length : '—' }}</span></button>
                <button type="button" :class="{ 'is-active': documentIndexStatus === 'indexed' }" :aria-pressed="documentIndexStatus === 'indexed'" @click="documentIndexStatus = 'indexed'">已入库 <span>{{ loaded ? indexedCount : '—' }}</span></button>
                <button type="button" :class="{ 'is-active': documentIndexStatus === 'pending' }" :aria-pressed="documentIndexStatus === 'pending'" @click="documentIndexStatus = 'pending'">未入库 <span>{{ loaded ? documents.length - indexedCount : '—' }}</span></button>
              </div>
              <el-form class="kb-filters" aria-label="资料筛选" @submit.prevent>
                <el-input id="kb-document-query" v-model="documentQuery" :prefix-icon="Search" placeholder="搜索文件名" aria-label="搜索文件名称" clearable />
                <el-select id="kb-document-status" v-model="documentStatus" aria-label="按正文状态筛选"><el-option label="全部正文" value="all" /><el-option label="正文已提取" value="parsed" /><el-option label="待解析" value="unparsed" /></el-select>
                <el-button text class="kb-card-sort" :icon="documentSortDirection === -1 ? SortDown : SortUp" :aria-label="documentSortDirection === -1 ? '按更新时间由早到晚排序' : '按更新时间由晚到早排序'" @click="documentSortDirection *= -1">{{ documentSortDirection === -1 ? '最近更新' : '最早更新' }}</el-button>
                <el-button v-if="hasDocumentFilters" text class="kb-reset-filter" @click="clearFilters">重置</el-button>
                <el-button text :icon="Refresh" :disabled="loading" class="kb-refresh" :aria-label="loading ? '正在刷新资料' : '刷新资料'" title="刷新资料" @click="loadDocuments" />
              </el-form>
            </div>
            <div v-if="listError && loaded" class="kb-refresh-notice" role="status"><el-icon><Warning /></el-icon><span>{{ capabilityError ? '资料与处理选项更新未完成，仍显示上次读取的资料。' : '资料更新未完成，仍显示上次读取的内容。' }}</span><el-button link @click="retryLibrary">重新读取</el-button></div>
            <div v-if="loading && !loaded" class="kb-list-skeleton" role="status" aria-label="正在读取资料">
              <el-skeleton :animated="false"><template #template><div v-for="row in 3" :key="row" class="kb-skeleton-row"><el-skeleton-item variant="rect" class="kb-skeleton-file" /><div class="kb-skeleton-copy"><el-skeleton-item variant="text" /><el-skeleton-item variant="text" /></div><el-skeleton-item variant="text" class="kb-skeleton-status" /></div></template></el-skeleton>
            </div>
            <UnavailableState v-else-if="!loaded && listError" title="暂时无法读取资料" description="请确认服务连接后重新读取。已有资料与导入草稿会保留。" :detail="[listError, capabilityError].filter(Boolean).join('\n')" @retry="retryLibrary" />
            <div v-else-if="loaded && !matchingDocuments.length" class="kb-empty">
              <el-icon><Document /></el-icon><h3>{{ documents.length ? '没有匹配的资料' : '还没有政策资料' }}</h3>
              <p>{{ documents.length ? '调整文件名称、正文状态或入库状态，重新查找资料。' : '导入 PDF、Word 或文本，开始核对和整理。' }}</p>
              <el-button v-if="documents.length" @click="clearFilters">清除筛选</el-button><el-button v-else type="primary" @click="importVisible = true">导入第一份资料</el-button>
            </div>
            <template v-else-if="loaded">
            <el-table id="kb-document-table" :data="visibleDocuments" row-key="id" highlight-current-row :current-row-key="selectedDocId" aria-label="知识库文档资料" @current-change="selectDocument">
              <el-table-column label="文件名称" min-width="300">
                <template #default="{ row }"><div class="kb-doc-identity"><span class="kb-file-icon" :class="{ 'is-pdf': fileExtension(row.name) === 'PDF' }" :title="fileExtension(row.name)"><el-icon><Document /></el-icon></span><div><button type="button" class="kb-doc-title" :title="row.name" :data-document-id="row.id" @click="openDocument(row.id)">{{ row.name }}</button></div></div></template>
              </el-table-column>
              <el-table-column label="大小" width="88"><template #default="{ row }"><span class="kb-numeric-meta">{{ formatBytes(row.size) }}</span></template></el-table-column>
              <el-table-column label="正文状态" width="110"><template #default="{ row }"><span class="kb-status" :class="row.parsed ? 'is-parsed' : 'is-pending'"><el-icon><component :is="row.parsed ? CircleCheck : Clock" /></el-icon>{{ row.parsed ? '有正文' : '待解析' }}</span></template></el-table-column>
              <el-table-column label="入库" width="100"><template #default="{ row }"><span class="kb-status" :class="row.embedded ? 'is-ready' : 'is-neutral'"><el-icon><component :is="row.embedded ? CircleCheck : Clock" /></el-icon>{{ row.embedded ? '已入库' : '未入库' }}</span></template></el-table-column>
              <el-table-column label="更新时间" width="152">
                <template #header><button type="button" class="kb-sort-heading" :aria-label="documentSortDirection === -1 ? '按更新时间由早到晚排序' : '按更新时间由晚到早排序'" @click="documentSortDirection *= -1">更新时间<el-icon><component :is="documentSortDirection === -1 ? SortDown : SortUp" /></el-icon></button></template>
                <template #default="{ row }"><time class="kb-numeric-meta">{{ formatDate(row.modified) }}</time></template>
              </el-table-column>
              <el-table-column label="操作" width="112">
                <template #default="{ row }"><div class="kb-row-actions">
                  <el-button link class="kb-open-document" @click="openDocument(row.id)">查看</el-button>
                  <el-dropdown trigger="click" popper-class="kb-document-menu" @click.stop @command="view => openDocument(row.id, view)">
                    <el-button text class="kb-more-actions" :icon="MoreFilled" :aria-label="'更多操作：' + row.name" />
                    <template #dropdown><el-dropdown-menu><el-dropdown-item command="parsed" :disabled="!row.parsed">查看解析正文</el-dropdown-item><el-dropdown-item command="chunks" :disabled="!row.parsed">查看切块预览</el-dropdown-item><el-dropdown-item command="index">处理方案</el-dropdown-item></el-dropdown-menu></template>
                  </el-dropdown>
                </div></template>
              </el-table-column>
            </el-table>
            <div class="kb-document-cards" aria-label="知识库文档资料">
              <article v-for="document in visibleDocuments" :key="document.id" class="kb-document-card">
                <div class="kb-doc-identity"><span class="kb-file-icon" :class="{ 'is-pdf': fileExtension(document.name) === 'PDF' }"><el-icon><Document /></el-icon></span><div><button type="button" class="kb-doc-title" :data-document-id="document.id" @click="openDocument(document.id)">{{ document.name }}</button><span class="kb-doc-meta">{{ fileExtension(document.name) }} · {{ formatBytes(document.size) }}</span></div></div>
                <dl class="kb-card-state"><div><dt>正文状态</dt><dd><span class="kb-status" :class="document.parsed ? 'is-ready' : 'is-pending'">{{ document.parsed ? '正文已提取' : '待解析' }}</span></dd></div><div><dt>入库状态</dt><dd><span class="kb-status" :class="document.embedded ? 'is-ready' : 'is-neutral'">{{ document.embedded ? '已入库' : '待入库' }}</span></dd></div></dl>
                <footer><time class="kb-doc-meta">更新于 {{ formatDate(document.modified) }}</time><div class="kb-row-actions">
                  <el-button link :aria-pressed="selectedDocId === document.id && selectedPreviewOpen" @click="previewDocument(document)">预览</el-button>
                  <el-button link @click="openDocument(document.id)">查看</el-button>
                  <el-dropdown trigger="click" popper-class="kb-document-menu" @command="view => openDocument(document.id, view)">
                    <el-button text class="kb-more-actions" :icon="MoreFilled" :aria-label="'更多操作：' + document.name" />
                    <template #dropdown><el-dropdown-menu><el-dropdown-item command="parsed" :disabled="!document.parsed">查看解析正文</el-dropdown-item><el-dropdown-item command="chunks" :disabled="!document.parsed">查看切块预览</el-dropdown-item><el-dropdown-item command="index">处理方案</el-dropdown-item></el-dropdown-menu></template>
                  </el-dropdown>
                </div></footer>
              </article>
            </div>
            </template>
            <div v-if="loaded && matchingDocuments.length" class="kb-list-footer"><span>{{ loading ? '正在更新资料…' : `共 ${matchingDocuments.length} 份资料` }}<template v-if="!loading && matchingDocuments.length !== documents.length">，全部 {{ documents.length }} 份</template><template v-if="listError"> · 上次读取结果</template></span><el-pagination v-if="matchingDocuments.length > 10" v-model:current-page="currentPage" :page-size="10" :total="matchingDocuments.length" layout="prev, pager, next" /><span v-else>10 条 / 页</span></div>
          </section>
          <p v-if="loaded" class="kb-collection-note"><el-icon><InfoFilled /></el-icon><span>问答将引用已入库的 {{ indexedCount }} 份资料，可在文件详情中核对正文与入库状态。</span></p>
          <section v-if="draft.count" class="kb-pending-task" aria-label="待提交资料"><el-icon><FolderOpened /></el-icon><div><strong>{{ draft.count }} 份资料的导入草稿</strong><p>文件清单和处理选项已保留，可继续核对。</p></div><el-button @click="importVisible = true">继续导入<el-icon><ArrowRight /></el-icon></el-button></section>
          <details v-if="selectedDocument" ref="selectionElement" class="kb-selection" :open="selectedPreviewOpen" aria-labelledby="kb-selected-title" @toggle="selectedPreviewOpen = $event.target.open">
            <summary id="kb-selected-title"><span>选中资料预览</span><strong>{{ selectedDocument.name }}</strong></summary>
            <header><p>{{ fileExtension(selectedDocument.name) }} · {{ formatBytes(selectedDocument.size) }}</p><el-button id="kb-open-workspace" @click="openDocument(selectedDocument.id)">进入文档工作区<el-icon><ArrowRight /></el-icon></el-button></header>
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
          </details>
        </el-tab-pane>
        <el-tab-pane label="知识检索" name="search">
          <div class="kb-search-layout">
            <section class="kb-search-controls">
              <h2>检索条件</h2>
              <p>查找已入库的政策条款与来源。</p>
              <el-form label-position="top" @submit.prevent="performSearch">
                <el-form-item label="问题或关键词" label-for="kb-knowledge-query">
                  <el-input id="kb-knowledge-query" v-model="appStore.kbState.searchQuery" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" resize="none" placeholder="例如：家电补贴的申请条件是什么？" />
                </el-form-item>
                <el-form-item label="返回数量" label-for="kb-search-count">
                  <el-input-number id="kb-search-count" v-model="searchOptions.topK" :min="1" :max="50" />
                </el-form-item>
                <el-form-item label="相似度阈值">
                  <div class="kb-threshold-control">
                    <el-slider aria-label="相似度阈值" v-model="searchOptions.threshold" :min="0" :max="1" :step="0.05" :format-tooltip="value => Math.round(value * 100) + '%'" />
                    <div class="kb-threshold-input"><el-input-number v-model="thresholdPercent" :min="0" :max="100" :step="5" :controls="false" aria-label="相似度阈值百分比" /><span aria-hidden="true">%</span></div>
                  </div>
                  <small>仅返回达到阈值的片段</small>
                </el-form-item>
                <el-button id="kb-run-search" native-type="submit" type="primary" :icon="Search" :loading="searching">检索知识库</el-button>
              </el-form>
            </section>
            <section class="kb-search-results" aria-labelledby="kb-results-heading" :aria-busy="searching"><header><h2 id="kb-results-heading">检索结果</h2><span v-if="searchCompleted">{{ searchResults.length }} 条</span></header><div v-if="searchError" class="kb-error" role="alert"><span>{{ searchError }}</span><el-button text @click="performSearch">重试</el-button></div>
              <div v-if="!searchCompleted && !searching && !searchError" class="kb-search-guide">
                <div class="kb-result-outline" aria-hidden="true"><span><el-icon><Document /></el-icon>政策条款<span>来源 · 相似度</span></span><i /><i /><i /></div>
                <h3>找到的政策依据会显示在这里</h3>
                <p>输入问题并检索，查看相关片段、相似度与来源，再打开文档核对全文。</p>
              </div>
              <div v-if="searching" class="kb-empty" role="status"><el-icon class="is-loading"><Loading /></el-icon><p>正在检索知识库…</p></div><div v-else-if="searchCompleted && !searchResults.length" class="kb-empty"><h3>没有符合条件的结果</h3><p>尝试更具体的关键词，或适当降低相似度阈值。</p></div><article v-for="(result, index) in searchResults" v-else :key="result.id" class="kb-result">
              <header><span>{{ String(index + 1).padStart(2, '0') }}</span><h3>{{ result.title }}</h3><span v-if="Number.isFinite(result.score)">{{ (result.score * 100).toFixed(1) }}%<small>相似度</small></span></header>
              <div class="kb-result-actions">
                <el-button v-if="findResultDocument(result)" link type="primary" @click="openDocument(findResultDocument(result).id, 'parsed')">核对来源文档<el-icon><ArrowRight /></el-icon></el-button>
                <el-button v-if="isLongSearchResult(result)" link :aria-expanded="expandedResultIds.has(result.id)" :aria-controls="'kb-result-content-' + index" @click="toggleSearchResult(result.id)">{{ expandedResultIds.has(result.id) ? '收起片段' : '展开完整片段' }}</el-button>
              </div>
              <p :id="'kb-result-content-' + index" :class="{ 'kb-result-excerpt': isLongSearchResult(result) && !expandedResultIds.has(result.id) }">{{ result.content }}</p>
              <footer><span>{{ sourceName(result.source) || '未提供来源' }}</span></footer>
            </article></section>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>
    <KnowledgeImportDialog v-model="importVisible" :documents="documents" :capabilities="capabilities" @uploaded="onUploaded" @draft-change="draft = $event" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, CircleCheck, Clock, Document, FolderOpened, InfoFilled, Loading, MoreFilled, Refresh, Search, SortDown, SortUp, Upload, Warning } from '@element-plus/icons-vue'
import { knowledgeApi } from '@/api'
import { useAppStore } from '@/stores/app'
import KnowledgeDocumentWorkspace from '@/components/knowledge/KnowledgeDocumentWorkspace.vue'
import KnowledgeImportDialog from '@/components/knowledge/KnowledgeImportDialog.vue'
import UnavailableState from '@/components/UnavailableState.vue'

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
const documentIndexStatus = ref('all')
const documentSortDirection = ref(-1)
const currentPage = ref(1)
const selectedDocId = ref('')
const selectedPreviewOpen = ref(false)
const selectionElement = ref(null)
const selectedDocument = computed(() => matchingDocuments.value.find(document => document.id === selectedDocId.value) || null)
const selectionDetail = ref(null)
const selectionLoading = ref(false)
const selectionError = ref('')
const loading = ref(false)
const loaded = ref(documents.value.length > 0)
const listError = ref('')
const importVisible = ref(false)
const draft = ref({ count: 0, savedAt: null })
const capabilities = ref(null)
const capabilityError = ref('')
const parsedDocuments = computed(() => documents.value.filter(document => document.parsed))
const indexedCount = computed(() => documents.value.filter(document => document.embedded).length)
const hasDocumentFilters = computed(() => Boolean(documentQuery.value.trim()) || documentStatus.value !== 'all' || documentIndexStatus.value !== 'all')
const matchingDocuments = computed(() => documents.value.filter(document => {
  const matchesName = document.name.toLocaleLowerCase().includes(documentQuery.value.trim().toLocaleLowerCase())
  const matchesStatus = documentStatus.value === 'all' || document.parsed === (documentStatus.value === 'parsed')
  const matchesIndex = documentIndexStatus.value === 'all' || document.embedded === (documentIndexStatus.value === 'indexed')
  return matchesName && matchesStatus && matchesIndex
}).sort((a, b) => (a.modified - b.modified) * documentSortDirection.value))
const visibleDocuments = computed(() => matchingDocuments.value.slice((currentPage.value - 1) * 10, currentPage.value * 10))
const selectionExcerpt = computed(() => {
  const text = selectionDetail.value?.parsed.text || ''
  const excerpt = text.replace(/\s+/g, ' ').slice(0, 170)
  return excerpt + (text.length > 170 ? '…' : '')
})
const searchOptions = reactive({ topK: 10, threshold: 0.5 })
const thresholdPercent = computed({
  get: () => Math.round(searchOptions.threshold * 100),
  set: value => {
    if (Number.isFinite(value)) searchOptions.threshold = value / 100
  }
})
const searchResults = ref([])
const expandedResultIds = ref(new Set())
const searching = ref(false)
const searchCompleted = ref(false)
const searchError = ref('')
let listRequest, selectionRequest, searchRequest, capabilityRequest
let libraryScrollTop = 0

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
  return new Intl.DateTimeFormat('sv-SE', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(seconds * 1000))
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
    appStore.kbState.documents = response.documents
    loaded.value = true
    const nextSelection = matchingDocuments.value.some(document => document.id === selectedDocId.value) ? selectedDocId.value : matchingDocuments.value[0]?.id || ''
    if (selectedDocId.value !== nextSelection) selectedDocId.value = nextSelection
    else if (selectedDocId.value) loadSelection()
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
async function previewDocument(document) {
  selectDocument(document)
  selectedPreviewOpen.value = true
  await nextTick()
  selectionElement.value.scrollIntoView({ block: 'start' })
}
function clearFilters() { documentQuery.value = ''; documentStatus.value = 'all'; documentIndexStatus.value = 'all' }
function setLibraryTab(tab) { router.replace({ query: { ...(tab === 'search' ? { tab } : {}) } }) }
async function openDocument(id, view = 'source') {
  selectionRequest?.abort()
  const scroller = document.getElementById('module-content')
  libraryScrollTop = scroller.scrollTop
  await router.push({ query: { ...(libraryTab.value === 'search' ? { tab: 'search' } : {}), doc: id, ...(view === 'source' ? {} : { view }), page: '1' } })
  await nextTick()
  if (route.path === '/knowledge' && activeDocId.value === id) scroller.scrollTop = 0
}
function navigateDocument({ view, page }) { router.replace({ query: { ...(libraryTab.value === 'search' ? { tab: 'search' } : {}), doc: activeDocId.value, ...(view === 'source' ? {} : { view }), page: String(page) } }) }
async function backToLibrary() {
  await router.push({ query: libraryTab.value === 'search' ? { tab: 'search' } : {} })
  await nextTick()
  if (route.path === '/knowledge' && !activeDocId.value) document.getElementById('module-content').scrollTop = libraryScrollTop
}
function isLongSearchResult(result) { return result.content.length > 300 || result.content.split('\n').length > 5 }
function toggleSearchResult(id) {
  if (expandedResultIds.value.has(id)) expandedResultIds.value.delete(id)
  else expandedResultIds.value.add(id)
}
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
async function retryLibrary() {
  await Promise.all([loadDocuments(), loadCapabilities()])
}
async function performSearch() {
  const query = appStore.kbState.searchQuery.trim()
  searchRequest?.abort()
  searchResults.value = []
  expandedResultIds.value = new Set()
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
watch([documentQuery, documentStatus, documentIndexStatus, documentSortDirection], () => { currentPage.value = 1 })
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
.knowledge-base { min-width: 0; font: var(--wb-text-size)/1.6 var(--wb-font); }
.knowledge-base:not(.is-document-open) { display: flex; flex-direction: column; min-height: 100%; }
.knowledge-base > .kb-library-tabs { display: flex; flex: 1; flex-direction: column; min-height: 0; }
.kb-library-tabs :deep(.el-tabs__content) { display: flex; flex: 1; overflow: visible; }
.kb-library-tabs :deep(.el-tab-pane) { display: flex; flex-direction: column; flex: 1; min-width: 0; }
.knowledge-base :deep(.el-button) { font-size: 14px; }
.kb-page-heading { display: flex; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 18px; }
.kb-page-heading > div { min-width: 0; }
.kb-page-heading h1 { margin: 0; color: var(--wb-ink); font-size: var(--wb-title-size); font-weight: 600; line-height: 1.5; }
.kb-page-heading p { margin: 7px 0 0; color: var(--wb-muted); font-size: 13px; line-height: 1.8; }
.kb-page-stats { display: flex; align-items: center; flex-wrap: wrap; gap: 5px 10px; line-height: 22px; }
.kb-page-stats > span + span::before { content: '·'; margin-right: 10px; color: var(--wb-muted); }
.kb-page-stats b { color: var(--wb-muted); font: 500 13px var(--wb-number); }
.kb-page-heading > .el-button { flex: none; }
.kb-library-tabs { background: transparent; }
.kb-library-tabs > :deep(.el-tabs__header) { margin: 0 0 18px; }
.kb-library-tabs :deep(.el-tabs__item) { height: 40px; color: var(--wb-muted); font-size: 14px; font-weight: 400; }
.kb-library-tabs :deep(.el-tabs__item.is-active) { color: var(--wb-ink); font-weight: 500; }
.kb-library-tabs :deep(.el-tabs__nav-wrap::after) { height: 1px; background: var(--wb-line); }
.kb-collection { display: flex; flex: 1; flex-direction: column; min-width: 0; min-height: 280px; overflow: hidden; border: 1px solid var(--wb-line); border-radius: var(--wb-radius); background: var(--wb-surface); }
.kb-collection > .unavailable-state, .kb-collection > .kb-empty, .kb-collection > .kb-list-skeleton { flex: 1; }
.kb-visually-hidden { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.kb-unloaded-toolbar { display: grid; grid-template-columns: minmax(120px, 1fr) minmax(180px, 320px) 148px; align-items: center; gap: 12px; padding: 14px 18px; border-bottom: 1px solid var(--wb-line); }
.kb-unloaded-caption { color: var(--wb-ink); font-size: 14px; font-weight: 500; }
.kb-unloaded-caption small { margin-left: 12px; color: var(--wb-muted); font-size: 12px; font-weight: 400; }
.kb-collection-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 0 18px; min-height: 62px; border-bottom: 1px solid var(--wb-line); }
.kb-scope-tabs { display: flex; align-items: center; gap: 4px; align-self: stretch; flex: none; }
.kb-scope-tabs > button { display: inline-flex; align-items: center; justify-content: center; gap: 7px; min-height: 36px; padding: 7px 10px; border: 0; border-radius: 5px; background: transparent; color: var(--wb-muted); font: 400 14px/1.5 var(--wb-font); white-space: nowrap; cursor: pointer; }
.kb-scope-tabs > button.is-active { color: var(--wb-ink); background: var(--wb-nav-active); font-weight: 500; }
.kb-scope-tabs > button:hover { color: var(--wb-ink); }
.kb-scope-tabs > button > span { color: var(--wb-muted); font: 400 12px var(--wb-number); }
.kb-filters { display: flex; align-items: center; justify-content: flex-end; gap: 10px; min-width: 0; margin: 0; padding: 12px 0; }
.kb-filters > .el-input { width: 232px; }
.kb-filters > .el-select { width: 128px; flex: none; }
.kb-filters > .el-button { flex: none; margin: 0; }
.kb-filters > .kb-reset-filter { padding-inline: 2px; color: var(--wb-muted); }
.kb-refresh { width: var(--wb-control-height); padding: 0; color: var(--wb-muted); }
.kb-filters :deep(.el-input__wrapper), .kb-filters :deep(.el-select__wrapper) { background: var(--wb-tint); box-shadow: 0 0 0 1px var(--wb-line) inset; }
.kb-filters :deep(.el-input__wrapper:hover), .kb-filters :deep(.el-select__wrapper:hover) { box-shadow: 0 0 0 1px var(--wb-border) inset; }
.kb-filters :deep(.el-input__wrapper.is-focus), .kb-filters :deep(.el-select__wrapper.is-focused) { box-shadow: 0 0 0 1px var(--wb-blue) inset; }
.kb-capability-notice, .kb-refresh-notice { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; color: var(--wb-muted); font-size: 13px; line-height: 1.8; }
.kb-capability-notice { margin-bottom: 16px; padding: 0 0 14px; border-bottom: 1px solid var(--wb-line); }
.kb-refresh-notice { padding: 12px 18px; border-bottom: 1px solid var(--wb-line); }
.kb-capability-notice > span, .kb-refresh-notice > span { flex: 1; min-width: 160px; }
.kb-capability-notice > .el-icon, .kb-refresh-notice > .el-icon { color: var(--wb-warning); }
.kb-list-skeleton { padding: 8px 22px; --el-skeleton-color: var(--wb-tint); --el-skeleton-to-color: var(--wb-line); }
.kb-skeleton-row { display: flex; align-items: center; gap: 14px; padding: 20px 0; border-bottom: 1px solid var(--wb-line); }
.kb-skeleton-row:last-child { border: 0; }
.kb-skeleton-copy { display: grid; flex: 1; gap: 10px; }
.kb-skeleton-copy > :first-child { width: 65%; }
.kb-skeleton-copy > :last-child { width: 35%; }
.kb-skeleton-row :deep(.kb-skeleton-file) { flex: none; width: 28px; height: 34px; }
.kb-skeleton-row :deep(.kb-skeleton-status) { flex: none; width: 60px; }
.kb-collection :deep(.el-table .cell) { padding-inline: 12px; }
.kb-collection :deep(.el-table th.el-table__cell) { height: 44px; font-size: 12px; }
.kb-collection :deep(.el-table td.el-table__cell) { height: 76px; padding-block: 10px; }
.kb-collection :deep(.el-table .el-table__cell:first-child .cell) { padding-left: 18px; }
.kb-collection :deep(.el-table__inner-wrapper::before) { display: none; }
.kb-doc-identity { display: flex; align-items: center; gap: 12px; min-width: 0; }
.kb-doc-identity > div { min-width: 0; }
.kb-file-icon { flex: none; display: grid; place-items: center; width: 29px; height: 34px; border-radius: 4px; background: color-mix(in srgb, var(--wb-muted) 8%, var(--wb-surface)); color: color-mix(in srgb, var(--wb-blue) 32%, var(--wb-muted)); font-size: 22px; }
.kb-file-icon.is-pdf { color: color-mix(in srgb, var(--wb-error) 54%, var(--wb-muted)); background: color-mix(in srgb, var(--wb-error) 5%, var(--wb-surface)); }
.kb-doc-title { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; padding: 0; border: 0; background: none; color: var(--wb-ink); font: 400 var(--wb-text-size)/1.7 var(--wb-font); text-align: left; cursor: pointer; overflow: hidden; overflow-wrap: anywhere; }
.kb-doc-title:hover { color: var(--wb-blue-hover); text-decoration: underline; }
.kb-doc-title:focus-visible { outline: 2px solid var(--wb-blue); outline-offset: 3px; }
.kb-doc-meta { display: block; color: var(--wb-muted); font-size: 12px; line-height: 1.9; overflow-wrap: anywhere; }
.kb-numeric-meta { color: var(--wb-muted); font: 12px/1.8 var(--wb-number); font-variant-numeric: tabular-nums; white-space: nowrap; }
.kb-status { display: inline-flex; align-items: center; gap: 6px; color: var(--wb-muted); font-size: 13px; line-height: 24px; white-space: nowrap; }
.kb-status .el-icon { font-size: 14px; }
.kb-status.is-ready { color: var(--wb-success); }
.kb-status.is-parsed, .kb-status.is-pending { color: var(--wb-muted); }
.kb-status.is-neutral { color: var(--wb-muted); }
.kb-row-actions { display: flex; align-items: center; gap: 14px; white-space: nowrap; }
.kb-row-actions .el-button { padding-inline: 0; color: var(--wb-muted); font-size: var(--wb-text-size); }
.kb-row-actions .el-button:hover { color: var(--wb-blue); }
.kb-row-actions .el-button + .el-button { margin-left: 0; }
.kb-row-actions .kb-more-actions { min-width: 30px; min-height: 30px; padding: 4px; }
.kb-sort-heading { display: inline-flex; align-items: center; gap: 6px; padding: 0; border: 0; background: transparent; color: var(--wb-muted); font: inherit; cursor: pointer; }
.kb-sort-heading:hover { color: var(--wb-blue); }
.kb-sort-heading:focus-visible { outline: 2px solid var(--wb-blue); outline-offset: 3px; }
.kb-filters > .kb-card-sort { display: none; }
:global(.kb-document-menu) { --el-bg-color-overlay: var(--wb-surface); --el-text-color-regular: var(--wb-ink); --el-text-color-disabled: var(--wb-muted); --el-color-primary-light-9: var(--wb-blue-soft); --el-color-primary: var(--wb-blue); --el-border-color-light: var(--wb-line); font-family: var(--wb-font); }
.kb-document-cards { display: none; }
.kb-document-card { padding: 20px; border-top: 1px solid var(--wb-line); }
.kb-document-card .kb-doc-title { display: block; overflow: visible; }
.kb-card-state { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 16px 0; }
.kb-card-state dt { color: var(--wb-muted); font-size: 12px; margin-bottom: 4px; }
.kb-card-state dd { margin: 0; }
.kb-document-card footer { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.kb-list-footer { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; min-height: 48px; padding: 10px 18px; border-top: 1px solid var(--wb-line); color: var(--wb-muted); font-size: 12px; }
.kb-collection-note { display: flex; align-items: baseline; gap: 7px; margin: 12px 0 0; color: var(--wb-muted); font-size: 12px; line-height: 22px; }
.kb-collection-note > .el-icon { position: relative; top: 2px; flex: none; font-size: 13px; }
.kb-selection { margin-top: 14px; border: 1px solid var(--wb-line); border-radius: var(--wb-radius); background: var(--wb-surface); }
.kb-selection > summary { padding: 16px 24px; cursor: pointer; color: var(--wb-muted); font-size: 13px; overflow-wrap: anywhere; }
.kb-selection > summary strong { margin-left: 16px; font-size: var(--wb-text-size); font-weight: 400; color: var(--wb-ink); }
.kb-selection > header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; padding: 0 24px 20px; }
.kb-selection > header p { margin: 0; color: var(--wb-muted); font-size: 13px; }
.kb-processing-chain { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); padding: 20px 24px; margin: 0; list-style: none; background: var(--wb-tint); }
.kb-processing-chain li { display: flex; gap: 10px; padding: 0 16px; border-right: 1px solid var(--wb-line); }
.kb-processing-chain li:first-child { padding-left: 0; }
.kb-processing-chain li:last-child { border: 0; }
.kb-processing-chain li > span { color: var(--wb-muted); font: 12px/1.8 var(--wb-number); }
.kb-processing-chain strong, .kb-processing-chain small { display: block; font-size: 13px; line-height: 1.8; }
.kb-processing-chain strong { font-weight: 500; color: var(--wb-ink); }
.kb-processing-chain small { margin-top: 4px; color: var(--wb-muted); }
.kb-selection-body { display: grid; grid-template-columns: 1.4fr 1fr; }
.kb-selection-body > * { padding: 24px; }
.kb-selection-body aside { border-left: 1px solid var(--wb-line); }
.kb-selection-body h3 { margin: 0 0 10px; font-size: var(--wb-text-size); font-weight: 500; }
.kb-selection-body p { margin: 0 0 12px; font-size: var(--wb-text-size); line-height: 1.9; }
.kb-selection-body aside p, .kb-muted { color: var(--wb-muted); }
.kb-excerpt { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.kb-pending-task { display: flex; align-items: center; gap: 16px; padding: 18px 24px; margin-top: 20px; background: var(--wb-blue-soft); border: 1px solid var(--wb-line); border-radius: var(--wb-radius); }
.kb-pending-task > .el-icon { color: var(--wb-blue); font-size: 22px; }
.kb-pending-task > div { flex: 1; min-width: 0; }
.kb-pending-task strong { font-size: var(--wb-text-size); font-weight: 500; }
.kb-pending-task p { margin: 4px 0 0; color: var(--wb-muted); font-size: 13px; line-height: 1.8; }
.kb-empty { min-height: 270px; padding: 32px 24px; display: flex; align-items: center; justify-content: center; flex-direction: column; text-align: center; color: var(--wb-muted); gap: 12px; }
.kb-empty > .el-icon { font-size: 28px; color: var(--wb-blue); }
.kb-empty h3 { margin: 0; font-size: 18px; font-weight: 500; color: var(--wb-ink); }
.kb-empty p { margin: 0; max-width: 420px; font-size: var(--wb-text-size); line-height: 1.8; }
.kb-error { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; padding: 12px 16px; margin-bottom: 16px; border: 1px solid var(--wb-line); border-radius: var(--wb-radius); font-size: var(--wb-text-size); background: var(--wb-surface); color: var(--wb-error); }
.kb-error > span { flex: 1; }
.kb-inline-error { color: var(--wb-error); }
.kb-search-layout { display: grid; flex: 1; grid-template-columns: 300px minmax(0, 1fr); gap: 20px; align-items: stretch; }
.kb-search-layout h2 { margin: 0; font-size: 15px; font-weight: 600; line-height: 1.7; }
.kb-search-controls, .kb-search-results { border: 1px solid var(--wb-line); border-radius: var(--wb-radius); background: var(--wb-surface); }
.kb-search-controls { min-width: 0; padding: 22px; }
.kb-search-controls > p { color: var(--wb-muted); font-size: 13px; margin: 7px 0 0; line-height: 1.8; }
.kb-search-controls .el-form { margin-top: 24px; }
.kb-search-controls small { display: block; color: var(--wb-muted); font-size: 12px; }
.kb-threshold-control { display: flex; align-items: center; gap: 16px; width: 100%; }
.kb-threshold-control > .el-slider { flex: 1; min-width: 0; --el-slider-height: 4px; --el-slider-button-size: 12px; }
.kb-threshold-input { display: flex; align-items: center; width: 76px; flex: none; position: relative; }
.kb-threshold-input > span { position: absolute; right: 9px; color: var(--wb-muted); font: 12px var(--wb-number); pointer-events: none; }
.kb-threshold-input :deep(.el-input-number) { width: 100%; }
.kb-threshold-input :deep(.el-input__inner) { padding-right: 12px; text-align: right; font-variant-numeric: tabular-nums; }
.kb-search-controls :deep(.el-input-number) { height: 36px; }
.kb-search-controls :deep(.el-input-number__increase), .kb-search-controls :deep(.el-input-number__decrease) { color: var(--wb-muted); background: var(--wb-tint); }
.kb-search-controls .el-button { width: 100%; }
.kb-search-results { display: flex; flex-direction: column; min-width: 0; min-height: 440px; }
.kb-search-results > .kb-search-guide, .kb-search-results > .kb-empty { flex: 1; }
.kb-search-results > header { padding: 18px 24px; border-bottom: 1px solid var(--wb-line); display: flex; justify-content: space-between; align-items: center; }
.kb-search-results > header > span { color: var(--wb-muted); font-size: 13px; }
.kb-search-results > .kb-error { margin: 16px; }
.kb-search-guide { display: grid; justify-items: center; align-content: center; min-height: 360px; padding: 40px 28px; color: var(--wb-muted); text-align: center; }
.kb-result-outline { display: grid; gap: 10px; width: min(100%, 310px); padding: 18px; border: 1px dashed var(--wb-border); border-radius: 8px; background: var(--wb-canvas); text-align: left; }
.kb-result-outline > span { display: flex; align-items: center; gap: 6px; margin-bottom: 5px; color: var(--wb-muted); font-size: 12px; }
.kb-result-outline > span > span { margin-left: auto; font-size: 11px; }
.kb-result-outline > i { display: block; width: 100%; height: 5px; background: var(--wb-line); border-radius: 3px; }
.kb-result-outline > i:last-child { width: 65%; }
.kb-search-guide h3 { margin: 24px 0 0; color: var(--wb-secondary); font-size: 15px; font-weight: 500; }
.kb-search-guide > p { max-width: 380px; margin: 8px 0 0; font-size: 13px; line-height: 1.8; }
.kb-result { padding: 24px; border-bottom: 1px solid var(--wb-line); }
.kb-result:last-child { border: 0; }
.kb-result header { display: flex; align-items: flex-start; gap: 12px; }
.kb-result header > span { color: var(--wb-muted); font: var(--wb-text-size)/1.8 var(--wb-number); }
.kb-result header > span:last-child { color: var(--wb-blue); text-align: right; }
.kb-result header h3 { flex: 1; margin: 0; font-size: 18px; font-weight: 500; overflow-wrap: anywhere; }
.kb-result header small { display: block; font: 12px var(--wb-font); color: var(--wb-muted); }
.kb-result > p { white-space: pre-wrap; font-size: var(--wb-reading-size); line-height: 1.8; overflow-wrap: anywhere; }
.kb-result-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px 20px; margin: 12px 0; }
.kb-result-actions .el-button + .el-button { margin-left: 0; }
.kb-result > p.kb-result-excerpt { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; white-space: normal; color: var(--wb-muted); font-size: var(--wb-text-size); }
.kb-result footer { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; color: var(--wb-muted); font-size: 13px; }
.kb-result footer > span { overflow-wrap: anywhere; }
@media (max-width: 1279px) {
  .kb-collection-toolbar { flex-wrap: wrap; gap: 0 18px; }
  .kb-scope-tabs { min-height: 52px; }
  .kb-filters { flex: 1; flex-wrap: wrap; justify-content: flex-start; }
  .kb-filters > .el-input { flex: 1; min-width: 180px; }
  .kb-filters > .kb-card-sort { display: inline-flex; }
  #kb-document-table { display: none; }
  .kb-document-cards { display: block; }
  .kb-processing-chain { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
  .kb-processing-chain li:nth-child(2) { border: 0; }
  .kb-processing-chain li:nth-child(3) { padding-left: 0; }
}
@media (max-width: 899px) {
  .kb-search-layout { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 699px) {
  .kb-unloaded-toolbar { grid-template-columns: minmax(0, 1fr) 124px; padding: 12px 16px; gap: 8px; }
  .kb-unloaded-caption { grid-column: 1 / -1; }
  .kb-page-heading { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 8px 12px; }
  .kb-page-heading > div { display: contents; }
  .kb-page-heading h1 { grid-column: 1; grid-row: 1; }
  .kb-page-heading p { grid-column: 1 / -1; grid-row: 2; margin: 0; }
  .kb-page-heading > .el-button { grid-column: 2; grid-row: 1; padding-inline: 12px; }
  .kb-page-stats { gap: 3px 7px; }
  .kb-page-stats > span + span::before { margin-right: 7px; }
  .kb-collection-toolbar { display: block; padding: 10px 14px 0; }
  .kb-scope-tabs { gap: 4px; margin-bottom: 8px; }
  .kb-scope-tabs > button { min-height: 44px; }
  .kb-filters { display: flex; flex-wrap: wrap; gap: 8px; padding: 0 0 14px; }
  .kb-filters > .el-input { flex: 1 0 100%; min-width: 0; width: 100%; }
  .kb-filters > .el-select { flex: 1; min-width: 100px; width: auto; }
  .kb-filters > .kb-reset-filter { padding-inline: 10px; }
  .knowledge-base :deep(input), .knowledge-base :deep(textarea) { font-size: 16px; }
  .kb-filters :deep(.el-select__selected-item) { font-size: 16px; }
  .kb-document-card { padding: 18px; }
  .kb-list-footer { padding: 12px 18px; }
  .kb-selection > summary { padding: 16px 18px; }
  .kb-selection > summary strong { display: block; margin: 7px 0 0; }
  .kb-selection > header { padding-inline: 18px; }
  .kb-selection-body, .kb-search-layout { grid-template-columns: minmax(0, 1fr); }
  .kb-selection-body aside { border-left: 0; border-top: 1px solid var(--wb-line); }
  .kb-selection-body > * { padding: 18px; }
  .kb-processing-chain { padding: 18px; gap: 16px 10px; }
  .kb-processing-chain li { padding: 0 8px; }
  .kb-pending-task { flex-wrap: wrap; padding: 18px; }
  .kb-pending-task > .el-button { margin-left: auto; }
  .kb-row-actions { gap: 14px; }
  .kb-search-controls, .kb-result { padding: 20px; }
}
</style>
