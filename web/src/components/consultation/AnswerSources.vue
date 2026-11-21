<template>
  <section v-if="groups.length" class="answer-sources" aria-label="本轮政策依据">
    <div class="sources-heading"><span>政策依据</span><span>{{ groups.length }} 份文件</span></div>
    <div class="sources-list">
      <article v-for="group in groups" :key="group.key" class="source-group">
        <div class="source-row">
          <span class="source-document" aria-hidden="true"><el-icon><Document /></el-icon></span>
          <a :href="group.url || '#policy-evidence'" :target="group.url ? '_blank' : undefined" rel="noopener noreferrer" class="source-title" @click="selectSource($event, group.primaryIndex)">{{ group.title }}</a>
          <button v-if="group.sources.length > 1" type="button" class="fragments-toggle" :aria-expanded="expanded.includes(group.key)" @click="toggle(group.key)">
            {{ group.sources.length }} 处引用<el-icon :class="{ expanded: expanded.includes(group.key) }"><ArrowDown /></el-icon>
          </button>
          <a v-if="group.url" :href="group.url" target="_blank" rel="noopener noreferrer" class="source-original" :aria-label="`打开原文：${group.title}`">原文<el-icon><TopRight /></el-icon></a>
        </div>
        <div v-if="expanded.includes(group.key)" class="source-fragments">
          <button v-for="(source, index) in group.sources" :key="group.originalIndices[index]" type="button" class="fragment-item" @click="emit('select', group.originalIndices[index])">
            <span class="fragment-number">资料{{ group.citationNumbers[index] }}</span>
            <span class="fragment-location">{{ getPolicySourceLocation(source) }}</span>
            <span v-if="source.excerpt" class="fragment-excerpt">{{ source.excerpt }}</span>
            <el-icon aria-hidden="true"><Right /></el-icon>
          </button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ArrowDown, Document, Right, TopRight } from '@element-plus/icons-vue'
import { getPolicySourceLocation, groupPolicySources } from '@/utils/policyPresentation'

const props = defineProps({ sources: { type: Array, default: () => [] } })
const emit = defineEmits(['select'])
const groups = computed(() => groupPolicySources(props.sources))
const expanded = ref([])
const toggle = key => { expanded.value = expanded.value.includes(key) ? expanded.value.filter(value => value !== key) : [...expanded.value, key] }
const selectSource = (event, index) => {
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return
  event.preventDefault()
  emit('select', index)
}
</script>

<style scoped>
.answer-sources { border-top: 1px solid var(--wb-line); margin-top: 22px; padding-top: 14px; }
.sources-heading { display: flex; gap: 10px; align-items: baseline; color: var(--wb-ink); font-size: 12px; font-weight: 500; margin-bottom: 6px; }
.sources-heading > :last-child { color: var(--wb-muted); font-weight: 400; }
.source-group + .source-group { border-top: 1px solid var(--wb-line); }
.source-row { display: flex; align-items: baseline; gap: 10px; padding: 10px 0; min-width: 0; }
.source-document { flex: 0 0 auto; align-self: flex-start; display: inline-flex; padding-top: 4px; color: var(--wb-muted); font-size: 14px; }
.source-title { color: var(--wb-ink); font-size: 13px; line-height: 1.7; text-decoration: none; min-width: 0; overflow-wrap: anywhere; flex: 1; }
.source-title:hover { color: var(--wb-blue); text-decoration: underline; text-underline-offset: 3px; }
.fragments-toggle, .source-original { display: inline-flex; flex-shrink: 0; gap: 5px; align-items: center; border: 0; background: transparent; padding: 2px 0; font: inherit; font-size: 12px; color: var(--wb-muted); white-space: nowrap; }
.fragments-toggle:hover, .source-original:hover { color: var(--wb-blue); }
.fragments-toggle { cursor: pointer; }
.fragments-toggle .el-icon { transition: transform var(--wb-motion); }
.fragments-toggle .expanded { transform: rotate(180deg); }
.source-original { text-decoration: none; }
.source-fragments { margin: 0 0 10px 24px; border-left: 2px solid var(--wb-line); }
.fragment-item { display: flex; align-items: baseline; gap: 8px; width: 100%; border: 0; background: transparent; color: var(--wb-muted); padding: 8px 10px; text-align: left; font: inherit; font-size: 12px; cursor: pointer; }
.fragment-item:hover { background: var(--wb-tint); color: var(--wb-blue); }
.fragment-number { color: var(--wb-blue); white-space: nowrap; }
.fragment-location { white-space: nowrap; }
.fragment-excerpt { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; flex: 1; }
.fragment-item > .el-icon { flex-shrink: 0; margin-left: auto; align-self: center; }
@media (max-width: 640px) {
  .source-row { flex-wrap: wrap; gap: 6px 9px; }
  .source-title { flex-basis: calc(100% - 28px); }
  .fragments-toggle { margin-left: 23px; }
  .fragment-excerpt { display: none; }
}
</style>
