<template>
<section class="subsidy-result" aria-label="补贴测算结果">
  <div class="result-heading">
    <h2>
      补贴测算结果
    </h2>
    <span>
      <el-icon>
        <CircleCheck />
      </el-icon>
      规则计算完成
    </span>
  </div>
  <p class="result-caption">
    根据本轮条件与政策规则测算，具体办理以政策原文为准。
  </p>
  <dl class="subsidy-metrics">
    <div class="subsidy-metric">
      <dt>
        测算补贴金额
      </dt>
      <dd class="metric-amount">
        {{ formatPolicyNumber(result.amount) }}
        <span>
          元
        </span>
      </dd>
      <p>
        购买金额 {{ formatPolicyNumber(result.price) }} 元
      </p>
    </div>
    <div class="subsidy-metric">
      <dt>
        适用补贴比例
      </dt>
      <dd>
        {{ formatPolicyNumber(result.rate * 100) }}
        <span>
          %
        </span>
      </dd>
      <p>
        {{ result.energyLevel === 1 ? '一级能效' : result.energyLevel === 2 ? '二级能效' : '按本轮规则确定' }}
      </p>
    </div>
    <div v-if="result.cap !== null" class="subsidy-metric">
      <dt>
        单件补贴上限
      </dt>
      <dd>
        {{ formatPolicyNumber(result.cap) }}
        <span>
          元
        </span>
      </dd>
      <p>
        按比例计算后封顶
      </p>
    </div>
  </dl>
  <div v-if="sourceCount" class="result-source-row">
    <span>
      本次结果依据政策规则生成。
    </span>
    <span class="result-citations">
      政策依据
      <button
        v-for="number in sourceCount"
        :key="number"
        type="button"
        class="citation"
        :aria-label="`查看政策依据 ${number}`"
        @click="$emit('source', number - 1)"
      >
        {{ number }}
      </button>
    </span>
  </div>
  <div class="calculation-line">
    <span class="calculation-label">
      计算明细
    </span>
    <p>
      {{ formatPolicyNumber(result.price) }}
      <small>
        元
      </small>
      <span class="formula-operator">
        ×
      </span>
      {{ formatPolicyNumber(result.rate * 100) }}
      <small>
        %
      </small>
      <span class="formula-operator">
        =
      </span>
      {{ formatPolicyNumber(result.rawAmount) }}
      <small>
        元
      </small>
    </p>
    <span class="cap-status">
      {{ result.rawAmount > result.amount ? `按规则以 ${formatPolicyNumber(result.amount)} 元计` : result.cap !== null ? '未超过单件上限' : '以规则返回结果为准' }}
    </span>
  </div>
  <details v-if="result.traces.length" class="calculation-trace" @toggle="handleTraceToggle">
    <summary>
      <span>
        <el-icon>
          <InfoFilled />
        </el-icon>
        规则计算过程
      </span>
      <span class="trace-toggle">
        <span class="when-closed">
          展开
        </span>
        <span class="when-open">
          收起
        </span>
        <el-icon>
          <ArrowDown />
        </el-icon>
      </span>
    </summary>
    <ol>
      <li v-for="(trace, index) in result.traces" :key="index">
        {{ trace }}
      </li>
    </ol>
  </details>
</section>
</template>

<script setup>
import { ArrowDown, CircleCheck, InfoFilled } from '@element-plus/icons-vue'
import { formatPolicyNumber } from '@/utils/policyPresentation'
defineProps({ result: { type: Object, required: true }, sourceCount: { type: Number, default: 0 } })
const emit = defineEmits(['source', 'expanded'])
const handleTraceToggle = (event) => {
  if (event.target.open) emit('expanded', event.target)
}
</script>

<style scoped>.subsidy-result {
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius);
  padding: 22px 24px 0;
  background: var(--wb-surface);
}
.result-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.result-heading h2 {
  font-size: 17px;
  font-weight: 600;
  margin: 0;
}
.result-heading > span {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--wb-muted);
  font-size: 12px;
}
.result-caption {
  margin: 8px 0 20px;
  color: var(--wb-muted);
  font-size: 13px;
}
.subsidy-metrics {
  display: flex;
  padding: 18px 0;
  margin: 0 0 20px;
  border: 1px solid var(--wb-line);
  border-radius: 6px;
  background: var(--wb-tint);
}
.subsidy-metric {
  flex: 1;
  min-width: 0;
  padding: 0 20px;
}
.subsidy-metric + .subsidy-metric {
  border-left: 1px solid var(--wb-line);
}
.subsidy-metric dt {
  font-size: 13px;
  color: var(--wb-muted);
  margin-bottom: 3px;
}
.subsidy-metric dd {
  font: 500 30px/1.1 var(--wb-number);
  margin: 0;
  padding-top: 9px;
  white-space: nowrap;
  letter-spacing: -.7px;
}
.subsidy-metric dd.metric-amount {
  font-size: 38px;
  padding-top: 0;
}
.subsidy-metric dd span {
  font-size: 14px;
  margin-left: 4px;
  letter-spacing: 0;
}
.subsidy-metric p {
  font-size: 12px;
  margin-top: 8px;
  color: var(--wb-muted);
}
.result-source-row {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: space-between;
  margin: 0 0 20px;
  font-size: 15px;
}
.result-citations {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  font-size: 12px;
  color: var(--wb-muted);
}
.calculation-line {
  border-top: 1px solid var(--wb-line);
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  padding: 16px 0;
}
.calculation-label, .cap-status {
  font-size: 12px;
  color: var(--wb-muted);
}
.calculation-line p {
  font: 500 16px/1.8 var(--wb-number);
  margin: 0;
}
.calculation-line small {
  font-size: 12px;
  font-weight: 400;
}
.formula-operator {
  color: var(--wb-muted);
  margin: 0 10px;
  font-weight: 400;
}
.cap-status {
  margin-left: auto;
}
.calculation-trace {
  border-top: 1px solid var(--wb-line);
}
.calculation-trace summary {
  list-style: none;
  padding: 14px 0;
  display: flex;
  justify-content: space-between;
  cursor: pointer;
  font-size: 13px;
  color: var(--wb-blue);
}
.calculation-trace summary::-webkit-details-marker {
  display: none;
}
.calculation-trace summary > span {
  display: flex;
  align-items: center;
  gap: 6px;
}
.trace-toggle {
  color: var(--wb-muted);
  font-size: 12px;
}
.when-open, [open] .when-closed {
  display: none;
}
[open] .when-open {
  display: inline;
}
[open] .trace-toggle .el-icon {
  transform: rotate(180deg);
}
.calculation-trace ol {
  padding: 0 0 18px 22px;
  font-size: 14px;
  line-height: 1.9;
  color: var(--wb-muted);
}
@media (max-width: 1200px) {
  .subsidy-metric {
    padding: 0 12px;
  }
}
@media (max-width: 600px) {
  .subsidy-result {
    padding: 16px 14px 0;
  }
  .subsidy-metrics {
    flex-wrap: wrap;
    gap: 16px 0;
  }
  .subsidy-metric {
    flex-basis: 50%;
  }
  .subsidy-metric dd.metric-amount {
    font-size: 30px;
  }
  .subsidy-metric dd {
    font-size: 26px;
    padding-top: 5px;
  }
  .subsidy-metric:last-child {
    border: 0;
  }
  .result-source-row {
    flex-wrap: wrap;
  }
  .result-heading {
    align-items: flex-start;
  }
  .result-heading > span {
    font-size: 10px;
  }
}
</style>
