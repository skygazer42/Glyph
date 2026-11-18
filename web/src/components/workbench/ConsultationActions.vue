<template>
  <div class="consultation-session-actions">
    <button type="button" class="new-consultation" @click="$emit('new')"><el-icon><Plus /></el-icon>新建咨询</button>
    <button type="button" class="session-history-trigger" @click="$emit('history')"><el-icon><Clock /></el-icon>咨询记录</button>
    <button type="button" class="evidence-toggle" :aria-expanded="evidenceVisible" aria-controls="policy-evidence" @click="$emit('evidence')"><el-icon><Reading /></el-icon>政策依据<span v-if="sourceCount" class="evidence-count">{{ sourceCount }}</span></button>
    <el-tooltip :content="workspace ? '咨询与数据库设置' : '答复显示与会话设置'" placement="bottom"><button type="button" class="workbench-icon" aria-label="咨询设置" @click="$emit('settings')"><el-icon><SetUp /></el-icon></button></el-tooltip>
  </div>
</template>

<script setup>
import { Clock, Plus, Reading, SetUp } from '@element-plus/icons-vue'
defineProps({ evidenceVisible: Boolean, sourceCount: { type: Number, default: 0 }, workspace: Boolean })
defineEmits(['new', 'history', 'evidence', 'settings'])
</script>
