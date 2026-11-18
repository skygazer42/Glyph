<template>
  <div class="unavailable-state" role="status">
    <span class="unavailable-state-icon" aria-hidden="true"><el-icon><Warning /></el-icon></span>
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <el-button :icon="Refresh" :loading="busy" @click="$emit('retry')">重新读取</el-button>
    <details v-if="detail"><summary>查看原因</summary><pre>{{ detail }}</pre></details>
  </div>
</template>

<script setup>
import { Refresh, Warning } from '@element-plus/icons-vue'
defineProps({ title: { type: String, required: true }, description: { type: String, required: true }, detail: { type: String, default: '' }, busy: { type: Boolean, default: false } })
defineEmits(['retry'])
</script>

<style scoped>
.unavailable-state { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; min-height: 260px; padding: 36px 24px; color: var(--wb-muted); font-family: var(--wb-font); text-align: center; }
.unavailable-state-icon { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 11px; background: var(--wb-warning-soft); color: var(--wb-warning); font-size: 22px; }
.unavailable-state h3 { margin: 0; color: var(--wb-ink); font-size: 16px; font-weight: 500; }
.unavailable-state > p { max-width: 380px; margin: 0 0 6px; font-size: 13px; line-height: 1.8; }
.unavailable-state details { max-width: 100%; margin-top: 2px; font-size: 12px; }
.unavailable-state summary { cursor: pointer; }
.unavailable-state pre { max-height: 140px; overflow: auto; margin: 10px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; text-align: left; font: 12px/1.8 var(--font-mono); }
</style>
