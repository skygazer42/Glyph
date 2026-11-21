<template>
  <div class="answer-progress" aria-label="答复处理进度">
    <div class="progress-current">
      <span class="progress-spinner" aria-hidden="true" />
      <span class="progress-label" role="status">{{ run.phase || '正在处理您的问题' }}</span>
      <span class="progress-elapsed" aria-live="off">{{ elapsedLabel }}</span>
      <button type="button" class="progress-stop" @click="$emit('stop')">停止</button>
    </div>
    <div v-if="sourceCount" class="progress-found">已找到 {{ sourceCount }} 份相关资料</div>
    <p v-else-if="elapsed >= 20 && !hasContent" class="progress-note">仍在处理中，您可以继续等待或停止本次答复。</p>
    <details v-if="run.steps.length || run.tools.length" class="progress-details">
      <summary>处理记录<span>{{ run.steps.length + run.tools.length }}</span></summary>
      <ol>
        <li v-for="(step, index) in run.steps" :key="`step-${index}`" :class="{ 'is-error': step.status === 'error' }">
          <span class="progress-step-mark" :class="{ 'is-finished': step.status === 'complete' || step.finished }" aria-hidden="true" />
          <span>{{ step.label || step.name }}</span>
          <small v-if="step.status === 'error'">未完成</small><small v-else-if="step.status === 'cancelled'">已停止</small>
        </li>
        <li v-for="tool in run.tools" :key="tool.id || tool.toolCallId" :class="{ 'is-error': tool.status === 'error' }">
          <span class="progress-step-mark" :class="{ 'is-finished': tool.status === 'complete' || tool.finished }" aria-hidden="true" />
          <span>{{ toolLabels[tool.name] || '处理资料' }}</span>
          <small v-if="tool.status === 'error'">未完成</small><small v-else-if="tool.status === 'cancelled'">已停止</small>
        </li>
      </ol>
    </details>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  run: { type: Object, required: true },
  startedAt: { type: Number, required: true },
  sourceCount: { type: Number, default: 0 },
  hasContent: { type: Boolean, default: false }
})
defineEmits(['stop'])

const toolLabels = {
  knowledge_tool: '检索政策资料',
  graph_tool: '查询政策关系',
  rule_tool: '核对条件与测算',
  text2sql_tool: '查询业务数据',
  workflow_tool: '处理附件与资料'
}
const now = ref(Date.now())
const elapsed = computed(() => Math.max(0, Math.floor((now.value - props.startedAt) / 1000)))
const elapsedLabel = computed(() => elapsed.value < 60 ? `已用时 ${elapsed.value} 秒` : `已用时 ${Math.floor(elapsed.value / 60)} 分 ${elapsed.value % 60} 秒`)
let timer
onMounted(() => { timer = window.setInterval(() => { now.value = Date.now() }, 1000) })
onBeforeUnmount(() => { window.clearInterval(timer) })
</script>

<style scoped>
.answer-progress { margin: 4px 0 18px; color: var(--wb-secondary); font-size: 13px; line-height: 1.8; }
.progress-current { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.progress-spinner { width: 14px; height: 14px; flex: none; border: 1.5px solid var(--wb-border); border-top-color: var(--wb-blue); border-radius: 50%; animation: progress-spin 1s linear infinite; }
.progress-label { color: var(--wb-ink); font-weight: 500; }
.progress-elapsed { color: var(--wb-muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.progress-stop { margin-left: auto; padding: 2px 8px; border: 1px solid var(--wb-line); border-radius: var(--wb-radius); background: var(--wb-surface); color: var(--wb-muted); font: inherit; font-size: 12px; cursor: pointer; }
.progress-stop:hover { color: var(--wb-ink); border-color: var(--wb-border); }
.progress-stop:focus-visible, summary:focus-visible { outline: 2px solid var(--wb-blue); outline-offset: 3px; }
.progress-found, .progress-note { margin: 7px 0 0 24px; color: var(--wb-muted); font-size: 12px; }
.progress-details { margin: 8px 0 0 24px; color: var(--wb-muted); font-size: 12px; }
.progress-details summary { cursor: pointer; width: fit-content; }
.progress-details summary span { margin-left: 7px; font-variant-numeric: tabular-nums; }
.progress-details ol { list-style: none; margin: 8px 0 0; padding: 0 0 0 3px; }
.progress-details li { display: flex; align-items: center; gap: 8px; padding: 2px 0; }
.progress-details li.is-error { color: var(--wb-warning); }
.progress-details small { color: var(--wb-muted); font-size: 11px; }
.progress-step-mark { width: 5px; height: 5px; border: 1px solid var(--wb-border); border-radius: 50%; }
.progress-step-mark.is-finished { border-color: var(--wb-blue); background: var(--wb-blue); }
@keyframes progress-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .progress-spinner { animation: none; } }
</style>
