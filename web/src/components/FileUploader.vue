<template>
  <div class="file-uploader">
    <el-upload
      v-model:file-list="fileList"
      :action="uploadUrl"
      :headers="headers"
      :multiple="multiple"
      :limit="limit"
      :accept="accept"
      :before-upload="beforeUpload"
      :on-success="handleSuccess"
      :on-error="handleError"
      :on-exceed="handleExceed"
      :on-remove="handleRemove"
      :disabled="disabled"
      :drag="drag"
      :auto-upload="autoUpload"
      :show-file-list="showFileList"
    >
      <div v-if="drag">
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处或 <em>点击上传</em>
        </div>
      </div>
      <el-button v-else type="primary" :icon="Upload" :loading="uploading">
        {{ buttonText }}
      </el-button>

      <template #tip>
        <div class="el-upload__tip" :style="!drag ? 'margin-left: 12px' : ''">
          <slot name="tip">
            {{ tipText }}
          </slot>
        </div>
      </template>
    </el-upload>

    <!-- Custom file list display -->
    <div v-if="showCustomList && uploadedFiles.length > 0" class="uploaded-files">
      <div class="files-header">
        <span>已上传文件 ({{ uploadedFiles.length }})</span>
        <el-button size="small" text @click="clearAll" v-if="!disabled">
          清空
        </el-button>
      </div>
      <div class="files-list">
        <div
          v-for="file in uploadedFiles"
          :key="file.uid || file.name"
          class="file-item"
        >
          <div class="file-info">
            <el-icon><Document /></el-icon>
            <span class="file-name">{{ file.name }}</span>
            <span class="file-size">{{ formatFileSize(file.size) }}</span>
          </div>
          <div class="file-actions">
            <el-button
              size="small"
              text
              type="danger"
              @click="removeFile(file)"
              v-if="!disabled"
            >
              删除
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, UploadFilled, Document } from '@element-plus/icons-vue'

const props = defineProps({
  uploadUrl: {
    type: String,
    default: '/api/upload'
  },
  headers: {
    type: Object,
    default: () => ({})
  },
  multiple: {
    type: Boolean,
    default: false
  },
  limit: {
    type: Number,
    default: 10
  },
  accept: {
    type: String,
    default: '' // e.g., '.pdf,.docx,.txt'
  },
  maxSize: {
    type: Number,
    default: 10 * 1024 * 1024 // 10MB
  },
  drag: {
    type: Boolean,
    default: true
  },
  autoUpload: {
    type: Boolean,
    default: true
  },
  showFileList: {
    type: Boolean,
    default: true
  },
  showCustomList: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  },
  buttonText: {
    type: String,
    default: '选择文件'
  },
  tipText: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['success', 'error', 'remove', 'change'])

const fileList = ref([])
const uploadedFiles = ref([])
const uploading = ref(false)

const beforeUpload = (file) => {
  // Check file size
  if (props.maxSize && file.size > props.maxSize) {
    ElMessage.error(`文件大小不能超过 ${formatFileSize(props.maxSize)}`)
    return false
  }

  // Check file type if accept is specified
  if (props.accept) {
    const acceptTypes = props.accept.split(',').map(type => type.trim().toLowerCase())
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase()
    if (!acceptTypes.includes(fileExtension)) {
      ElMessage.error(`只支持 ${props.accept} 格式的文件`)
      return false
    }
  }

  uploading.value = true
  return true
}

const handleSuccess = (response, file, fileList) => {
  uploading.value = false
  uploadedFiles.value.push({
    uid: file.uid,
    name: file.name,
    size: file.size,
    response: response
  })
  ElMessage.success(`${file.name} 上传成功`)
  emit('success', { response, file, fileList })
  emit('change', uploadedFiles.value)
}

const handleError = (error, file, fileList) => {
  uploading.value = false
  ElMessage.error(`${file.name} 上传失败`)
  emit('error', { error, file, fileList })
}

const handleExceed = (files, fileList) => {
  ElMessage.warning(`最多只能上传 ${props.limit} 个文件`)
}

const handleRemove = (file, fileList) => {
  const index = uploadedFiles.value.findIndex(f => f.uid === file.uid)
  if (index > -1) {
    uploadedFiles.value.splice(index, 1)
  }
  emit('remove', { file, fileList })
  emit('change', uploadedFiles.value)
}

const removeFile = (file) => {
  handleRemove(file, fileList.value)
}

const clearAll = () => {
  fileList.value = []
  uploadedFiles.value = []
  emit('change', uploadedFiles.value)
  ElMessage.success('已清空所有文件')
}

const formatFileSize = (size) => {
  if (!size) return '0B'
  const units = ['B', 'KB', 'MB', 'GB']
  let index = 0
  let fileSize = size

  while (fileSize >= 1024 && index < units.length - 1) {
    fileSize /= 1024
    index++
  }

  return `${fileSize.toFixed(1)}${units[index]}`
}

// Expose methods for parent component
defineExpose({
  clearAll,
  getFiles: () => uploadedFiles.value
})
</script>

<style scoped>
.file-uploader {
  width: 100%;
}

.uploaded-files {
  margin-top: 20px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: var(--el-border-radius-base);
  overflow: hidden;
}

.files-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-weight: 500;
}

.files-list {
  max-height: 300px;
  overflow-y: auto;
}

.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  transition: background-color 0.3s;
}

.file-item:hover {
  background-color: var(--el-fill-color-lighter);
}

.file-item:last-child {
  border-bottom: none;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.file-name {
  flex: 1;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-left: 8px;
}

.file-actions {
  display: flex;
  gap: 8px;
}

/* Drag upload styles */
:deep(.el-upload-dragger) {
  padding: 40px 0;
  border-radius: var(--el-border-radius-base);
}

:deep(.el-icon--upload) {
  font-size: 67px;
  color: var(--el-text-color-placeholder);
  margin-bottom: 16px;
}

:deep(.el-upload__text) {
  color: var(--el-text-color-regular);
  font-size: 14px;
}

:deep(.el-upload__text em) {
  color: var(--el-color-primary);
  font-style: normal;
}

:deep(.el-upload__tip) {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-top: 8px;
}
</style>