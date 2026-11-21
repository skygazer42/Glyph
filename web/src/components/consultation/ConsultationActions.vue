<template>
  <div class="consultation-session-actions" :class="{ 'is-workspace': workspace }" role="group" aria-label="咨询操作">
    <button type="button" class="new-consultation" @click="$emit('new')"><el-icon><Plus /></el-icon>新建咨询</button>
    <div class="consultation-secondary-actions" role="group" aria-label="咨询工具">
      <button type="button" class="session-history-trigger" @click="$emit('history')"><el-icon><Clock /></el-icon>咨询记录</button>
      <el-dropdown v-if="workspace" ref="moreDropdown" trigger="click" placement="bottom-end" popper-class="consultation-more-menu" @command="openWorkspaceTool">
        <button ref="moreTrigger" type="button" class="workbench-icon consultation-more-trigger" :class="{ 'is-active': evidenceVisible }" aria-label="更多咨询操作" @keydown.esc.stop="closeWorkspaceTools"><el-icon><MoreFilled /></el-icon></button>
        <template #dropdown>
          <el-dropdown-menu @keydown.esc.capture.stop="closeWorkspaceTools">
            <el-dropdown-item command="evidence" :icon="Reading">{{ evidenceVisible ? '收起政策依据' : '政策依据' }}<span v-if="sourceCount">（{{ sourceCount }}）</span></el-dropdown-item>
            <el-dropdown-item command="settings" :icon="SetUp">咨询设置</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <template v-else>
        <button type="button" class="evidence-toggle" :aria-expanded="evidenceVisible" aria-controls="policy-evidence" @click="$emit('evidence')"><el-icon><Reading /></el-icon>政策依据<span v-if="sourceCount" class="evidence-count">{{ sourceCount }}</span></button>
        <el-tooltip content="答复显示与会话设置" placement="bottom"><button type="button" class="workbench-icon" aria-label="咨询设置" @click="$emit('settings')"><el-icon><SetUp /></el-icon></button></el-tooltip>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Clock, MoreFilled, Plus, Reading, SetUp } from '@element-plus/icons-vue'
defineProps({ evidenceVisible: Boolean, sourceCount: { type: Number, default: 0 }, workspace: Boolean })
const emit = defineEmits(['new', 'history', 'evidence', 'settings'])
const moreTrigger = ref(null)
const moreDropdown = ref(null)
function closeWorkspaceTools() {
  moreDropdown.value?.handleClose()
  moreTrigger.value?.focus()
}
function openWorkspaceTool(command) {
  moreTrigger.value?.focus()
  emit(command)
}
</script>
