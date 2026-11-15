<template>
  <section class="knowledge-document-workspace" :aria-busy="loading" aria-label="文档工作区">
    <el-button class="kdw-back" text :icon="Back" @click="emit('back')">返回文档资料</el-button>

    <div v-if="loading && !workspace" class="kdw-empty" role="status">
      <el-icon class="is-loading"><Loading /></el-icon>
      <p>正在读取文档与处理方案…</p>
    </div>
    <div v-else-if="loadError && !workspace" class="kdw-empty" role="alert">
      <el-icon><Warning /></el-icon>
      <h2>文档暂时无法读取</h2>
      <p>{{ loadError }}</p>
      <el-button :icon="Refresh" @click="loadDocument">重新读取</el-button>
    </div>

    <template v-if="workspace">
      <header class="kdw-document-heading">
        <div>
          <h1>{{ workspace.name }}</h1>
          <p>{{ formatLabel }} · {{ formatBytes(workspace.size) }}<template v-if="workspace.page_count"> · {{ workspace.page_count }} 页</template><template v-if="workspace.modified"> · 更新于 {{ formatDate(workspace.modified) }}</template></p>
        </div>
        <el-button v-if="workspace.source_url" tag="a" :href="workspace.source_url" target="_blank" rel="noopener noreferrer" :icon="TopRight">打开原始文件</el-button>
      </header>

      <ol class="kdw-processing-chain" aria-label="文档处理状态">
        <li v-for="step in processingSteps" :key="step.view">
          <button type="button" @click="navigate(step.view)"><span>{{ step.number }}</span>{{ step.label }}</button>
          <small>{{ step.detail }}</small>
        </li>
      </ol>
      <p v-if="loadError" class="kdw-error" role="alert">{{ loadError }} <el-button text @click="refreshDocument">重新读取</el-button></p>

      <el-tabs v-model="activeView" class="kdw-tabs">
        <el-tab-pane v-for="readingView in readingViews" :key="readingView.name" :label="readingView.label" :name="readingView.name">
          <section v-if="activeView === readingView.name" class="kdw-panel kdw-reading-panel" :aria-label="readingView.label">
            <div class="kdw-reading-tools">
              <div class="kdw-page-tools">
                <el-button :icon="ArrowLeft" :disabled="!previousPage" aria-label="上一页" @click="navigate(activeView, previousPage.number)" />
                <el-select :model-value="currentPage?.number" aria-label="选择原文页码" :disabled="!pages.length" @update:model-value="navigate(activeView, $event)">
                  <el-option v-for="sourcePage in pages" :key="sourcePage.number" :label="`第 ${sourcePage.number} 页`" :value="sourcePage.number" />
                </el-select>
                <span>/ {{ workspace.page_count || pages.length }} 页</span>
                <el-button :icon="ArrowRight" :disabled="!nextPage" aria-label="下一页" @click="navigate(activeView, nextPage.number)" />
              </div>
              <div v-if="readingView.name === 'source'" class="kdw-page-tools">
                <el-button :icon="Minus" :disabled="zoom <= 50" aria-label="缩小原文页面" @click="zoom -= 25" />
                <span>{{ zoom }}%</span>
                <el-button :icon="Plus" :disabled="zoom >= 175" aria-label="放大原文页面" @click="zoom += 25" />
                <el-button text @click="zoom = 100">重置缩放</el-button>
                <el-button text :aria-expanded="sourceInfoOpen" aria-controls="kdw-source-info" @click="sourceInfoOpen = !sourceInfoOpen">{{ sourceInfoOpen ? '收起来源' : '展开来源' }}</el-button>
              </div>
              <el-checkbox v-else v-model="compareSource">对照原页</el-checkbox>
            </div>

            <div v-if="readingView.name === 'source'" class="kdw-source-layout" :class="{ 'is-expanded': !sourceInfoOpen }">
              <div class="kdw-page-stage">
                <img v-if="currentPage?.image_url && !imageError" :key="currentPage.image_url" class="kdw-source-image" :style="{ '--kdw-page-zoom': zoom / 100 }" :src="currentPage.image_url" :alt="`${workspace.name}，原文第 ${currentPage.number} 页`" @error="imageError = true">
                <article v-else-if="currentPage?.text && !currentPage.image_url" class="kdw-source-text" :style="{ fontSize: `${14 * zoom / 100}px` }">{{ currentPage.text }}</article>
                <div v-else class="kdw-empty">
                  <el-icon><Document /></el-icon>
                  <h2>{{ imageError ? '原页图像未能载入' : '此文件没有逐页预览' }}</h2>
                  <p>可打开原始文件核对，或切换到解析结果查看已提取的正文。</p>
                  <el-button v-if="imageError" @click="imageError = false">重试原页图像</el-button>
                </div>
              </div>
              <aside v-if="sourceInfoOpen" id="kdw-source-info" class="kdw-source-info">
                <h2>原文来源</h2>
                <dl><dt>当前页</dt><dd>{{ currentPage ? `第 ${currentPage.number} / ${workspace.page_count || pages.length} 页` : '无逐页信息' }}</dd><dt>文件</dt><dd>{{ workspace.name }}</dd><dt>格式</dt><dd>{{ formatLabel }}</dd><dt>大小</dt><dd>{{ formatBytes(workspace.size) }}</dd></dl>
                <h3>核对本页正文</h3>
                <p>{{ sourceTextSummary }}</p>
                <el-button text @click="navigate(workspace.parsed?.available ? 'parsed' : 'index')">{{ workspace.parsed?.available ? '查看解析结果' : '核对解析方案' }} <el-icon><ArrowRight /></el-icon></el-button>
                <el-button v-if="workspace.parsed?.available" text @click="navigate('index')">查看处理方案 <el-icon><ArrowRight /></el-icon></el-button>
              </aside>
            </div>

            <div v-else class="kdw-parsed-layout" :class="{ 'is-text-only': !compareSource }">
              <section class="kdw-parsed-pane" aria-label="解析正文">
                <div class="kdw-pane-label"><span>{{ exactPageMapping && currentPage ? `解析正文 · 第 ${currentPage.number} 页` : '解析正文 · 完整正文' }}</span><span>{{ characterCount(parsedText) }} 字符</span></div>
                <p v-if="workspace.parsed?.available && !exactPageMapping" class="kdw-mapping-note">当前解析结果没有可靠的逐页对应，展示完整正文；可开启“对照原页”，独立翻阅核对。</p>
                <div class="kdw-text-scroll">
                  <article v-if="parsedText" class="kdw-parsed-text">{{ parsedText }}</article>
                  <div v-else class="kdw-empty kdw-empty-inline">
                    <h2>{{ workspace.parsed?.available ? '本页没有可复制文字' : '尚无可用解析正文' }}</h2>
                    <p>原始文件保留供核对。可先确认解析方式，再主动执行解析。</p>
                    <el-button @click="navigate('index')">核对解析方案</el-button>
                    <el-button type="primary" :loading="parsing" :disabled="busy || configDirty" @click="parseDocument">按已保存方案解析</el-button>
                    <p v-if="configDirty">方案有未保存修改，请先保存。</p>
                  </div>
                </div>
                <footer class="kdw-parsed-footer"><span>{{ parserLabel }}<template v-if="exactPageMapping && currentPage"> · 第 {{ currentPage.number }} 页</template></span><el-button text :disabled="!workspace.parsed?.available" @click="navigate('chunks')">{{ exactPageMapping ? '查看本页切块' : '查看切块预览' }} <el-icon><ArrowRight /></el-icon></el-button></footer>
              </section>
              <section v-if="compareSource" class="kdw-compare-pane" aria-label="原页对照">
                <div class="kdw-pane-label">原始文件<template v-if="currentPage"> · 第 {{ currentPage.number }} 页</template></div>
                <div class="kdw-page-stage">
                  <img v-if="currentPage?.image_url && !imageError" :key="currentPage.image_url" class="kdw-compare-image" :src="currentPage.image_url" :alt="`${workspace.name}，原文第 ${currentPage.number} 页`" @error="imageError = true">
                  <article v-else-if="currentPage?.text && !currentPage.image_url" class="kdw-source-text">{{ currentPage.text }}</article>
                  <div v-else class="kdw-empty"><p>{{ imageError ? '原页图像未能载入，请打开原始文件核对。' : '此文件没有逐页图像。' }}</p><el-button v-if="imageError" @click="imageError = false">重试原页图像</el-button></div>
                </div>
              </section>
            </div>
          </section>
        </el-tab-pane>

        <el-tab-pane label="切块预览" name="chunks">
          <section v-if="activeView === 'chunks'" class="kdw-panel" aria-label="切块预览">
            <div v-if="!previewValid && preview" class="kdw-stale" role="status"><span>正文或切块参数已改变，旧预览已失效。重新生成后可继续核对正文与来源。</span><el-button :loading="previewLoading" :disabled="!canPreview" @click="generatePreview">重新生成预览</el-button></div>
            <div class="kdw-chunks-layout">
              <section class="kdw-chunk-config" :class="{ 'is-collapsed': !chunkConfigOpen }" aria-label="切块配置">
                <button type="button" class="kdw-mobile-config-toggle" :aria-expanded="chunkConfigOpen" aria-controls="kdw-chunk-config-form" @click="chunkConfigOpen = !chunkConfigOpen"><span><strong>切块配置</strong><small>目标 {{ config.size ?? '—' }} · 重叠 {{ config.overlap ?? '—' }} 字符</small></span><span>{{ chunkConfigOpen ? '收起' : '调整' }} <el-icon><component :is="chunkConfigOpen ? ArrowUp : ArrowDown" /></el-icon></span></button>
                <form id="kdw-chunk-config-form" class="kdw-chunk-config-form" novalidate @submit.prevent="generatePreview">
                <h2>切块配置</h2><p class="kdw-subtle">按正文字符试切，检查条款边界和重叠内容。</p>
                <el-form :model="config" label-position="top" tag="div">
                  <el-form-item label="切分边界" label-for="kdw-boundary"><el-select id="kdw-boundary" v-model="config.boundary"><el-option label="优先句末 / 换行" value="sentence" /><el-option label="固定字符长度" value="fixed" /></el-select></el-form-item>
                  <el-form-item label="目标长度（字符）" label-for="kdw-size"><el-input-number id="kdw-size" v-model="config.size" :min="100" :max="3000" :step="1" :precision="0" controls-position="right" /><small>100–3,000 个 Unicode 字符</small></el-form-item>
                  <el-form-item label="重叠长度（字符）" label-for="kdw-overlap"><el-input-number id="kdw-overlap" v-model="config.overlap" :min="0" :max="1000" :step="1" :precision="0" controls-position="right" /><small>须小于目标长度，且不超过 1,000</small></el-form-item>
                </el-form>
                <el-button class="kdw-wide-button" type="primary" native-type="submit" :icon="Refresh" :loading="previewLoading" :disabled="!workspace.parsed?.available || busy">生成切块预览</el-button>
                <p v-if="configError" class="kdw-error" role="alert">{{ configError }}</p>
                <p v-if="previewError" class="kdw-error" role="alert">{{ previewError }}</p>
                <div class="kdw-config-summary"><p>预览按字符计算，用于核对正文与来源。预览块数不代表已写入的向量记录数。</p><el-button text @click="navigate('index')">查看索引方案 <el-icon><ArrowRight /></el-icon></el-button></div>
                </form>
              </section>

              <section class="kdw-chunk-list-pane" aria-label="预览切块列表" :aria-busy="previewLoading">
                <div class="kdw-chunk-list-tools"><el-input v-model="chunkQuery" :prefix-icon="Search" clearable placeholder="搜索块内正文" aria-label="搜索切块正文" :disabled="!previewValid" /><p><span>{{ previewValid ? `${filteredChunks.length} / ${preview.total} 个预览块` : previewLoading ? '正在生成…' : '待生成预览' }}</span><el-button v-if="chunkQuery" text @click="chunkQuery = ''">清除</el-button></p><div class="kdw-mobile-chunk-select"><el-select :model-value="selectedChunk?.id" aria-label="选择切块" :disabled="!previewValid || !filteredChunks.length" :placeholder="previewValid && !filteredChunks.length ? '没有匹配的切块' : '选择切块'" @update:model-value="selectChunkById"><el-option v-for="chunk in filteredChunks" :key="chunk.id" :label="`块 ${String(chunk.number).padStart(2, '0')} · ${pageLabel(chunk)} · ${characterCount(chunk.text)} 字符`" :value="chunk.id" /></el-select></div></div>
                <div ref="chunkListElement" class="kdw-chunk-list">
                  <template v-if="previewValid && filteredChunks.length"><button v-for="chunk in filteredChunks" :key="chunk.id" type="button" class="kdw-chunk-row" :data-chunk-id="chunk.id" :aria-pressed="selectedChunk?.id === chunk.id" @click="selectChunk(chunk)"><span><strong>块 {{ String(chunk.number).padStart(2, '0') }}</strong><small>{{ pageLabel(chunk) }}</small></span><p>{{ chunk.text }}</p></button></template>
                  <div v-else class="kdw-empty kdw-empty-inline"><p>{{ previewLoading ? '正在读取服务端切块结果…' : previewValid ? '没有匹配的切块。' : '生成预览后显示实际切块。' }}</p><el-button v-if="chunkQuery && previewValid" @click="chunkQuery = ''">恢复全部切块</el-button></div>
                </div>
              </section>

              <section class="kdw-chunk-detail" aria-label="选中切块正文">
                <template v-if="previewValid && selectedChunk">
                  <header class="kdw-chunk-detail-head"><div><h2>块 {{ String(selectedChunk.number).padStart(2, '0') }} · 正文</h2><span class="kdw-tag">{{ selectedChunk.overlap ? `含重叠 ${selectedChunk.overlap} 字符` : selectedChunk.number === 1 ? '首块' : '无重叠' }}</span></div><p class="kdw-chunk-meta"><span>{{ characterCount(selectedChunk.text) }} 字符</span><span>{{ pageLabel(selectedChunk) }}</span><span>偏移 {{ selectedChunk.start }}–{{ selectedChunk.end }}（左闭右开）</span></p><p v-if="selectedChunk.overlap" class="kdw-overlap-key"><span aria-hidden="true" />浅蓝底为与上一块重复的内容，竖线后为新增正文。</p></header>
                  <div class="kdw-text-scroll"><article class="kdw-chunk-text"><template v-if="selectedChunk.overlap"><mark class="kdw-chunk-overlap">{{ selectedChunkText.overlap }}</mark><span class="kdw-overlap-divider" aria-hidden="true" /></template>{{ selectedChunkText.body }}</article></div>
                  <footer class="kdw-chunk-footer"><el-button v-if="selectedChunk.pages?.length" text @click="navigate('source', selectedChunk.pages[0])">原文第 {{ selectedChunk.pages[0] }} 页 <el-icon><TopRight /></el-icon></el-button><span v-else class="kdw-subtle">来源页码未可靠映射</span><el-button text @click="navigate('parsed', selectedChunk.pages?.[0] || currentPage?.number)">解析正文 <el-icon><ArrowRight /></el-icon></el-button></footer>
                </template>
                <div v-else class="kdw-empty"><el-icon><component :is="previewLoading ? Loading : Document" :class="{ 'is-loading': previewLoading }" /></el-icon><h2>{{ previewLoading ? '正在生成切块预览' : !workspace.parsed?.available ? '请先核对解析正文' : preview && !previewValid ? '预览需要更新' : previewValid ? '没有匹配正文' : '开始核对切块边界' }}</h2><p>{{ !workspace.parsed?.available ? '当前没有可用于切块的解析正文。' : previewError ? '生成失败，配置和阅读位置已保留，可重新生成。' : '按当前配置生成服务端预览，再选择切块查看正文与来源。' }}</p><el-button v-if="!workspace.parsed?.available" @click="navigate('parsed')">查看解析结果</el-button></div>
              </section>
            </div>
          </section>
        </el-tab-pane>

        <el-tab-pane label="索引信息" name="index">
          <section v-if="activeView === 'index'" class="kdw-panel kdw-index-layout" aria-label="索引与处理方案">
            <div class="kdw-index-main">
              <h2>选择文档的索引方案</h2><p class="kdw-subtle">方案决定内容的组织层级。保存方案后，可继续核对正文与预览切块。</p>
              <el-radio-group v-model="config.index" class="kdw-index-options" aria-label="索引层级">
                <div class="kdw-index-option" :class="{ 'is-selected': config.index === 'document' }"><el-radio value="document" label="document">文档级索引</el-radio><p>将标题与整篇正文作为一个检索单元，适合先确认整份资料的相关性。</p><small>按整份文档建立检索内容</small></div>
                <div class="kdw-index-option" :class="{ 'is-selected': config.index === 'hierarchical', 'is-unavailable': !capabilities.hierarchical_index }"><el-radio value="hierarchical" label="hierarchical" :disabled="!capabilities.hierarchical_index">分级索引 <span v-if="!capabilities.hierarchical_index" class="kdw-unavailable-label">当前不可用</span></el-radio><p>按文档、章节、切块与摘要组织内容，便于不同粒度的定位。</p><small>{{ capabilities.hierarchical_index ? '文档 / 章节 / 切块 / 摘要' : '当前文档处理接口未开放分级构建' }}</small></div>
              </el-radio-group>
              <section class="kdw-index-section">
                <h2>解析与文字识别方案</h2>
                <el-form :model="config" class="kdw-processing-form" label-position="top" @submit.prevent="saveConfig">
                  <el-form-item label="解析方式" label-for="kdw-parser"><el-select id="kdw-parser" v-model="config.parser"><el-option v-for="parser in capabilities.parsers || []" :key="parser.value" :label="`${parser.label}${parser.available ? '' : '（不可用）'}`" :value="parser.value" :disabled="!parser.available" /></el-select></el-form-item>
                  <el-form-item label="OCR 文字识别" label-for="kdw-ocr"><el-select id="kdw-ocr" v-model="config.ocr"><el-option label="随解析方式处理" value="auto" /><el-option label="启用 OCR（扫描件）" value="on" :disabled="!capabilities.ocr" /><el-option label="不使用 OCR（文本件）" value="off" :disabled="!capabilities.ocr" /></el-select></el-form-item>
                </el-form>
                <p class="kdw-subtle">{{ capabilities.ocr ? 'OCR 选项按当前解析服务能力执行。' : 'OCR 用于识别扫描页中的文字。当前服务不支持独立控制 OCR，仅可随解析方式处理。' }}</p>
              </section>
              <section class="kdw-index-section"><h3>处理范围与边界</h3><p>文档级方案以当前资料的完整正文建立检索内容。切块预览用于核对正文与来源，不代表实际入库记录或向量数量。</p><p>保存处理方案、执行解析和写入知识库为独立动作。请确认方案后主动执行。</p></section>
              <section class="kdw-index-section"><h3>当前切块参数</h3><p>{{ config.boundary === 'sentence' ? '优先句末 / 换行' : '固定字符长度' }} · 目标 {{ config.size ?? '未填写' }} 字符 · 重叠 {{ config.overlap ?? '未填写' }} 字符。<el-button text @click="navigate('chunks')">调整并核对预览 <el-icon><ArrowRight /></el-icon></el-button></p></section>
            </div>
            <aside class="kdw-index-side">
              <h2>当前文档方案</h2>
              <dl><dt>资料</dt><dd>{{ formatLabel }}<template v-if="workspace.page_count"> · {{ workspace.page_count }} 页</template></dd><dt>正文</dt><dd>{{ workspace.parsed?.available ? `${characterCount(workspace.parsed.text)} 字符` : '尚未解析' }}</dd><dt>字符预览</dt><dd>{{ previewValid ? `${preview.total} 块` : '待生成 / 更新' }}</dd><dt>预览参数</dt><dd>{{ config.size ?? '—' }} / {{ config.overlap ?? '—' }} 字符</dd><dt>索引层级</dt><dd>{{ config.index === 'hierarchical' ? '分级索引' : '文档级索引' }}</dd><dt>入库状态</dt><dd>{{ workspace.embedded ? '已入库' : '尚未入库' }}</dd></dl>
              <div class="kdw-index-actions"><el-button class="kdw-wide-button" type="primary" :icon="Check" :loading="saving" :disabled="busy || (!configDirty && !!workspace.saved_at)" @click="saveConfig">保存处理方案</el-button><p class="kdw-save-status" role="status">{{ configDirty ? '方案有修改，等待保存' : workspace.saved_at ? `已保存 · ${formatDate(workspace.saved_at)}` : '方案尚未保存' }}</p><p v-if="saveMessage" class="kdw-subtle" role="status">{{ saveMessage }}</p><p v-if="saveError || configError" class="kdw-error" role="alert">{{ saveError || configError }}</p></div>
              <div class="kdw-index-actions"><h3>执行文档处理</h3><p class="kdw-subtle">使用已保存方案。修改选项后请先保存；解析不会自动入库。</p><el-button class="kdw-wide-button" :icon="Refresh" :loading="parsing" :disabled="busy || configDirty" @click="parseDocument">{{ workspace.parsed?.available ? '重新解析文档' : '解析文档' }}</el-button><el-button class="kdw-wide-button" :icon="Upload" :loading="embedding" :disabled="busy || configDirty || !workspace.parsed?.available || !!workspace.embedded" @click="embedDocument">{{ workspace.embedded ? '已写入知识库' : '执行入库' }}</el-button><el-button text :disabled="busy" @click="refreshDocument">刷新处理状态</el-button><p v-if="operationMessage" class="kdw-subtle" role="status">{{ operationMessage }}</p><p v-if="operationError" class="kdw-error" role="alert">{{ operationError }}</p></div>
            </aside>
          </section>
        </el-tab-pane>
      </el-tabs>
      <p v-if="activeView !== 'index' && operationError" class="kdw-error" role="alert">{{ operationError }}</p>
      <p v-if="activeView !== 'index' && operationMessage" class="kdw-subtle" role="status">{{ operationMessage }}</p>
    </template>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Back, Check, Document, Loading, Minus, Plus, Refresh, Search, TopRight, Upload, Warning } from '@element-plus/icons-vue'
import { knowledgeApi } from '@/api'
import '@/styles/knowledge-workspace.css'

const props = defineProps({
  docId: { type: String, required: true },
  view: { type: String, default: 'source' },
  page: { type: Number, default: 1 }
})
const emit = defineEmits(['back', 'navigate', 'updated'])
const readingViews = [{ name: 'source', label: '原文预览' }, { name: 'parsed', label: '解析结果' }]
const configKeys = ['size', 'overlap', 'boundary', 'index', 'parser', 'ocr']
const workspace = ref(null)
const config = reactive({ size: 800, overlap: 100, boundary: 'sentence', index: 'document', parser: 'auto', ocr: 'auto' })
const loading = ref(false)
const loadError = ref('')
const saving = ref(false)
const saveError = ref('')
const saveMessage = ref('')
const parsing = ref(false)
const embedding = ref(false)
const operationError = ref('')
const operationMessage = ref('')
const preview = ref(null)
const previewLoading = ref(false)
const previewError = ref('')
const chunkQuery = ref('')
const chunkConfigOpen = ref(true)
const selectedChunkId = ref(null)
const chunkListElement = ref(null)
const zoom = ref(100)
const sourceInfoOpen = ref(true)
const compareSource = ref(typeof window === 'undefined' || !window.matchMedia('(max-width: 699px)').matches)
const imageError = ref(false)
let documentGeneration = 0
let loadController = null
let previewController = null
let previewGeneration = 0
let readingAnchor = null

const activeView = computed({
  get: () => ['source', 'parsed', 'chunks', 'index'].includes(props.view) ? props.view : 'source',
  set: view => navigate(view)
})
const pages = computed(() => workspace.value?.pages || [])
const currentPageIndex = computed(() => Math.max(0, pages.value.findIndex(page => page.number === props.page)))
const currentPage = computed(() => pages.value[currentPageIndex.value] || null)
const previousPage = computed(() => pages.value[currentPageIndex.value - 1])
const nextPage = computed(() => pages.value[currentPageIndex.value + 1])
const capabilities = computed(() => workspace.value?.capabilities || {})
const formatLabel = computed(() => String(workspace.value?.format || '文件').replace(/^\./, '').toUpperCase())
const exactPageMapping = computed(() => workspace.value?.parsed?.page_mapping === 'exact')
const parsedText = computed(() => {
  if (!workspace.value?.parsed?.available) return ''
  return exactPageMapping.value && currentPage.value ? currentPage.value.text || '' : workspace.value.parsed.text || ''
})
const parserLabel = computed(() => capabilities.value.parsers?.find(parser => parser.value === workspace.value?.parsed?.parser)?.label || workspace.value?.parsed?.parser || '尚未解析')
const sourceTextSummary = computed(() => {
  if (!currentPage.value?.has_text) return '本页没有可复制文字。原页仍可查阅，解析能力与文字识别选项可在索引方案中核对。'
  const text = `原页含 ${characterCount(currentPage.value.text)} 字符的可复制文字`
  return workspace.value?.parsed?.available ? `${text}，可与解析正文对照。` : `${text}；处理正文尚待解析。`
})
const configDirty = computed(() => !!workspace.value && configKeys.some(key => config[key] !== workspace.value.config?.[key]))
const chunkConfigKey = computed(() => JSON.stringify([config.size, config.overlap, config.boundary]))
const configError = computed(() => {
  if (!Number.isInteger(config.size) || config.size < 100 || config.size > 3000) return '目标长度须为 100–3,000 的整数。'
  if (!Number.isInteger(config.overlap) || config.overlap < 0 || config.overlap > 1000 || config.overlap >= config.size) return '重叠长度须为 0–1,000 的整数，且小于目标长度。'
  return ''
})
const busy = computed(() => saving.value || parsing.value || embedding.value)
const canPreview = computed(() => !!workspace.value?.parsed?.available && !configError.value && !previewLoading.value && !busy.value)
const previewValid = computed(() => !!preview.value && preview.value.source_version === workspace.value?.source_version && preview.value.parsed_version === workspace.value?.parsed?.version && preview.value.config.size === config.size && preview.value.config.overlap === config.overlap && preview.value.config.boundary === config.boundary)
const filteredChunks = computed(() => {
  if (!previewValid.value) return []
  const query = chunkQuery.value.trim().toLocaleLowerCase()
  return preview.value.chunks.filter(chunk => chunk.text.toLocaleLowerCase().includes(query))
})
const selectedChunk = computed(() => filteredChunks.value.find(chunk => chunk.id === selectedChunkId.value) || filteredChunks.value[0] || null)
const selectedChunkText = computed(() => {
  const characters = Array.from(selectedChunk.value?.text || '')
  const overlap = selectedChunk.value?.overlap || 0
  return { overlap: characters.slice(0, overlap).join(''), body: characters.slice(overlap).join('') }
})
const processingSteps = computed(() => [
  { number: '01', view: 'source', label: '原始资料', detail: `${workspace.value?.page_count ? `${workspace.value.page_count} 页 · ` : ''}${formatLabel.value} · ${formatBytes(workspace.value?.size)}` },
  { number: '02', view: 'parsed', label: '解析正文', detail: workspace.value?.parsed?.available ? `${characterCount(workspace.value.parsed.text)} 字符 · ${exactPageMapping.value ? '可核对原页' : '完整正文'}` : '等待解析 · 原文保留' },
  { number: '03', view: 'chunks', label: '切块预览', detail: previewValid.value ? `${preview.value.total} 块 · 按正文试切` : '待生成 / 更新预览' },
  { number: '04', view: 'index', label: '索引方案', detail: `${config.index === 'hierarchical' ? '分级索引' : '文档级索引'} · ${configDirty.value ? '有未保存修改' : workspace.value?.saved_at ? '方案已保存' : '待确认方案'}` }
])

function navigate(view, page = currentPage.value?.number || props.page) {
  emit('navigate', { view, page: Number(page) || 1 })
}

function characterCount(text) {
  return Array.from(text || '').length.toLocaleString('zh-CN')
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return '大小未知'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(value) {
  const timestamp = typeof value === 'number' && Math.abs(value) < 1e12 ? value * 1000 : value
  const date = new Date(timestamp)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false })
}

function pageLabel(chunk) {
  if (!chunk.pages?.length) return '页码未映射'
  return chunk.pages.length === 1 ? `第 ${chunk.pages[0]} 页` : `第 ${chunk.pages[0]}–${chunk.pages[chunk.pages.length - 1]} 页`
}

function errorMessage(error, fallback) {
  const detail = error?.response?.data?.detail || error?.response?.data?.message
  if (detail) return typeof detail === 'string' ? detail : fallback
  if (error?.code === 'ERR_NETWORK' || /^Network\s*Error$/i.test(error?.message || '')) return '网络连接异常，当前输入已保留，请检查连接后重试。'
  if (error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT') return fallback
  return typeof error?.message === 'string' ? error.message : fallback
}

function assertSuccess(response, fallback) {
  if (!response || response.success === false) throw new Error(response?.message || response?.detail || fallback)
  return response
}

function copyConfig(source) {
  for (const key of configKeys) config[key] = source[key]
}

function currentDocument(generation, docId) {
  return documentGeneration === generation && props.docId === docId
}

async function readWorkspace(docId, generation) {
  loadController?.abort()
  const controller = new AbortController()
  loadController = controller
  const response = assertSuccess(await knowledgeApi.getDocumentWorkspace(docId, { signal: controller.signal }), '文档读取失败。')
  if (!currentDocument(generation, docId) || controller.signal.aborted) return null
  return response
}

async function loadDocument() {
  const generation = ++documentGeneration
  const docId = props.docId
  loadController?.abort()
  previewController?.abort()
  previewGeneration++
  workspace.value = null
  preview.value = null
  selectedChunkId.value = null
  readingAnchor = null
  chunkQuery.value = ''
  chunkConfigOpen.value = true
  loading.value = true
  loadError.value = ''
  saveError.value = ''
  saveMessage.value = ''
  operationError.value = ''
  operationMessage.value = ''
  previewError.value = ''
  saving.value = false
  parsing.value = false
  embedding.value = false
  previewLoading.value = false
  zoom.value = 100
  imageError.value = false
  try {
    const response = await readWorkspace(docId, generation)
    if (!response) return
    copyConfig(response.config)
    workspace.value = response
    if (activeView.value === 'chunks') await generatePreview()
  } catch (error) {
    if (currentDocument(generation, docId) && error?.code !== 'ERR_CANCELED') loadError.value = errorMessage(error, '请检查连接后重新读取。')
  } finally {
    if (currentDocument(generation, docId)) loading.value = false
  }
}

async function refreshDocument() {
  if (busy.value) return
  const generation = documentGeneration
  const docId = props.docId
  const previousDraft = JSON.stringify(config)
  const preserveDraft = configDirty.value
  loadError.value = ''
  try {
    const response = await readWorkspace(docId, generation)
    if (response) {
      if (!preserveDraft && JSON.stringify(config) === previousDraft) copyConfig(response.config)
      workspace.value = response
    }
  } catch (error) {
    if (currentDocument(generation, docId) && error?.code !== 'ERR_CANCELED') loadError.value = errorMessage(error, '重新读取失败，当前内容已保留。')
  }
}

function selectChunk(chunk) {
  selectedChunkId.value = chunk.id
  readingAnchor = Math.floor((chunk.start + (chunk.overlap || 0) + chunk.end - 1) / 2)
  if (chunk.pages?.length && !chunk.pages.includes(currentPage.value?.number)) navigate('chunks', chunk.pages[0])
}

function selectChunkById(chunkId) {
  const chunk = filteredChunks.value.find(item => item.id === chunkId)
  if (chunk) selectChunk(chunk)
}

async function generatePreview() {
  if (!canPreview.value) return
  const generation = documentGeneration
  const requestGeneration = ++previewGeneration
  const docId = props.docId
  const previous = preview.value?.chunks.find(chunk => chunk.id === selectedChunkId.value)
  const anchor = readingAnchor ?? (previous ? Math.floor((previous.start + (previous.overlap || 0) + previous.end - 1) / 2) : null)
  const payload = { size: config.size, overlap: config.overlap, boundary: config.boundary, source_version: workspace.value.source_version, parsed_version: workspace.value.parsed.version }
  previewController?.abort()
  const controller = new AbortController()
  previewController = controller
  previewLoading.value = true
  previewError.value = ''
  try {
    const response = assertSuccess(await knowledgeApi.previewChunks(docId, payload, { signal: controller.signal }), '切块预览生成失败。')
    if (!currentDocument(generation, docId) || requestGeneration !== previewGeneration || controller.signal.aborted) return
    if (response.source_version !== payload.source_version || response.parsed_version !== payload.parsed_version) throw new Error('正文已更新，请重新读取文档后生成预览。')
    preview.value = response
    const anchored = anchor === null ? null : response.chunks.find(chunk => chunk.start + (chunk.overlap || 0) <= anchor && chunk.end > anchor) || response.chunks.find(chunk => chunk.start <= anchor && chunk.end > anchor)
    const selected = anchored || response.chunks.find(chunk => chunk.pages?.includes(currentPage.value?.number)) || response.chunks[0]
    selectedChunkId.value = selected?.id || null
    if (selected) readingAnchor = anchor ?? selected.start
    chunkQuery.value = ''
    chunkConfigOpen.value = false
    await nextTick()
    if (currentDocument(generation, docId) && requestGeneration === previewGeneration) chunkListElement.value?.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: 'nearest' })
  } catch (error) {
    if (currentDocument(generation, docId) && requestGeneration === previewGeneration && error?.code !== 'ERR_CANCELED') previewError.value = errorMessage(error, '生成失败，当前参数与阅读位置已保留。')
  } finally {
    if (currentDocument(generation, docId) && requestGeneration === previewGeneration) previewLoading.value = false
  }
}

async function saveConfig() {
  if (busy.value || configError.value) return
  const generation = documentGeneration
  const docId = props.docId
  const submitted = Object.fromEntries(configKeys.map(key => [key, config[key]]))
  const payload = { ...submitted, source_version: workspace.value.source_version, revision: workspace.value.config_revision }
  saving.value = true
  saveError.value = ''
  saveMessage.value = ''
  try {
    const response = assertSuccess(await knowledgeApi.saveProcessingConfig(docId, payload), '处理方案保存失败。')
    if (!currentDocument(generation, docId)) return
    const verified = await readWorkspace(docId, generation)
    if (!verified) return
    workspace.value = verified
    if (String(verified.config_revision) !== String(response.revision) || verified.source_version !== payload.source_version || configKeys.some(key => verified.config[key] !== response.config[key])) throw new Error('方案已提交，但读回结果已发生变化。当前输入已保留，请核对后重新保存。')
    // Inputs can change during the request; only adopt the readback when this draft is still the submitted one.
    if (configKeys.every(key => config[key] === submitted[key])) copyConfig(verified.config)
    saveMessage.value = configDirty.value ? '已保存提交时的方案；后续修改仍保留，等待保存。' : '处理方案已保存并读回核对。'
    emit('updated')
  } catch (error) {
    if (!currentDocument(generation, docId)) return
    saveError.value = errorMessage(error, '保存或读回核验失败，当前输入已保留。')
    if (error?.response?.status === 409) {
      saveError.value = '原文或方案已被更新，本次没有覆盖。当前输入已保留，正在读取最新版本；请核对后重新保存。'
      try {
        const latest = await readWorkspace(docId, generation)
        if (latest) workspace.value = latest
      } catch (readError) {
        if (currentDocument(generation, docId)) saveError.value = `版本冲突，最新方案读取失败。当前输入已保留。${errorMessage(readError, '')}`
      }
    }
  } finally {
    if (currentDocument(generation, docId)) saving.value = false
  }
}

async function runDocumentOperation(operation) {
  if (busy.value || configDirty.value || (operation === 'embed' && (!workspace.value?.parsed?.available || workspace.value.embedded))) return
  const generation = documentGeneration
  const docId = props.docId
  const running = operation === 'parse' ? parsing : embedding
  running.value = true
  operationError.value = ''
  operationMessage.value = operation === 'parse' ? '正在按已保存方案解析，原始文件与当前内容保留。' : '正在写入知识库，请等待服务端确认。'
  try {
    const versions = { source_version: workspace.value.source_version, parsed_version: workspace.value.parsed?.version }
    const response = assertSuccess(await (operation === 'parse' ? knowledgeApi.parseDocument(docId, { source_version: versions.source_version }) : knowledgeApi.embedDocument(docId, versions)), operation === 'parse' ? '解析失败。' : '入库失败。')
    if (!currentDocument(generation, docId)) return
    const verified = await readWorkspace(docId, generation)
    if (!verified) return
    workspace.value = verified
    if (operation === 'parse' && !verified.parsed?.available) throw new Error('解析请求已返回，但尚未读到可用正文。请重新读取核对。')
    if (operation === 'embed' && !verified.embedded) throw new Error('入库请求已返回，但尚未确认入库状态。请重新读取核对后再决定是否重试。')
    operationMessage.value = operation === 'parse' ? '解析完成，已重新读取正文。切块预览需按最新正文核对。' : response.message || '文档已写入知识库，并已读回确认。'
    emit('updated')
  } catch (error) {
    if (currentDocument(generation, docId)) {
      operationMessage.value = ''
      operationError.value = errorMessage(error, '处理失败，原文、配置和当前内容已保留。')
    }
  } finally {
    if (currentDocument(generation, docId)) running.value = false
  }
}

function parseDocument() {
  return runDocumentOperation('parse')
}

function embedDocument() {
  return runDocumentOperation('embed')
}

watch(() => props.docId, loadDocument, { immediate: true, flush: 'sync' })
watch(() => props.page, () => { imageError.value = false })
watch(activeView, view => {
  if (view === 'chunks' && workspace.value && !preview.value && !previewLoading.value) generatePreview()
})
watch(filteredChunks, chunks => {
  if (!previewValid.value || !chunks.length || chunks.some(chunk => chunk.id === selectedChunkId.value)) return
  const chunk = chunks[0]
  selectedChunkId.value = chunk.id
  readingAnchor = Math.floor((chunk.start + (chunk.overlap || 0) + chunk.end - 1) / 2)
})
watch(chunkConfigKey, () => {
  previewController?.abort()
  previewGeneration++
  previewLoading.value = false
  previewError.value = ''
  saveMessage.value = ''
}, { flush: 'sync' })
onBeforeUnmount(() => {
  documentGeneration++
  loadController?.abort()
  previewController?.abort()
})
</script>
