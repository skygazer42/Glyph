<template>
  <div class="rule-editor-layout">
    <div v-if="compareEditors" class="rule-editor-compare">
      <section class="rule-editor-column" aria-label="政策原文">
        <header class="rule-source-label">政策原文</header>
        <slot name="source" />
      </section>
      <section class="rule-editor-column" aria-label="结构化规则">
        <slot name="rule" />
      </section>
    </div>
    <el-tabs v-else :model-value="modelValue" class="rule-editor-tabs" aria-label="规则编制内容" @update:model-value="$emit('update:modelValue', $event)">
      <el-tab-pane label="政策原文" name="source"><slot name="source" /></el-tab-pane>
      <el-tab-pane name="rule">
        <template #label><span class="rule-tab-label">结构化规则<span v-if="hasRule" class="rule-ready-dot" aria-hidden="true" /></span></template>
        <slot name="rule" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

defineProps({
  modelValue: { type: String, default: 'source' },
  hasRule: { type: Boolean, default: false }
})
defineEmits(['update:modelValue'])

const comparisonQuery = window.matchMedia('(min-width: 1536px)')
const compareEditors = ref(comparisonQuery.matches)
const updateComparison = event => { compareEditors.value = event.matches }
onMounted(() => comparisonQuery.addEventListener('change', updateComparison))
onBeforeUnmount(() => comparisonQuery.removeEventListener('change', updateComparison))
</script>

<style scoped>
.rule-editor-layout,
.rule-editor-tabs {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}
.rule-editor-compare {
  display: grid;
  flex: 1;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  min-height: 0;
}
.rule-editor-column {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}
.rule-editor-column + .rule-editor-column {
  border-left: 1px solid var(--wb-line);
}
.rule-source-label {
  min-height: 54px;
  padding: 12px 22px;
  border-bottom: 1px solid var(--wb-line);
  color: var(--wb-muted);
  font-size: 13px;
  line-height: 1.7;
}
.rule-editor-tabs :deep(.el-tabs__content) {
  display: flex;
  flex: 1;
  min-height: 0;
}
.rule-editor-tabs :deep(.el-tab-pane) {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
}
.rule-editor-tabs :deep(.el-tabs__header) {
  padding: 0 22px;
  margin: 0;
  border-bottom: 1px solid var(--wb-line);
}
.rule-editor-tabs :deep(.el-tabs__nav-wrap::after) { display: none; }
.rule-editor-tabs :deep(.el-tabs__item) {
  height: 48px;
  color: var(--wb-muted);
  font-family: var(--wb-font);
  font-size: var(--wb-text-size);
  font-weight: 400;
}
.rule-editor-tabs :deep(.el-tabs__item.is-active) {
  color: var(--wb-ink);
  font-weight: 500;
}
.rule-tab-label { display: inline-flex; align-items: center; gap: 8px; }
.rule-ready-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--wb-blue);
}
@media (max-width: 699px) {
  .rule-editor-tabs :deep(.el-tabs__header) { padding: 0 16px; }
}
</style>
