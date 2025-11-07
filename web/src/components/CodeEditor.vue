<template>
  <div class="code-editor">
    <div class="editor-header">
      <div class="editor-title">
        <slot name="title">
          <span>{{ title }}</span>
        </slot>
      </div>
      <div class="editor-actions">
        <slot name="actions">
          <el-button
            v-if="showCopy && modelValue"
            size="small"
            @click="handleCopy"
            :icon="CopyDocument"
          >
            复制
          </el-button>
        </slot>
      </div>
    </div>

    <div class="editor-body">
      <el-input
        v-if="mode === 'input'"
        :modelValue="modelValue"
        @update:modelValue="$emit('update:modelValue', $event)"
        type="textarea"
        :rows="rows"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
      />

      <div v-else-if="mode === 'display' && modelValue" class="code-display">
        <pre><code :class="language">{{ modelValue }}</code></pre>
      </div>

      <el-empty
        v-else-if="mode === 'display' && !modelValue"
        :description="emptyText"
        :image-size="80"
      />
    </div>

    <div v-if="$slots.footer" class="editor-footer">
      <slot name="footer"></slot>
    </div>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { CopyDocument } from '@element-plus/icons-vue'

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
    default: 'input', // 'input' | 'display'
    validator: (value) => ['input', 'display'].includes(value)
  },
  language: {
    type: String,
    default: 'yaml' // for syntax highlighting
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
  disabled: {
    type: Boolean,
    default: false
  },
  readonly: {
    type: Boolean,
    default: false
  }
})

defineEmits(['update:modelValue'])

const handleCopy = () => {
  navigator.clipboard.writeText(props.modelValue)
  ElMessage.success('已复制到剪贴板')
}
</script>

<style scoped>
.code-editor {
  border: 1px solid var(--el-border-color);
  border-radius: var(--el-border-radius-base);
  overflow: hidden;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.editor-title {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.editor-actions {
  display: flex;
  gap: 8px;
}

.editor-body {
  background-color: var(--el-bg-color);
}

.editor-body :deep(.el-textarea__inner) {
  border: none;
  border-radius: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.code-display {
  background-color: #f6f8fa;
  padding: 16px;
  max-height: 600px;
  overflow: auto;
}

.code-display pre {
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.editor-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--el-border-color-lighter);
  background-color: var(--el-fill-color-blank);
}

/* Dark mode support */
@media (prefers-color-scheme: dark) {
  .code-display {
    background-color: #1e1e1e;
  }

  .code-display pre code {
    color: #d4d4d4;
  }
}
</style>