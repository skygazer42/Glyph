<template>
<aside id="policy-evidence" class="policy-evidence" aria-label="政策依据">
  <div class="evidence-heading">
    <h2><el-icon><Reading /></el-icon>政策依据</h2>
    <el-tooltip content="收起政策依据" placement="left"><button type="button" class="workbench-icon" aria-label="收起政策依据" @click="$emit('close')"><el-icon><Fold /></el-icon></button></el-tooltip>
  </div>
  <p class="evidence-context">{{ message ? `所选答复 · ${groups.length} 份文件 · ${sources.length} 处引用` : '随咨询答复更新' }}</p>
  <el-tabs v-model="activeTab" stretch class="evidence-tabs">
    <el-tab-pane :label="`政策来源${groups.length ? ` ${groups.length}` : ''}`" name="sources">
      <div v-if="!sources.length" class="evidence-empty"><el-icon><Document /></el-icon><h3>{{ message ? '本条答复暂无政策来源' : '政策依据，一处查阅' }}</h3><p>{{ message ? '该答复未附带来源信息，可继续追问政策名称或原文。' : '开始咨询后，在这里查看答复引用的政策，以及本轮测算条件。' }}</p></div>
      <article v-for="(group, groupIndex) in groups" :key="group.key" class="policy-source" :class="{ 'is-selected': group.originalIndices.includes(selectedSourceIndex) }">
        <button type="button" class="source-summary" :aria-expanded="expandedSources.includes(group.key)" :aria-controls="`policy-source-body-${groupIndex}`" @click="toggleSource(group.key)">
          <span class="source-meta"><el-icon><Document /></el-icon><span>政策原文</span><span>{{ group.sources.length }} 处引用</span><el-icon :class="{ 'is-expanded': expandedSources.includes(group.key) }"><ArrowDown /></el-icon></span>
          <h3>{{ group.title }}</h3>
        </button>
        <div v-if="expandedSources.includes(group.key)" :id="`policy-source-body-${groupIndex}`" class="source-body">
          <details v-for="(source, index) in group.sources" :id="`policy-source-fragment-${group.originalIndices[index]}`" :key="group.originalIndices[index]" class="source-fragment" :class="{ 'is-current': group.originalIndices[index] === selectedSourceIndex }" :open="group.originalIndices[index] === selectedSourceIndex">
            <summary><span class="citation-number">{{ group.citationNumbers[index] }}</span><span>资料{{ group.citationNumbers[index] }}</span><span class="fragment-location">{{ getPolicySourceLocation(source) }}</span></summary>
            <p v-if="source.excerpt" class="source-excerpt"><template v-if="citationTarget.matched && group.originalIndices[index] === selectedSourceIndex">{{ source.excerpt.slice(0, citationTarget.start) }}<mark :id="`policy-source-article-${selectedSourceIndex}`" class="source-article-match">{{ source.excerpt.slice(citationTarget.start, citationTarget.end) }}</mark>{{ source.excerpt.slice(citationTarget.end) }}</template><template v-else>{{ source.excerpt }}</template></p>
            <p v-else class="source-excerpt">本条来源未提供条款摘录，请打开原文核对引用位置。</p>
          </details>
          <div class="source-footer"><span><el-icon><Document /></el-icon>{{ sourceHost(group) }}</span><a v-if="originalUrl(group)" :href="originalUrl(group)" target="_blank" rel="noopener noreferrer">打开政策原文<el-icon><TopRight /></el-icon></a><span v-else class="source-unavailable">暂未提供原文链接</span></div>
        </div>
      </article>
    </el-tab-pane>
    <el-tab-pane label="测算条件" name="conditions">
      <dl v-if="conditions.length" class="evidence-conditions"><div v-for="condition in conditions" :key="condition.name"><dt>{{ condition.label }}</dt><dd>{{ condition.value }}</dd></div></dl>
      <div v-else class="evidence-empty"><el-icon><SetUp /></el-icon><h3>暂无结构化条件</h3><p>本条答复尚未附带可查看的测算参数。</p></div>
      <p class="evidence-note">每条答复保留各自的条件，继续提问不会改写已有结果。</p>
    </el-tab-pane>
  </el-tabs>
  <p v-if="sources.length" class="evidence-note"><el-icon><InfoFilled /></el-icon>适用范围与有效期以原文为准。</p>
</aside>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Reading, Fold, Document, ArrowDown, TopRight, InfoFilled, SetUp } from '@element-plus/icons-vue'
import { getPolicySources, getPolicyConditions, getPolicySourceLocation, getPolicySourceUrl, groupPolicySources, resolveCitationSource } from '@/utils/policyPresentation'
const props = defineProps({
  message: { type: Object, default: null },
  sourceIndex: { type: Number, default: 0 },
  revealToken: { type: Number, default: 0 },
  citationContext: { type: String, default: '' }
})
defineEmits(['close'])
const activeTab = ref('sources')
const expandedSources = ref([])
const sources = computed(() => getPolicySources(props.message?.metadata))
const groups = computed(() => groupPolicySources(sources.value))
const conditions = computed(() => getPolicyConditions(props.message?.metadata))
const citationTarget = computed(() => resolveCitationSource(sources.value, props.sourceIndex, props.citationContext))
const selectedSourceIndex = computed(() => citationTarget.value.sourceIndex)
const originalUrl = group => {
  const selected = group.originalIndices.includes(selectedSourceIndex.value) ? sources.value[selectedSourceIndex.value] : null
  return getPolicySourceUrl(selected) || group.url
}
const sourceHost = group => {
  const url = originalUrl(group)
  if (!url) return '引用资料'
  return url.startsWith('/') ? '本地政策原文' : new URL(url).hostname
}
const toggleSource = key => { expandedSources.value = expandedSources.value.includes(key) ? expandedSources.value.filter(value => value !== key) : [...expandedSources.value, key] }
watch([() => props.message, () => props.sourceIndex, () => props.citationContext, () => props.revealToken, sources], async () => {
  activeTab.value = 'sources'
  const group = groups.value.find(item => item.originalIndices.includes(selectedSourceIndex.value))
  expandedSources.value = group ? [group.key] : []
  await nextTick()
  const match = citationTarget.value.matched ? document.getElementById(`policy-source-article-${selectedSourceIndex.value}`) : null
  const target = match || document.getElementById(`policy-source-fragment-${selectedSourceIndex.value}`)
  const excerpt = match?.closest('.source-excerpt')
  if (excerpt) {
    excerpt.scrollTop += match.getBoundingClientRect().top - excerpt.getBoundingClientRect().top
    excerpt.scrollIntoView({ block: 'nearest' })
  } else {
    target?.scrollIntoView({ block: 'nearest' })
  }
}, { immediate: true })
</script>

<style scoped>.policy-evidence {
  min-width: 0;
  min-height: 0;
  grid-area: evidence;
  padding: 0;
  background: var(--wb-evidence);
  overflow-y: auto;
}
.evidence-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 52px;
  padding: 10px 18px;
  border-bottom: 1px solid var(--wb-line);
}
.evidence-heading h2 {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}
.evidence-heading h2 .el-icon {
  color: var(--wb-muted);
}
.evidence-context {
  font-size: 12px;
  color: var(--wb-muted);
  margin: 12px 18px;
}
.evidence-context::before {
  content: '·';
  color: var(--wb-blue);
  margin-right: 5px;
}
.evidence-tabs :deep(.el-tabs__header) {
  border-bottom: 1px solid var(--wb-line);
  padding: 0 18px;
  margin-bottom: 0;
}
.evidence-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}
.evidence-tabs :deep(.el-tabs__active-bar) { height: 2px; background: var(--wb-blue); }
.evidence-tabs :deep(.el-tabs__item) {
  height: 38px;
  font-size: 13px;
  color: var(--wb-muted);
  padding: 0 12px;
}
.evidence-tabs :deep(.el-tabs__item.is-active) {
  color: var(--wb-blue);
  font-weight: 500;
}
.policy-source {
  background: var(--wb-surface);
  border-bottom: 1px solid var(--wb-line);
  overflow: hidden;
}
.policy-source.is-selected {
  border-color: var(--wb-border);
}
.source-summary {
  display: block;
  text-align: left;
  width: 100%;
  border: 0;
  background: transparent;
  padding: 18px;
  color: var(--wb-ink);
}
.source-summary:hover {
  background: var(--wb-tint);
}
.source-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--wb-muted);
}
.source-meta > .el-icon {
  margin-left: auto;
  transition: transform var(--wb-motion);
}
.source-meta .is-expanded {
  transform: rotate(180deg);
}
.citation-number {
  display: inline-grid;
  place-items: center;
  min-width: 20px;
  height: 20px;
  border: 1px solid var(--wb-border);
  border-radius: 3px;
  color: var(--wb-blue);
  background: var(--wb-blue-soft);
  font: 12px var(--wb-number);
}
.source-summary h3 {
  font-size: 14px;
  line-height: 1.8;
  margin: 10px 0 0;
  font-weight: 500;
  overflow-wrap: anywhere;
}
.source-body {
  border-top: 1px solid var(--wb-line);
  padding: 0 18px 16px;
}
.source-excerpt {
  font-size: 13px;
  line-height: 1.9;
  color: var(--wb-ink);
  border-left: 2px solid var(--wb-border);
  padding-left: 10px;
  margin: 12px 0 4px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: min(340px, 46vh);
  overflow-y: auto;
  overscroll-behavior: contain;
}
.source-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 14px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--wb-muted);
}
.source-footer > span, .source-footer a {
  display: flex;
  align-items: center;
  gap: 5px;
}
.source-footer a {
  color: var(--wb-blue);
  text-decoration: none;
}
.source-footer a:hover {
  text-decoration: underline;
}
.source-unavailable {
  font-size: 12px;
}
.evidence-note {
  display: flex;
  align-items: baseline;
  gap: 7px;
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.9;
  margin: 18px;
}
.evidence-note .el-icon {
  flex-shrink: 0;
}
.evidence-empty {
  text-align: center;
  padding: 44px 20px 30px;
  color: var(--wb-muted);
}
.evidence-empty > .el-icon {
  font-size: 28px;
  color: var(--wb-blue);
  opacity: .65;
}
.evidence-empty h3 {
  margin: 16px 0 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--wb-ink);
}
.evidence-empty p {
  font-size: 13px;
  line-height: 1.9;
}
.evidence-conditions {
  padding: 8px 18px;
  margin: 0;
}
.evidence-conditions > div {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 0;
  border-bottom: 1px solid var(--wb-line);
  font-size: 14px;
}
.evidence-conditions dt {
  color: var(--wb-muted);
}
.evidence-conditions dd {
  text-align: right;
  overflow-wrap: anywhere;
  min-width: 0;
}
.source-meta > .el-icon:first-child { margin-left: 0; }
.source-meta > span + span { margin-left: auto; }
.source-meta > .el-icon:last-child { margin-left: 0; }
.source-article-match { color: var(--wb-ink); background: var(--wb-blue-soft); outline: 1px solid var(--wb-border); border-radius: 2px; padding: 1px 2px; scroll-margin: 18px; }
.source-fragment { border-bottom: 1px solid var(--wb-line); padding: 10px 0; }
.source-fragment summary { display: flex; align-items: center; gap: 8px; cursor: pointer; color: var(--wb-muted); font-size: 12px; list-style: none; }
.source-fragment summary::-webkit-details-marker { display: none; }
.source-fragment summary::after { content: '+'; margin-left: auto; font-size: 16px; }
.source-fragment[open] summary::after { content: '−'; }
.source-fragment.is-current .citation-number { border-color: var(--wb-blue); }
.fragment-location { color: var(--wb-muted); font-size: 11px; }
.source-footer > span { min-width: 0; overflow-wrap: anywhere; }
</style>
