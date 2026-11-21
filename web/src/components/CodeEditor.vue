<template>
  <div class="code-editor">
    <div v-if="showHeader" class="editor-header">
      <div class="editor-title">
        <slot name="title">
          <span>{{ title }}</span>
        </slot>
      </div>
      <div class="editor-actions">
        <slot name="actions">
          <el-button
            v-if="showCopy && modelValue !== ''"
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
        :model-value="modelValue"
        @update:modelValue="$emit('update:modelValue', $event)"
        type="textarea"
        resize="none"
        :rows="rows"
        :placeholder="placeholder"
        :aria-label="title || placeholder || '代码内容'"
        :disabled="disabled"
        :readonly="readonly"
      />

      <div
        v-else-if="mode === 'display' && modelValue !== ''"
        class="code-display"
      >
        <pre><code :class="language">{{ modelValue }}</code></pre>
      </div>

      <template v-else-if="mode === 'display' && modelValue === ''">
        <slot name="empty">
          <el-empty :description="emptyText" :image-size="80" />
        </slot>
      </template>
    </div>

    <div
      v-if="$slots.footer"
      class="editor-footer"
    >
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
  showHeader: {
    type: Boolean,
    default: true
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

const handleCopy = async () => {
  try {
    await navigator.clipboard.writeText(props.modelValue)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制内容')
  }
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
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
}

.code-display {
  background-color: var(--wb-tint, var(--el-fill-color-light));
  color: var(--wb-ink, var(--el-text-color-primary));
  padding: 16px;
  max-height: 600px;
  overflow: auto;
}

.code-display pre {
  margin: 0;
  font-family: var(--font-mono);
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

</style>
