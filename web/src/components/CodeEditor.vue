<template>
  <div class="code-editor" :class="{ 'editor-focused': isFocused }">
    <!-- 编辑器头部 -->
    <div class="editor-header">
      <div class="editor-title">
        <slot name="title">
          <el-icon v-if="mode === 'input'"><Edit /></el-icon>
          <el-icon v-else><View /></el-icon>
          <span>{{ title }}</span>
        </slot>
      </div>
      <div class="editor-actions">
        <slot name="actions">
          <!-- 行数统计 -->
          <span v-if="modelValue" class="line-count">
            {{ lineCount }} 行
          </span>
          <!-- 字符统计 -->
          <span v-if="modelValue && mode === 'input'" class="char-count">
            {{ charCount }} 字符
          </span>
          <!-- 复制按钮 -->
          <el-button
            v-if="showCopy && modelValue"
            size="small"
            @click="handleCopy"
            :icon="CopyDocument"
          >
            复制
          </el-button>
          <!-- 下载按钮 -->
          <el-button
            v-if="showDownload && modelValue"
            size="small"
            @click="handleDownload"
            :icon="Download"
          >
            下载
          </el-button>
        </slot>
      </div>
    </div>

    <!-- 编辑器主体 -->
    <div class="editor-body">
      <!-- 输入模式 -->
      <el-input
        v-if="mode === 'input'"
        :modelValue="modelValue"
        @update:modelValue="$emit('update:modelValue', $event)"
        @focus="isFocused = true"
        @blur="isFocused = false"
        type="textarea"
        :rows="rows"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :maxlength="maxLength"
        :show-word-limit="showWordLimit"
        class="code-textarea"
      />

      <!-- 显示模式 -->
      <div v-else-if="mode === 'display' && modelValue" class="code-display">
        <div v-if="showLineNumbers" class="line-numbers">
          <div
            v-for="(line, index) in lines"
            :key="index"
            class="line-number"
          >
            {{ index + 1 }}
          </div>
        </div>
        <pre class="code-content"><code :class="`language-${language}`" v-html="highlightedCode"></code></pre>
      </div>

      <!-- 空状态 -->
      <el-empty
        v-else-if="mode === 'display' && !modelValue"
        :description="emptyText"
        :image-size="80"
      />
    </div>

    <!-- 编辑器底部 -->
    <div v-if="$slots.footer" class="editor-footer">
      <slot name="footer"></slot>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument, Download, Edit, View } from '@element-plus/icons-vue'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  title: {
    type: String,
    default: ''
  },
  mode: {
    type: String,
    default: 'input',
    validator: (value) => ['input', 'display'].includes(value)
  },
  language: {
    type: String,
    default: 'yaml'
  },
  rows: {
    type: Number,
    default: 20
  },
  placeholder: {
    type: String,
    default: ''
  },
  emptyText: {
    type: String,
    default: '暂无内容'
  },
  showCopy: {
    type: Boolean,
    default: false
  },
  showDownload: {
    type: Boolean,
    default: false
  },
  showLineNumbers: {
    type: Boolean,
    default: true
  },
  showWordLimit: {
    type: Boolean,
    default: false
  },
  maxLength: {
    type: Number,
    default: undefined
  },
  disabled: {
    type: Boolean,
    default: false
  },
  readonly: {
    type: Boolean,
    default: false
  },
  fileName: {
    type: String,
    default: 'code'
  }
})

defineEmits(['update:modelValue'])

const isFocused = ref(false)

// 计算属性
const lines = computed(() => {
  return props.modelValue ? props.modelValue.split('\n') : []
})

const lineCount = computed(() => {
  return lines.value.length
})

const charCount = computed(() => {
  return props.modelValue.length
})

const highlightedCode = computed(() => {
  if (!props.modelValue) return ''
  try {
    if (props.language && hljs.getLanguage(props.language)) {
      return hljs.highlight(props.modelValue, { language: props.language }).value
    }
    return hljs.highlightAuto(props.modelValue).value
  } catch (error) {
    console.warn('Highlighting error:', error)
    return props.modelValue
  }
})

// 方法
const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(props.modelValue)
    ElMessage.success('已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

const handleDownload = () => {
  try {
    const blob = new Blob([props.modelValue], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${props.fileName}.${props.language}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch (error) {
    ElMessage.error('下载失败')
  }
}
</script>

<style scoped>
.code-editor {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  overflow: hidden;
  background: var(--bg-primary);
  transition: var(--transition-fast);
}

.code-editor.editor-focused {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

/* 编辑器头部 */
.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
  background: linear-gradient(to bottom, var(--bg-tertiary), var(--bg-secondary));
  border-bottom: 1px solid var(--border-light);
}

.editor-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-weight: 600;
  color: var(--text-primary);
  font-size: var(--font-size-base);
}

.editor-title .el-icon {
  color: var(--primary-color);
}

.editor-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.line-count,
.char-count {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  padding: 4px 8px;
  background: var(--bg-primary);
  border-radius: var(--radius-small);
}

/* 编辑器主体 */
.editor-body {
  background: var(--bg-primary);
  position: relative;
}

.code-textarea :deep(.el-textarea__inner) {
  border: none;
  border-radius: 0;
  font-family: var(--font-family-mono);
  font-size: var(--font-size-sm);
  line-height: 1.6;
  padding: var(--spacing-lg);
  background: #2d2d30;
  color: #d4d4d4;
  resize: vertical;
}

.code-textarea :deep(.el-textarea__inner:focus) {
  box-shadow: none;
}

/* 显示模式 */
.code-display {
  display: flex;
  background: #1e1e1e;
  padding: var(--spacing-lg);
  max-height: 600px;
  overflow: auto;
  position: relative;
}

.line-numbers {
  flex-shrink: 0;
  padding-right: var(--spacing-md);
  border-right: 1px solid var(--border-base);
  user-select: none;
  text-align: right;
  color: #858585;
  font-family: var(--font-family-mono);
  font-size: var(--font-size-sm);
  line-height: 1.6;
}

.line-number {
  height: 1.6em;
}

.code-content {
  flex: 1;
  margin: 0;
  padding-left: var(--spacing-md);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-sm);
  line-height: 1.6;
  overflow-x: auto;
}

.code-content code {
  display: block;
  white-space: pre;
  word-wrap: normal;
}

/* 编辑器底部 */
.editor-footer {
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--border-light);
  background: var(--bg-secondary);
}

/* 响应式 */
@media (max-width: 768px) {
  .editor-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-sm);
  }

  .editor-actions {
    width: 100%;
    justify-content: space-between;
  }

  .code-display {
    font-size: var(--font-size-xs);
  }

  .line-numbers,
  .code-content {
    font-size: var(--font-size-xs);
  }
}

/* 滚动条样式 */
.code-display::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.code-display::-webkit-scrollbar-track {
  background: #1e1e1e;
}

.code-display::-webkit-scrollbar-thumb {
  background: #424242;
  border-radius: 4px;
}

.code-display::-webkit-scrollbar-thumb:hover {
  background: #4e4e4e;
}
</style>