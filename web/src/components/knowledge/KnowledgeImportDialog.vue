<script setup>
import { computed, markRaw, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { CircleCheck, Document, InfoFilled, Upload, Close } from '@element-plus/icons-vue'
import { knowledgeApi } from '@/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  documents: { type: Array, default: () => [] },
  capabilities: { type: Object, default: null }
})
const emit = defineEmits(['update:modelValue', 'uploaded', 'draft-change'])

const DRAFT_KEY = 'glyph.knowledge.import.v1'
const MAX_FILES = 20
const MAX_BYTES = 50 * 1024 * 1024
const FILE_PATTERN = /\.(pdf|docx|txt|md)$/i
const entries = ref([])
const options = reactive({ parser: 'auto', ocr: 'auto', index: 'document' })
const uploadRef = ref(null)
const busy = ref(false)
const formError = ref('')
const storageError = ref('')
const storageMessage = ref('')
const selectionIssues = ref([])
const savedAt = ref(null)
const draftDirty = ref(false)
const batchMessage = ref('')
let nextEntryId = 0
let disposed = false
let requestController = null

const visible = computed({
  get: () => props.modelValue,
  set: value => {
    if (!busy.value) emit('update:modelValue', value)
  }
})
const parsers = computed(() => Array.isArray(props.capabilities?.parsers) ? props.capabilities.parsers : [])
const capabilitiesReady = computed(() => parsers.value.length > 0)
const selectedParserAvailable = computed(() => parsers.value.some(parser => parser.value === options.parser && parser.available === true))
const planLocked = computed(() => entries.value.some(entry => entry.docId))
const pendingEntries = computed(() => entries.value.filter(entry => entry.phase !== 'done'))
const completedCount = computed(() => entries.value.length - pendingEntries.value.length)
const missingCount = computed(() => pendingEntries.value.filter(entry => !entry.docId && !entry.file).length)
const submitLabel = computed(() => pendingEntries.value.some(entry => entry.docId) ? '继续完成上传' : '上传资料')
const savedTimeLabel = computed(() => savedAt.value ? new Date(savedAt.value).toLocaleString('zh-CN', { hour12: false }) : '')

function normalizeName(name) {
  return String(name || '').toLocaleLowerCase()
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function parserLabel(value) {
  return parsers.value.find(parser => parser.value === value)?.label || value
}

function markDraftChanged() {
  draftDirty.value = true
  storageMessage.value = ''
  formError.value = ''
  batchMessage.value = ''
}

function emitDraftSummary() {
  emit('draft-change', { count: pendingEntries.value.length, savedAt: savedAt.value })
}

function serializeEntry(entry) {
  return {
    name: entry.name, size: entry.size, modified: entry.modified,
    docId: entry.docId, phase: entry.phase, stage: entry.stage,
    configSaved: entry.configSaved, appliedParser: entry.appliedParser,
    contentLength: entry.contentLength, error: entry.error,
    options: entry.options
  }
}

function persistDraft(showFeedback = false) {
  const timestamp = new Date().toISOString()
  const draft = {
    version: 1, savedAt: timestamp,
    options: { ...options, ocr: 'auto', index: 'document' },
    files: entries.value.map(serializeEntry)
  }
  try {
    const serialized = JSON.stringify(draft)
    window.localStorage.setItem(DRAFT_KEY, serialized)
    if (window.localStorage.getItem(DRAFT_KEY) !== serialized) throw new Error('草稿写入校验未通过')
    savedAt.value = timestamp
    draftDirty.value = false
    storageError.value = ''
    if (showFeedback) storageMessage.value = '任务已保存。保存的是文件清单与处理方案；刷新后未上传的文件需重新选择。'
    emitDraftSummary()
    return true
  } catch {
    storageError.value = '任务保存失败，当前文件与选项仍保留在此窗口。请检查浏览器存储后重试。'
    draftDirty.value = true
    emitDraftSummary()
    return false
  }
}

function restoreDraft() {
  try {
    const serialized = window.localStorage.getItem(DRAFT_KEY)
    if (!serialized) return
    const draft = JSON.parse(serialized)
    if (draft?.version !== 1 || !Array.isArray(draft.files) || draft.files.length > MAX_FILES) {
      throw new Error('草稿格式不受支持')
    }
    const names = new Set()
    const restored = []
    for (const saved of draft.files) {
      if (!saved || typeof saved.name !== 'string' || !FILE_PATTERN.test(saved.name) ||
          !Number.isFinite(saved.size) || saved.size <= 0 || saved.size > MAX_BYTES ||
          names.has(normalizeName(saved.name))) throw new Error('草稿文件清单无效')
      names.add(normalizeName(saved.name))
      const docId = typeof saved.docId === 'string' && saved.docId ? saved.docId : null
      const done = docId && saved.phase === 'done'
      restored.push({
        id: ++nextEntryId, name: saved.name, size: saved.size,
        modified: Number.isFinite(saved.modified) ? saved.modified : 0,
        file: null, docId, phase: done ? 'done' : docId ? 'uploaded' : 'pending',
        stage: docId ? saved.configSaved ? 'parse' : 'config' : 'upload',
        configSaved: Boolean(docId && saved.configSaved),
        appliedParser: typeof saved.appliedParser === 'string' ? saved.appliedParser : '',
        contentLength: Number.isFinite(saved.contentLength) ? saved.contentLength : null,
        error: '', resultText: '',
        options: docId && saved.options ? {
          parser: typeof saved.options.parser === 'string' ? saved.options.parser : 'auto',
          ocr: 'auto', index: 'document'
        } : null
      })
    }
    if (typeof draft.options?.parser === 'string') options.parser = draft.options.parser
    entries.value = restored
    savedAt.value = typeof draft.savedAt === 'string' && !Number.isNaN(Date.parse(draft.savedAt)) ? draft.savedAt : null
    storageMessage.value = restored.some(entry => !entry.docId)
      ? '已恢复任务清单和处理方案。文件内容未存入浏览器，请重新选择清单中的原文件。'
      : '已恢复任务记录。已上传的资料会从保存配置或解析阶段继续，不会重复上传。'
  } catch {
    storageError.value = '未能读取已保存的任务，原存储记录未被删除。可以重新选择文件并保存一份新任务。'
  } finally {
    emitDraftSummary()
  }
}

function fileValidationError(file) {
  if (!FILE_PATTERN.test(file.name)) return /\.doc$/i.test(file.name) ? '暂不支持 DOC，请转换为 DOCX 或 PDF' : '格式不支持，请选择 PDF、DOCX、TXT 或 Markdown'
  if (file.size === 0) return '文件为空'
  if (file.size > MAX_BYTES) return '超过单个文件 50 MB 的上限'
  return ''
}

function existingDocument(entry) {
  return props.documents.find(document => normalizeName(document.name || document.doc_id || document.id) === normalizeName(entry.name) &&
    String(document.doc_id || document.id || '') !== String(entry.docId || ''))
}

function addFile(uploadFile) {
  const file = uploadFile.raw
  uploadRef.value?.clearFiles()
  if (!file || busy.value) return
  const error = fileValidationError(file)
  const matching = entries.value.find(entry => normalizeName(entry.name) === normalizeName(file.name))
  let issue = error
  if (!issue && matching) {
    if (!matching.docId && matching.size === file.size && matching.modified === file.lastModified) {
      if (matching.file) issue = '已在清单中，已合并重复选择'
      else {
        matching.file = markRaw(file)
        matching.error = ''
        matching.phase = 'pending'
        markDraftChanged()
      }
    } else issue = matching.docId ? '该资料已经上传，无需再次选择' : '清单中已有同名文件，请移除原条目或重命名后选择'
  } else if (!issue && existingDocument({ name: file.name })) {
    issue = '知识库已有同名资料，请重命名后上传；不会覆盖已有资料'
  } else if (!issue && entries.value.length >= MAX_FILES) {
    issue = '本次最多保留 20 个文件，请先移除不需要的条目'
  } else if (!issue) {
    entries.value.push({
      id: ++nextEntryId, name: file.name, size: file.size, modified: file.lastModified,
      file: markRaw(file), docId: null, phase: 'pending', stage: 'upload',
      configSaved: false, appliedParser: '', contentLength: null,
      error: '', resultText: '', options: null
    })
    markDraftChanged()
  }
  if (issue) selectionIssues.value = [...selectionIssues.value.slice(-19), `${file.name}：${issue}`]
  emitDraftSummary()
}

function removeEntry(entry) {
  if (busy.value) return
  entries.value = entries.value.filter(item => item.id !== entry.id)
  markDraftChanged()
  // 已有存储记录时同步移除，避免刷新后已移除的任务重新出现。
  if (savedAt.value) persistDraft()
  emitDraftSummary()
}

function statusLabel(entry) {
  if (entry.phase === 'uploading') return '上传并解析中'
  if (entry.phase === 'saving') return '正在保存处理方案'
  if (entry.phase === 'parsing') return '正在应用解析方案'
  if (entry.phase === 'done') return '已完成'
  if (entry.phase === 'error') return entry.docId ? entry.stage === 'parse' ? '已上传 · 解析失败' : '已上传 · 配置待保存' : '上传失败'
  if (entry.docId) return entry.configSaved ? '上传已完成 · 待应用方案' : '上传已完成 · 待保存方案'
  return entry.file ? '待上传' : '需重新选择文件'
}

function validateSubmission() {
  if (!pendingEntries.value.length) return '请先选择要上传的资料。'
  if (!capabilitiesReady.value) return '解析能力尚未读取成功，请等待或在资料列表刷新后重试。'
  if (!selectedParserAvailable.value) return '当前解析方式不可用，请选择可用方案后继续。'
  if (missingCount.value) return `还有 ${missingCount.value} 份资料需要重新选择原文件。已上传的资料无需重选。`
  for (const entry of pendingEntries.value) {
    if (!entry.docId && existingDocument(entry)) return `「${entry.name}」已存在于知识库，请移除本次条目或重命名；已有资料不会被覆盖。`
    const parser = entry.options?.parser || options.parser
    if (!parsers.value.some(item => item.value === parser && item.available === true)) return `「${entry.name}」保存的解析方式当前不可用。`
    if (parser === 'text' && !/\.(txt|md)$/i.test(entry.name)) return '直接文本读取只适用于 TXT / Markdown，请调整解析方式。'
    if (parser === 'mineru' && !/\.pdf$/i.test(entry.name)) return 'MinerU 解析仅适用于 PDF，请调整解析方式。'
  }
  return ''
}

function saveTask() {
  if (busy.value) return
  formError.value = ''
  if (!entries.value.length) {
    formError.value = '请先选择至少一份资料，再保存待提交任务。'
    return
  }
  if (!selectedParserAvailable.value) {
    formError.value = '解析能力尚未读取成功或所选解析器不可用，处理方案暂不能保存。'
    return
  }
  const invalidParser = pendingEntries.value.find(entry =>
    options.parser === 'text' && !/\.(txt|md)$/i.test(entry.name) ||
    options.parser === 'mineru' && !/\.pdf$/i.test(entry.name))
  if (invalidParser) {
    formError.value = `「${invalidParser.name}」不支持当前解析方式，请调整后保存。`
    return
  }
  persistDraft(true)
}

function errorMessage(error) {
  const detail = error?.response?.data?.detail || error?.response?.data?.message
  if (typeof detail === 'string' && !/^Network Error$/i.test(detail)) return detail
  if (Array.isArray(detail)) return detail.map(item => item.msg || '请求参数不符合要求').join('；')
  if (error?.code === 'ERR_NETWORK' || /^Network Error$/i.test(error?.message || detail || '')) return '网络连接异常，请检查连接后重试'
  if (['ECONNABORTED', 'ETIMEDOUT'].includes(error?.code) || /timeout|timed out/i.test(error?.message || '')) return '请求超时，请稍后重试'
  return error?.message || '请求未完成，请稍后重试'
}

function recordWorkspace(entry, workspace) {
  if (workspace?.success !== true || !workspace.source_version || workspace.config_revision == null) throw new Error('工作区版本信息不完整，请刷新后重试')
  if (workspace.parsed?.available) {
    entry.contentLength = workspace.parsed.content_length ?? null
    entry.appliedParser = workspace.parsed.parser || ''
    entry.resultText = typeof workspace.parsed.text === 'string' ? workspace.parsed.text.slice(0, 1400) : ''
  }
}

async function processEntry(entry, signal) {
  entry.error = ''
  entry.options ||= { ...options, ocr: 'auto', index: 'document' }
  try {
    if (!entry.docId) {
      entry.stage = 'upload'
      entry.phase = 'uploading'
      const form = new FormData()
      form.append('file', entry.file)
      const uploaded = await knowledgeApi.uploadDocument(form, { signal })
      if (uploaded?.success !== true || typeof uploaded.doc_id !== 'string' || !uploaded.doc_id) throw new Error('上传响应未确认成功，请核对资料列表后重试')
      entry.docId = uploaded.doc_id
      entry.contentLength = uploaded.content_length ?? null
      entry.stage = 'config'
      entry.phase = 'uploaded'
      persistDraft()
      emit('uploaded', entry.docId)
    }
    if (disposed) return
    entry.stage = entry.configSaved ? 'parse' : 'config'
    entry.phase = entry.configSaved ? 'parsing' : 'saving'
    const workspace = await knowledgeApi.getDocumentWorkspace(entry.docId, { signal })
    recordWorkspace(entry, workspace)
    if (disposed) return
    if (!entry.configSaved) {
      const result = await knowledgeApi.saveProcessingConfig(entry.docId, {
        size: 800, overlap: 100, boundary: 'sentence', index: 'document',
        parser: entry.options.parser, ocr: 'auto',
        source_version: workspace.source_version, revision: workspace.config_revision
      })
      if (result?.success !== true) throw new Error('处理方案保存未确认成功，请重试保存')
      entry.configSaved = true
      entry.stage = 'parse'
      persistDraft()
    }
    if (disposed) return
    // 上传已按 auto 生成解析缓存；仅缓存缺失或选定其他方案时再次解析。
    if (!workspace.parsed?.available || entry.options.parser !== 'auto' && entry.appliedParser !== entry.options.parser) {
      entry.phase = 'parsing'
      const result = await knowledgeApi.parseDocument(entry.docId, {
        parser: entry.options.parser, ocr: 'auto', source_version: workspace.source_version, signal
      })
      if (result?.success !== true) throw new Error('解析未确认成功，请重试应用解析方案')
      entry.appliedParser = entry.options.parser
      entry.contentLength = result.content_length ?? entry.contentLength
      entry.resultText = ''
      persistDraft()
    }
    if (disposed) return
    entry.phase = 'done'
    entry.error = ''
    persistDraft()
    emit('uploaded', entry.docId)
  } catch (error) {
    entry.phase = 'error'
    const prefix = entry.docId
      ? entry.stage === 'parse' ? '资料已上传，解析方案尚未完成：' : '资料已上传，处理方案尚未保存：'
      : error?.response?.status === 409 ? '同名资料已存在，未覆盖：' : '上传未完成：'
    entry.error = `${prefix}${errorMessage(error)}`
    if (!entry.docId && !error?.response) entry.error += '。若连接中断，请先在资料列表核对上传结果。'
    persistDraft()
  }
}

async function submitFiles() {
  if (busy.value) return
  formError.value = validateSubmission()
  if (formError.value) return
  busy.value = true
  batchMessage.value = ''
  storageMessage.value = ''
  requestController = new AbortController()
  const batch = [...pendingEntries.value]
  try {
    for (const entry of batch) {
      if (disposed) break
      await processEntry(entry, requestController.signal)
    }
    if (!disposed) {
      const failed = batch.filter(entry => entry.phase !== 'done').length
      batchMessage.value = failed
        ? `本次已完成 ${batch.length - failed} 份，${failed} 份尚未完成。文件与已上传记录均已保留，请查看对应条目。`
        : `本次 ${batch.length} 份资料已上传并保存处理方案。可在下方查看结果，后续由文档工作区管理索引。`
    }
  } finally {
    busy.value = false
    requestController = null
    emitDraftSummary()
  }
}

function beforeClose(done) {
  if (busy.value) {
    formError.value = '资料正在处理中，请等待当前任务结束后再关闭。'
    return
  }
  done()
}

function guardUnload(event) {
  if (!busy.value) return
  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave(() => {
  if (!busy.value) return true
  formError.value = '资料正在处理中，请等待当前任务结束后再离开。'
  return false
})

watch(() => props.modelValue, value => {
  if (!value && busy.value) emit('update:modelValue', true)
})

onMounted(() => {
  restoreDraft()
  window.addEventListener('beforeunload', guardUnload)
})
onBeforeUnmount(() => {
  disposed = true
  if (busy.value) persistDraft()
  requestController?.abort()
  window.removeEventListener('beforeunload', guardUnload)
})
</script>

<template>
  <el-dialog
    v-model="visible"
    class="glyph-dialog knowledge-import-dialog"
    title="上传资料"
    width="760px"
    :close-on-click-modal="false"
    :close-on-press-escape="!busy"
    :show-close="!busy"
    :destroy-on-close="false"
    :before-close="beforeClose"
    align-center
  >
    <p class="import-intro">选择文件、核对处理方案，也可以保存为待提交任务。</p>
    <el-form class="import-form" label-position="top" :disabled="busy" @submit.prevent="submitFiles">
      <section class="import-section" aria-labelledby="import-files-heading">
        <div class="section-heading">
          <h3 id="import-files-heading"><span>1</span>选择文件</h3>
          <span class="file-count">{{ entries.length }} / {{ MAX_FILES }} 份</span>
        </div>
        <el-upload
          ref="uploadRef"
          class="import-upload"
          action=""
          accept=".pdf,.docx,.txt,.md"
          multiple
          drag
          :auto-upload="false"
          :show-file-list="false"
          :disabled="busy"
          :on-change="addFile"
          aria-label="选择或拖入资料文件"
        >
          <el-icon class="upload-icon" aria-hidden="true"><Upload /></el-icon>
          <div class="upload-label">选择文件<span>或将文件拖到此处</span></div>
          <p>PDF、DOCX、TXT、Markdown · 单个不超过 50 MB</p>
        </el-upload>
        <p class="import-note">最多 20 份，可继续添加；重复选择会合并。DOC 请先转换为 DOCX 或 PDF。</p>
        <div v-if="selectionIssues.length" class="selection-feedback" role="status">
          <div class="feedback-heading"><span>文件选择反馈</span><el-button text size="small" :disabled="busy" @click="selectionIssues = []">收起</el-button></div>
          <ul><li v-for="(issue, index) in selectionIssues" :key="index">{{ issue }}</li></ul>
        </div>
        <ul v-if="entries.length" class="import-files" aria-label="本次导入文件" :aria-busy="busy">
          <li v-for="entry in entries" :key="entry.id">
            <div class="file-row">
              <el-icon class="file-icon" :class="{ 'is-pdf': /\.pdf$/i.test(entry.name) }" aria-hidden="true"><Document /></el-icon>
              <div class="file-identity">
                <strong>{{ entry.name }}</strong>
                <small>{{ formatBytes(entry.size) }}<template v-if="entry.docId"> · 已保留上传记录</template></small>
              </div>
              <span class="file-status" :class="{ 'is-error': entry.phase === 'error', 'is-done': entry.phase === 'done' }">
                <el-icon v-if="entry.phase === 'done'" aria-hidden="true"><CircleCheck /></el-icon>{{ statusLabel(entry) }}
              </span>
              <el-tooltip :content="entry.docId ? '移除此任务记录，已上传资料仍保留在知识库' : '从本次任务移除'" placement="top">
                <el-button text circle :icon="Close" :aria-label="`移除 ${entry.name}`" :disabled="busy" @click="removeEntry(entry)" />
              </el-tooltip>
            </div>
            <p v-if="entry.error" class="entry-error" role="alert">{{ entry.error }}</p>
            <details v-if="entry.docId" class="file-result">
              <summary>查看{{ entry.phase === 'done' ? '上传结果' : '已上传记录' }}</summary>
              <dl><div><dt>文档 ID</dt><dd>{{ entry.docId }}</dd></div><div><dt>处理方案</dt><dd>{{ parserLabel(entry.options?.parser || options.parser) }} · 文档级索引</dd></div><div v-if="entry.contentLength !== null"><dt>解析字符</dt><dd>{{ entry.contentLength.toLocaleString() }}</dd></div></dl>
              <pre v-if="entry.resultText" class="result-excerpt">{{ entry.resultText }}</pre>
              <p class="import-note">{{ entry.phase === 'done' ? '原文与解析结果已保留，可在资料列表打开文档工作区核对。' : '后续将继续保存配置或应用解析方案，不会再次上传该文件。' }}</p>
            </details>
          </li>
        </ul>
        <p v-if="missingCount" class="restore-note" role="status">{{ missingCount }} 份文件需重新选择。请选择原文件（名称、大小和修改时间须一致），其他文件已保留。</p>
      </section>

      <section class="import-section" aria-labelledby="import-parser-heading">
        <h3 id="import-parser-heading"><span>2</span>解析与文字识别</h3>
        <div class="import-grid">
          <el-form-item label="解析方式" label-for="knowledge-import-parser">
            <el-select id="knowledge-import-parser" v-model="options.parser" :disabled="busy || planLocked || !capabilitiesReady" :placeholder="capabilitiesReady ? '选择解析方式' : '等待读取解析能力'" @change="markDraftChanged">
              <el-option v-for="parser in parsers" :key="parser.value" :value="parser.value" :label="parser.label + (parser.available ? '' : '（暂不可用）')" :disabled="parser.available !== true" />
            </el-select>
            <p class="field-note">{{ planLocked ? '已有资料使用此方案上传，未完成条目将按原方案继续。' : 'PDF / DOCX 提取正文，TXT / Markdown 可直接读取。' }}</p>
          </el-form-item>
          <el-form-item label="OCR 文字识别" label-for="knowledge-import-ocr">
            <el-tooltip content="当前服务只支持随解析方式处理 OCR，暂不能单独开关。" placement="top">
              <el-select id="knowledge-import-ocr" :model-value="'auto'" disabled aria-describedby="import-ocr-note"><el-option value="auto" label="随解析方式处理" /></el-select>
            </el-tooltip>
            <p id="import-ocr-note" class="field-note">当前服务暂不支持单独设置 OCR。</p>
          </el-form-item>
        </div>
        <p v-if="!capabilitiesReady" class="capability-note" role="status"><el-icon aria-hidden="true"><InfoFilled /></el-icon>解析能力尚未读取成功，暂不能提交。已选择文件会保留。</p>
        <p v-else-if="!selectedParserAvailable" class="entry-error" role="alert">草稿中的解析方式当前不可用，请选择其他方案；若已有上传记录，可移除此任务记录后在文档工作区调整。</p>
        <p v-if="options.parser !== 'auto'" class="parser-notice"><el-icon aria-hidden="true"><InfoFilled /></el-icon><span>上传会先按文件类型提取正文，再保存并应用所选解析方案。{{ options.parser === 'mineru' ? '提交将调用 MinerU API，可能产生服务费用。' : '重试只继续未完成的步骤。' }}</span></p>
      </section>

      <section class="import-section" aria-labelledby="import-index-heading">
        <h3 id="import-index-heading"><span>3</span>索引方案与保存范围</h3>
        <div class="import-grid">
          <el-form-item label="索引层级" label-for="knowledge-import-index">
            <el-tooltip content="当前文档处理接口未开放分级构建。" placement="top"><el-select id="knowledge-import-index" :model-value="'document'" disabled><el-option value="document" label="文档级索引" /></el-select></el-tooltip>
            <p class="field-note">保留文档级方案，当前文档处理接口未开放分级构建。</p>
          </el-form-item>
          <div class="save-scope"><span>保存范围</span><p>本地保存文件清单与处理选项。文件内容仅保留在当前窗口，刷新后未上传的文件需重新选择。</p><p>上传后保留原文与解析结果；索引在文档工作区另行管理。</p></div>
        </div>
      </section>
      <p v-if="formError" class="import-error" role="alert">{{ formError }}</p>
      <p v-if="storageError" class="import-error" role="alert">{{ storageError }}</p>
      <p v-if="storageMessage" class="import-message" role="status">{{ storageMessage }}</p>
      <p v-if="batchMessage" class="import-message" role="status">{{ batchMessage }}</p>
    </el-form>
    <template #footer>
      <div class="import-footer">
        <p class="draft-status" role="status"><template v-if="busy">正在处理，请保持此窗口打开。</template><template v-else-if="draftDirty">有未保存的任务修改</template><template v-else-if="savedTimeLabel">已保存于 {{ savedTimeLabel }}</template><template v-else>任务尚未保存</template><small v-if="completedCount">已完成 {{ completedCount }} 份 · 待完成 {{ pendingEntries.length }} 份</small></p>
        <div class="import-actions">
          <el-button :disabled="busy" @click="visible = false">稍后整理</el-button>
          <el-button :disabled="busy || !entries.length" @click="saveTask">{{ storageError ? '重试保存任务' : '保存待提交任务' }}</el-button>
          <el-button type="primary" :loading="busy" :disabled="!pendingEntries.length || !selectedParserAvailable" @click="submitFiles">{{ submitLabel }}</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.knowledge-import-dialog {
  --el-color-primary: var(--wb-blue);
  --el-color-danger: var(--wb-error);
  --el-text-color-primary: var(--wb-ink);
  --el-text-color-regular: var(--wb-ink);
  --el-text-color-secondary: var(--wb-muted);
  --el-text-color-placeholder: var(--wb-muted);
  --el-border-color: var(--wb-border);
  --el-border-color-light: var(--wb-line);
  --el-fill-color-blank: var(--wb-surface);
  --el-fill-color-light: var(--wb-tint);
  --el-dialog-bg-color: var(--wb-surface);
  --el-border-radius-base: var(--wb-radius);
  --el-font-size-base: var(--wb-text-size);
  display: flex;
  flex-direction: column;
  max-width: calc(100vw - 32px);
  max-height: calc(100dvh - 32px);
  padding: 0;
  overflow: hidden;
  color: var(--wb-ink);
  font: var(--wb-text-size)/1.8 var(--wb-font);
  border-radius: var(--wb-radius);
}
.knowledge-import-dialog :deep(.el-dialog__header),
.knowledge-import-dialog :deep(.el-dialog__footer) { flex: none; padding: 18px 24px; border-color: var(--wb-line); }
.knowledge-import-dialog :deep(.el-dialog__header) { border-bottom: 1px solid var(--wb-line); margin: 0; }
.knowledge-import-dialog :deep(.el-dialog__footer) { border-top: 1px solid var(--wb-line); }
.knowledge-import-dialog :deep(.el-dialog__title) { color: var(--wb-ink); font-size: var(--wb-reading-size); font-weight: 600; }
.knowledge-import-dialog :deep(.el-dialog__body) { min-height: 0; padding: 24px; overflow-y: auto; overscroll-behavior: contain; scrollbar-width: thin; }
.knowledge-import-dialog :deep(.el-button) { min-height: var(--wb-control-height); font: 400 var(--wb-text-size)/1 var(--wb-font); box-shadow: none; }
.knowledge-import-dialog :deep(.el-input__wrapper),
.knowledge-import-dialog :deep(.el-select__wrapper) { min-height: var(--wb-control-height); font-size: var(--wb-text-size); }
.import-intro { margin: 0 0 22px; color: var(--wb-muted); font-size: var(--wb-text-size); line-height: 1.8; }
.import-form { min-width: 0; }
.import-section + .import-section { margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--wb-line); }
.import-section h3 { display: flex; align-items: center; gap: 10px; margin: 0 0 16px; color: var(--wb-ink); font-size: var(--wb-text-size); font-weight: 600; }
.import-section h3 > span { color: var(--wb-blue); font-family: var(--wb-number); font-size: 13px; }
.section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
.file-count, .import-note, .field-note { color: var(--wb-muted); font-size: 13px; line-height: 1.8; }
.file-count { font-family: var(--wb-number); }
.import-upload :deep(.el-upload) { display: block; }
.import-upload :deep(.el-upload-dragger) { padding: 24px 16px; border: 1px dashed var(--wb-border); border-radius: var(--wb-radius); background: var(--wb-tint); }
.import-upload :deep(.el-upload-dragger:hover), .import-upload :deep(.el-upload-dragger.is-dragover) { border-color: var(--wb-blue); background: var(--wb-blue-soft); }
.upload-icon { color: var(--wb-blue); font-size: 26px; }
.upload-label { margin-top: 6px; color: var(--wb-blue); font-size: var(--wb-text-size); }
.upload-label span { margin-left: 10px; color: var(--wb-muted); font-size: var(--wb-text-size); }
.import-upload p { margin: 8px 0 0; color: var(--wb-muted); font-size: 13px; line-height: 1.8; }
.import-note { margin: 10px 0 0; }
.import-files { padding: 0; margin: 16px 0 0; list-style: none; }
.import-files > li { padding: 14px 0; border-bottom: 1px solid var(--wb-line); }
.file-row { display: flex; align-items: center; gap: 12px; }
.file-icon { flex: none; width: 29px; height: 34px; border-radius: 4px; background: color-mix(in srgb, var(--wb-muted) 8%, var(--wb-surface)); color: color-mix(in srgb, var(--wb-blue) 32%, var(--wb-muted)); font-size: 22px; }
.file-icon.is-pdf { color: color-mix(in srgb, var(--wb-error) 54%, var(--wb-muted)); background: color-mix(in srgb, var(--wb-error) 5%, var(--wb-surface)); }
.file-identity { min-width: 0; flex: 1; }
.file-identity strong { display: block; color: var(--wb-ink); font-size: var(--wb-text-size); font-weight: 400; line-height: 1.7; overflow-wrap: anywhere; }
.file-identity small { display: block; margin-top: 4px; color: var(--wb-muted); font-size: 12px; line-height: 1.8; }
.file-status { display: flex; align-items: center; gap: 5px; flex: none; max-width: 180px; color: var(--wb-muted); font-size: 13px; line-height: 1.8; }
.file-status.is-done { color: var(--wb-success); }
.file-status.is-error, .entry-error, .import-error { color: var(--wb-error); }
.entry-error { margin: 8px 0 0 34px; font-size: 13px; line-height: 1.85; overflow-wrap: anywhere; }
.file-result { margin: 10px 42px 0 34px; font-size: 13px; line-height: 1.8; }
.file-result summary { width: fit-content; color: var(--wb-blue); cursor: pointer; }
.file-result dl { margin: 12px 0 0; padding: 12px; border-radius: var(--wb-radius); background: var(--wb-tint); }
.file-result dl > div { display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 12px; margin: 3px 0; }
.file-result dt { color: var(--wb-muted); }
.file-result dd { margin: 0; overflow-wrap: anywhere; }
.result-excerpt { max-height: 220px; margin: 10px 0 0; padding: 12px; overflow-y: auto; border: 1px solid var(--wb-line); color: var(--wb-ink); font: var(--wb-reading-size)/1.8 var(--wb-font); white-space: pre-wrap; overflow-wrap: anywhere; }
.import-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
.import-grid :deep(.el-form-item) { min-width: 0; margin-bottom: 0; }
.import-grid :deep(.el-form-item__label) { height: auto; margin-bottom: 8px; color: var(--wb-ink); font-size: var(--wb-text-size); line-height: 24px; }
.import-grid :deep(.el-select) { width: 100%; }
.import-grid :deep(.el-select__wrapper.is-disabled .el-select__selected-item) { color: var(--wb-muted); }
.field-note { margin: 8px 0 0; }
.save-scope > span { color: var(--wb-ink); font-size: var(--wb-text-size); }
.save-scope p { margin: 8px 0 0; color: var(--wb-muted); font-size: 13px; line-height: 1.85; }
.selection-feedback, .restore-note, .capability-note, .parser-notice { padding: 12px; margin: 12px 0 0; border-radius: var(--wb-radius); background: var(--wb-tint); color: var(--wb-muted); font-size: 13px; line-height: 1.85; }
.feedback-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.selection-feedback ul { margin: 4px 0 0; padding-left: 18px; overflow-wrap: anywhere; }
.capability-note, .parser-notice { display: flex; align-items: baseline; gap: 8px; }
.parser-notice { color: var(--wb-blue); background: var(--wb-blue-soft); }
.import-error, .import-message { margin: 16px 0 0; font-size: 13px; line-height: 1.85; }
.import-message { color: var(--wb-blue); }
.import-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; text-align: left; }
.draft-status { margin: 0; color: var(--wb-muted); font-size: 12px; line-height: 1.8; }
.draft-status small { display: block; font-size: 12px; }
.import-actions { display: flex; align-items: center; flex-wrap: wrap; justify-content: flex-end; gap: 10px; flex: none; }
.import-actions :deep(.el-button + .el-button) { margin-left: 0; }
.import-form :deep(button:focus-visible), .file-result summary:focus-visible { outline: 2px solid var(--wb-blue); outline-offset: 3px; }
@media (max-width: 680px) {
  .knowledge-import-dialog :deep(.el-dialog__header), .knowledge-import-dialog :deep(.el-dialog__footer) { padding: 18px 20px; }
  .knowledge-import-dialog :deep(.el-dialog__body) { padding: 20px; }
  .knowledge-import-dialog :deep(input), .knowledge-import-dialog :deep(textarea), .knowledge-import-dialog :deep(.el-select__selected-item) { font-size: 16px; }
  .import-grid { grid-template-columns: minmax(0, 1fr); gap: 18px; }
  .file-row { flex-wrap: wrap; }
  .file-identity { flex-basis: calc(100% - 70px); }
  .file-status { max-width: none; padding-left: 34px; flex: 1; }
  .file-result { margin-right: 0; }
  .import-footer { align-items: stretch; flex-direction: column; gap: 12px; }
  .import-actions { justify-content: flex-end; gap: 8px; }
  .import-actions :deep(.el-button) { padding-inline: 10px; }
}
</style>
