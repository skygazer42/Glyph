<template>
<aside id="policy-evidence" class="policy-evidence" aria-label="政策依据">
  <div class="evidence-heading">
    <h2>
      <el-icon>
        <Reading />
      </el-icon>
      政策依据
    </h2>
    <el-tooltip content="收起政策依据" placement="left">
      <button type="button" class="workbench-icon" aria-label="收起政策依据" @click="$emit('close')">
        <el-icon>
          <Fold />
        </el-icon>
      </button>
    </el-tooltip>
  </div>
  <p class="evidence-context">
    {{ message ? `对应所选答复 · ${sources.length} 项来源` : '随咨询答复更新' }}
  </p>
  <el-tabs v-model="activeTab" stretch class="evidence-tabs">
    <el-tab-pane :label="`政策来源${sources.length ? ` ${sources.length}` : ''}`" name="sources">
      <div v-if="!sources.length" class="evidence-empty">
        <el-icon>
          <Document />
        </el-icon>
        <h3>
          {{ message ? '本条答复暂无政策来源' : '政策依据，一处查阅' }}
        </h3>
        <p>
          {{ message ? '该答复未附带来源信息，可继续追问政策名称或原文。' : '开始咨询后，在这里查看答复引用的政策，以及本轮测算条件。' }}
        </p>
      </div>
      <article
        v-for="(source, index) in sources"
        :key="`${index}-${source.title}-${source.path}`"
        class="policy-source"
        :class="{ 'is-selected': index === sourceIndex }"
      >
        <button
          type="button"
          class="source-summary"
          :aria-expanded="expandedSources.includes(index)"
          :aria-controls="`policy-source-body-${index}`"
          @click="toggleSource(index)"
        >
          <span class="source-meta">
            <span class="citation-number">
              {{ index + 1 }}
            </span>
            <span>
              政策来源
            </span>
            <el-icon :class="{ 'is-expanded': expandedSources.includes(index) }">
              <ArrowDown />
            </el-icon>
          </span>
          <h3>
            {{ source.title || '未命名政策资料' }}
          </h3>
        </button>
        <div v-if="expandedSources.includes(index)" :id="`policy-source-body-${index}`" class="source-body">
          <p v-if="source.origin" class="source-origin">
            {{ source.origin }}
          </p>
          <p class="source-excerpt">
            本条来源未提供可核对的条款摘录，请查看原文确认适用范围与有效期。
          </p>
          <div class="source-footer">
            <span>
              <el-icon>
                <Document />
              </el-icon>
              引用资料
            </span>
            <a
              v-if="getSourceUrl(source.path) || getSourceUrl(source.origin)"
              :href="getSourceUrl(source.path) || getSourceUrl(source.origin)"
              target="_blank"
              rel="noopener noreferrer"
            >
              查看原文
              <el-icon>
                <Right />
              </el-icon>
            </a>
            <span v-else class="source-unavailable">
              暂无原文链接
            </span>
          </div>
        </div>
      </article>
    </el-tab-pane>
    <el-tab-pane label="测算条件" name="conditions">
      <dl v-if="conditions.length" class="evidence-conditions">
        <div v-for="condition in conditions" :key="condition.name">
          <dt>
            {{ condition.label }}
          </dt>
          <dd>
            {{ condition.value }}
          </dd>
        </div>
      </dl>
      <div v-else class="evidence-empty">
        <el-icon>
          <SetUp />
        </el-icon>
        <h3>
          暂无结构化条件
        </h3>
        <p>
          接口返回测算参数后，将在这里保留该条答复的条件快照。
        </p>
      </div>
      <p class="evidence-note">
        每条答复保留各自的条件，继续提问不会改写已有结果。
      </p>
    </el-tab-pane>
  </el-tabs>
  <p v-if="sources.length" class="evidence-note">
    <el-icon>
      <InfoFilled />
    </el-icon>
    点击正文引用编号，可定位对应来源。政策适用范围与有效期以原文为准。
  </p>
</aside>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Reading, Fold, Document, ArrowDown, Right, InfoFilled, SetUp } from '@element-plus/icons-vue'
import { getPolicySources, getPolicyConditions, getSourceUrl } from '@/utils/policyPresentation'
const props = defineProps({
  message: { type: Object, default: null },
  sourceIndex: { type: Number, default: 0 },
  revealToken: { type: Number, default: 0 }
})
defineEmits(['close'])
const activeTab = ref('sources')
const expandedSources = ref([0])
const sources = computed(() => getPolicySources(props.message?.metadata))
const conditions = computed(() => getPolicyConditions(props.message?.metadata))
watch([() => props.message, () => props.revealToken], () => {
  activeTab.value = 'sources'
  expandedSources.value = [props.sourceIndex]
})
const toggleSource = (index) => {
  expandedSources.value = expandedSources.value.includes(index) ? expandedSources.value.filter(value => value !== index) : [...expandedSources.value, index]
}
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
  padding: 18px;
}
.source-origin {
  color: var(--wb-muted);
  font-size: 12px;
  margin-bottom: 12px;
  overflow-wrap: anywhere;
}
.source-excerpt {
  font-size: 14px;
  line-height: 1.9;
  color: var(--wb-muted);
  border-left: 2px solid var(--wb-border);
  padding-left: 10px;
}
.source-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 20px;
  border-top: 1px solid var(--wb-line);
  padding-top: 14px;
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
</style>
