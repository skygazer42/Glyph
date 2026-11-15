<template>
  <div class="workspace-module dsl-generator">
    <section class="rule-composer" aria-labelledby="rule-composer-heading">
      <header class="composer-heading">
        <div>
          <h2 id="rule-composer-heading">规则编制</h2>
          <p>粘贴政策原文，生成并核对结构化规则。</p>
        </div>
        <span class="generation-status" role="status" :aria-busy="appStore.dslState.generating">
          <el-icon v-if="appStore.dslState.generating" class="is-loading"><Loading /></el-icon>
          <el-icon v-else-if="appStore.hasGeneratedDSL"><DocumentChecked /></el-icon>
          <span>{{ appStore.dslState.generating ? '正在生成' : appStore.hasGeneratedDSL ? '已生成 · 请核对' : '等待输入' }}</span>
        </span>
      </header>

      <el-collapse-transition>
        <section v-if="showExamples" class="policy-example" aria-label="政策文本示例">
          <header>
            <strong>政策文本示例</strong>
            <el-button text type="primary" :disabled="appStore.dslState.generating" @click="useExample">填入原文</el-button>
          </header>
          <pre>{{ exampleText }}</pre>
        </section>
      </el-collapse-transition>

      <div class="rule-editor-grid">
        <CodeEditor
          v-model="appStore.dslState.inputText"
          class="policy-input-editor"
          title="政策原文"
          mode="input"
          :rows="10"
          :disabled="appStore.dslState.generating"
          placeholder="请粘贴需要转为规则的政策条款，保留适用对象、条件、标准和有效期限。"
        >
          <template #title>
            <div class="editor-identity">
              <span class="editor-step" aria-hidden="true">01</span>
              <div><h3>政策原文</h3><span>保留完整条款，作为生成依据</span></div>
            </div>
          </template>
          <template #actions>
            <el-button text type="primary" :aria-expanded="showExamples" @click="showExamples = !showExamples">
              {{ showExamples ? '收起示例' : '查看示例' }}
            </el-button>
          </template>
          <template #footer>
            <div class="editor-footer-row">
              <span class="editor-note">{{ inputCharacterCount.toLocaleString('zh-CN') }} 字</span>
              <div class="editor-button-group">
                <el-button :disabled="!appStore.dslState.inputText && !appStore.hasGeneratedDSL" @click="clearInput">
                  {{ appStore.dslState.generating ? '取消并清空' : '清空' }}
                </el-button>
                <el-button type="primary" :loading="appStore.dslState.generating" :disabled="inputCharacterCount === 0" @click="generateDSL">
                  <el-icon v-if="!appStore.dslState.generating"><MagicStick /></el-icon>
                  <span>生成规则</span>
                </el-button>
              </div>
            </div>
          </template>
        </CodeEditor>

        <CodeEditor
          v-model="appStore.dslState.generatedYAML"
          class="rule-output-editor"
          title="结构化规则"
          mode="display"
          language="yaml"
          :show-copy="true"
          :empty-text="appStore.dslState.generating ? '正在解析政策条款，请稍候…' : '生成后，结构化规则将在这里显示'"
          :aria-busy="appStore.dslState.generating"
        >
          <template #title>
            <div class="editor-identity">
              <span class="editor-step" aria-hidden="true">02</span>
              <div><h3>结构化规则</h3><span>YAML 格式 · 核对条件与计算逻辑</span></div>
            </div>
          </template>
          <template #footer>
            <div class="editor-footer-row">
              <span class="editor-note">{{ appStore.hasGeneratedDSL ? '核对原文后再保存' : '生成后可保存与测试' }}</span>
              <div class="editor-button-group">
                <el-button :disabled="!appStore.hasGeneratedDSL || appStore.dslState.generating" @click="testCurrentDSL">测试规则</el-button>
                <el-button type="primary" :icon="FolderChecked" :loading="saving" :disabled="!appStore.hasGeneratedDSL || appStore.dslState.generating" @click="saveDSL">保存规则</el-button>
              </div>
            </div>
          </template>
        </CodeEditor>
      </div>
      <div class="capability-note">
        <el-icon><InfoFilled /></el-icon>
        <span>支持粘贴文本生成；文档导入与批量生成暂不可用。</span>
      </div>
    </section>

    <section class="saved-rules" aria-labelledby="saved-rules-heading">
      <header class="rules-heading">
        <div class="rules-heading-label"><h2 id="saved-rules-heading">已保存的规则</h2><span v-if="!tableLoading && !listError">{{ appStore.dslState.dslList.length }} 条</span></div>
        <div class="rules-toolbar">
          <SearchBar v-model="searchQuery" placeholder="搜索规则名称或 ID" :show-button="false" :debounce="300" @input="filterRules" />
          <el-tooltip content="刷新规则列表" placement="top">
            <el-button :icon="Refresh" :loading="tableLoading" aria-label="刷新规则列表" @click="loadDSLList" />
          </el-tooltip>
        </div>
      </header>
      <div v-if="listError" class="rules-load-error" role="alert">
        <el-icon><Warning /></el-icon>
        <div>
          <strong>规则列表加载失败</strong>
          <p>暂时无法读取规则列表，请稍后重试。</p>
          <details class="rules-error-details">
            <summary>查看错误详情</summary>
            <p>{{ listError }}</p>
          </details>
        </div>
        <el-button :loading="tableLoading" @click="loadDSLList">重试</el-button>
      </div>
      <div v-else class="rules-table-wrap">
        <el-table :data="filteredRules" v-loading="tableLoading" class="rules-table">
          <el-table-column prop="title" label="规则名称" min-width="210" show-overflow-tooltip />
          <el-table-column prop="rule_id" label="规则 ID" min-width="190" show-overflow-tooltip>
            <template #default="scope"><span class="rule-id">{{ scope.row.rule_id }}</span></template>
          </el-table-column>
          <el-table-column prop="doc_type" label="文档类型" width="110">
            <template #default="scope"><span>{{ scope.row.doc_type || '通用' }}</span></template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="scope"><span class="rule-state" :class="{ 'is-active': scope.row.is_active }"><i aria-hidden="true"></i>{{ scope.row.is_active ? '已激活' : '未激活' }}</span></template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="168">
            <template #default="scope"><span class="rule-date">{{ formatDate(scope.row.created_at) }}</span></template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="scope">
              <el-button link type="primary" @click="viewRule(scope.row)">查看</el-button>
              <el-button link type="primary" @click="testRule(scope.row)">测试</el-button>
            </template>
          </el-table-column>
          <template #empty><div class="rules-empty"><strong>{{ searchQuery ? '未找到匹配规则' : '暂无已保存的规则' }}</strong><span>{{ searchQuery ? '换个名称或规则 ID 试试' : '在上方生成并核对规则后，保存到规则库' }}</span></div></template>
        </el-table>
      </div>
      <footer class="rules-footer">
        <span>规则编辑与删除暂不可用</span>
        <el-pagination v-if="!tableLoading && !listError && matchingRules.length > pageSize" v-model:current-page="currentPage" :page-size="pageSize" :total="matchingRules.length" layout="total, prev, pager, next" />
      </footer>
    </section>

    <el-dialog v-model="showTestDialog" title="测试规则" width="640px" class="glyph-dialog dsl-test-dialog">
      <p class="dialog-description">输入实际条件，检查规则返回的状态与计算结果。</p>
      <el-form :model="testForm" label-position="top" class="rule-test-form">
        <el-form-item label="规则 ID"><el-input v-model="testForm.ruleId" disabled /></el-form-item>
        <div class="test-inputs-heading">输入参数</div>
        <el-form-item v-for="key in Object.keys(testForm.inputs)" :key="key" :label="formatParamLabel(key)">
          <el-input v-model="testForm.inputs[key]" :placeholder="`请输入${formatParamLabel(key)}`" :aria-label="formatParamLabel(key)" />
        </el-form-item>
        <p v-if="Object.keys(testForm.inputs).length === 0" class="dialog-description">此规则没有需要填写的输入参数，可直接执行测试。</p>
      </el-form>
      <template #footer>
        <el-button @click="showTestDialog = false">取消</el-button>
        <el-button type="primary" :loading="testing" @click="executeTest">执行测试</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showResultDialog" title="规则测试结果" width="640px" class="glyph-dialog dsl-result-dialog">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="执行状态"><span class="result-status">{{ testResult.status || '未返回状态' }}</span></el-descriptions-item>
        <el-descriptions-item label="最终结果"><span class="result-value">{{ testResult.final_result ?? '未返回结果' }}</span></el-descriptions-item>
        <el-descriptions-item v-if="testResult.trace" label="执行跟踪"><pre class="trace-content">{{ testResult.trace }}</pre></el-descriptions-item>
      </el-descriptions>
      <template #footer><el-button type="primary" @click="showResultDialog = false">完成</el-button></template>
    </el-dialog>

    <el-dialog v-model="showDetailDialog" title="规则详情" width="800px" class="glyph-dialog dsl-detail-dialog">
      <CodeEditor v-model="currentRuleDetail" class="rule-detail-editor" title="结构化规则内容" mode="display" language="json" :show-copy="true" />
      <template #footer><el-button @click="showDetailDialog = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAppStore } from '@/stores/app'
import { dslApi } from '@/api'
import { CodeEditor, SearchBar } from '@/components'
import { DocumentChecked, FolderChecked, InfoFilled, Loading, MagicStick, Refresh, Warning } from '@element-plus/icons-vue'

// Store
const appStore = useAppStore()

// Refs
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const tableLoading = ref(false)
const listError = ref('')
const saving = ref(false)
const showExamples = ref(false)
const showTestDialog = ref(false)
const showResultDialog = ref(false)
const showDetailDialog = ref(false)
const testing = ref(false)
const currentRuleDetail = ref('')

// Test form
const testForm = ref({
  ruleId: '',
  inputs: {}
})

// Test result
const testResult = ref({
  status: '',
  final_result: '',
  trace: ''
})

// Example text
const exampleText = `济南市消费券发放实施细则

一、发放标准
1. 满100元减20元
2. 满200元减50元
3. 满500元减150元
4. 满1000元减350元

二、使用范围
适用于全市参与活动的餐饮、零售、文旅等商户。

三、发放时间
2025年1月1日至2025年3月31日

四、使用规则
1. 每人每日限用1张消费券
2. 消费券不可叠加使用
3. 消费券不可兑换现金`

// Computed
const inputCharacterCount = computed(() => appStore.dslState.inputText.trim().length)

const matchingRules = computed(() => {
  const rules = appStore.dslState.dslList
  if (searchQuery.value.length === 0) {
    return rules
  }

  const query = searchQuery.value.toLowerCase()
  return rules.filter(rule =>
    rule.rule_id.toLowerCase().includes(query) ||
    rule.title.toLowerCase().includes(query)
  )
})

const filteredRules = computed(() => {
  const lastPage = Math.max(1, Math.ceil(matchingRules.value.length / pageSize.value))
  const page = Math.min(currentPage.value, lastPage)
  const start = (page - 1) * pageSize.value
  const end = start + pageSize.value
  return matchingRules.value.slice(start, end)
})

// Methods
let generationRequest = null
let listRequest = null
let detailRequest = null
let testRequest = null
let testFormRequest = null
let saveRequest = null

const useExample = () => {
  appStore.dslState.inputText = exampleText
  showExamples.value = false
  appStore.showNotification('success', '示例已加载')
}

const clearInput = () => {
  generationRequest = null
  testRequest = null
  testFormRequest = null
  testing.value = false
  appStore.resetDSLState()
  testForm.value.ruleId = ''
  testForm.value.inputs = {}
}

const generateDSL = async () => {
  if (appStore.dslState.inputText.trim().length === 0) {
    appStore.showNotification('warning', '请输入政策文本')
    return
  }

  if (appStore.dslState.generating) {
    return
  }
  const inputText = appStore.dslState.inputText
  appStore.dslState.generating = true
  const request = {}
  generationRequest = request
  try {
    const response = await dslApi.generateFromText(
      inputText,
      {
        source: 'manual_input',
        generated_at: new Date().toISOString()
      }
    )

    if (generationRequest !== request) {
      return
    }
    if (appStore.dslState.inputText !== inputText) {
      return
    }
    const { yaml_content, dsl_data } = response
    appStore.dslState.generatedYAML = yaml_content
    const { rule_id, inputs } = dsl_data
    appStore.dslState.generatedRuleId = rule_id
    appStore.dslState.generatedInputs = inputs || []
    appStore.showNotification('success', 'DSL 规则生成成功')
  } catch (error) {
    if (generationRequest !== request) {
      return
    }
    appStore.showNotification('error', `生成失败: ${error.message}`)
  } finally {
    if (generationRequest === request) {
      appStore.dslState.generating = false
    }
  }
}

const saveDSL = async () => {
  if (!appStore.dslState.generatedYAML) {
    appStore.showNotification('warning', '没有可保存的 DSL 规则')
    return
  }

  if (saving.value) {
    return
  }
  saving.value = true
  const request = {}
  saveRequest = request
  try {
    await dslApi.saveDSL({
      rule_id: appStore.dslState.generatedRuleId,
      yaml_content: appStore.dslState.generatedYAML
    })
    if (saveRequest !== request) {
      return
    }
    appStore.showNotification('success', 'DSL 规则保存成功')
    loadDSLList()
  } catch (error) {
    if (saveRequest === request) {
      appStore.showNotification('error', `保存失败: ${error.message}`)
    }
  } finally {
    if (saveRequest === request) {
      saveRequest = null
      saving.value = false
    }
  }
}

const loadDSLList = async () => {
  tableLoading.value = true
  listError.value = ''
  const request = {}
  listRequest = request
  try {
    const response = await dslApi.listDSL()
    if (listRequest !== request) {
      return
    }
    appStore.dslState.dslList = response.rules || []
  } catch (error) {
    if (listRequest !== request) {
      return
    }
    listError.value = error.message || '请检查连接后重试'
    appStore.showNotification('error', '规则列表加载失败，请稍后重试')
  } finally {
    if (listRequest === request) {
      tableLoading.value = false
    }
  }
}

const filterRules = () => {
  currentPage.value = 1
}

const viewRule = async (rule) => {
  const request = {}
  detailRequest = request
  try {
    const response = await dslApi.getDSL(rule.rule_id)
    if (detailRequest !== request) {
      return
    }
    currentRuleDetail.value = JSON.stringify(response.rule, null, 2)
    showDetailDialog.value = true
  } catch (error) {
    if (detailRequest !== request) {
      return
    }
    appStore.showNotification('error', `查看失败: ${error.message}`)
  }
}

const testRule = async (rule) => {
  const request = {}
  testFormRequest = request
  testRequest = null
  testing.value = false
  try {
    const response = await dslApi.getDSL(rule.rule_id)
    if (testFormRequest !== request) {
      return
    }
    testForm.value.ruleId = rule.rule_id
    testForm.value.inputs = {}
    for (const input of response.rule.inputs || []) {
      testForm.value.inputs[input.name] = ''
    }
    showTestDialog.value = true
  } catch (error) {
    if (testFormRequest !== request) {
      return
    }
    appStore.showNotification('error', `加载测试参数失败: ${error.message}`)
  }
}

const testCurrentDSL = () => {
  if (!appStore.dslState.generatedRuleId) {
    appStore.showNotification('warning', '请先生成 DSL 规则')
    return
  }
  testFormRequest = null
  testRequest = null
  testing.value = false
  testForm.value.ruleId = appStore.dslState.generatedRuleId
  testForm.value.inputs = {}
  for (const input of appStore.dslState.generatedInputs) {
    testForm.value.inputs[input.name] = ''
  }
  showTestDialog.value = true
}

const executeTest = async () => {
  testing.value = true
  const request = {}
  testRequest = request
  const ruleId = testForm.value.ruleId
  const inputs = { ...testForm.value.inputs }
  try {
    const response = await dslApi.testDSL(
      ruleId,
      inputs
    )
    if (testRequest !== request) {
      return
    }
    if (testForm.value.ruleId !== ruleId || JSON.stringify(testForm.value.inputs) !== JSON.stringify(inputs)) {
      return
    }
    testResult.value = { status: '', final_result: '', trace: '', ...response.result }
    showTestDialog.value = false
    showResultDialog.value = true
  } catch (error) {
    if (testRequest !== request) {
      return
    }
    appStore.showNotification('error', `测试失败: ${error.message}`)
  } finally {
    if (testRequest === request) {
      testing.value = false
    }
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) {
    return '-'
  }
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatParamLabel = (key) => {
  const labels = {
    price: '商品价格',
    energy_level: '能效等级',
    category: '商品类别',
    quantity: '购买数量',
    amount: '消费金额'
  }
  return labels[key] || key
}

// Lifecycle
onMounted(() => {
  loadDSLList()
})
onBeforeUnmount(() => {
  saveRequest = null
  if (generationRequest) {
    appStore.dslState.generating = false
  }
  testFormRequest = null
  generationRequest = null
  listRequest = null
  detailRequest = null
  testRequest = null
})
</script>

<style scoped>
.dsl-generator {
  display: grid;
  gap: 24px;
  min-width: 0;
}
.rule-composer,
.saved-rules {
  min-width: 0;
  border: 1px solid var(--wb-line);
  border-radius: var(--wb-radius);
  background: var(--wb-surface);
}
.composer-heading,
.rules-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  padding: 20px 22px;
}
.composer-heading h2,
.rules-heading h2 {
  margin: 0;
  color: var(--wb-ink);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.5;
}
.composer-heading p {
  margin: 5px 0 0;
  color: var(--wb-muted);
  font-size: 13px;
  line-height: 1.7;
}
.generation-status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--wb-blue);
  font-size: 13px;
}
.rule-editor-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  margin: 0 22px;
  border: 1px solid var(--wb-line);
  border-radius: 6px;
  overflow: hidden;
}
.rule-editor-grid :deep(.code-editor) {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 0;
  border-radius: 0;
}
.policy-input-editor {
  border-right: 1px solid var(--wb-line) !important;
}
.rule-editor-grid :deep(.editor-header) {
  min-height: 72px;
  gap: 8px;
  padding: 14px 16px;
  background: var(--wb-tint);
  border-bottom: 1px solid var(--wb-line);
}
.editor-identity {
  display: flex;
  align-items: center;
  gap: 10px;
}
.editor-step {
  display: grid;
  place-items: center;
  flex: 0 0 28px;
  height: 28px;
  border: 1px solid var(--wb-border);
  border-radius: 5px;
  background: var(--wb-surface);
  color: var(--wb-blue);
  font: 500 13px var(--wb-number);
}
.editor-identity h3 {
  margin: 0;
  color: var(--wb-ink);
  font-size: 15px;
  font-weight: 600;
  line-height: 1.7;
}
.editor-identity div > span {
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.7;
}
.rule-editor-grid :deep(.editor-body) {
  flex: 1;
  min-height: 298px;
  background: var(--wb-surface);
}
.policy-input-editor :deep(.el-textarea__inner) {
  min-height: 298px !important;
  height: 298px;
  max-height: 520px;
  padding: 16px;
  box-shadow: none;
  font-family: var(--wb-font);
  color: var(--wb-ink);
  font-size: 14px;
  line-height: 1.85;
  resize: vertical;
}
.policy-input-editor :deep(.el-textarea__inner:focus) {
  box-shadow: inset 0 0 0 1px var(--wb-blue);
}
.rule-output-editor :deep(.code-display),
.rule-detail-editor :deep(.code-display) {
  max-height: 520px;
  background: var(--wb-surface);
  color: var(--wb-ink);
}
.rule-output-editor :deep(.code-display pre),
.rule-detail-editor :deep(.code-display pre) {
  color: var(--wb-ink);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.85;
}
.rule-output-editor :deep(.el-empty) {
  min-height: 298px;
  padding: 36px 20px;
}
.rule-output-editor :deep(.el-empty__image) {
  width: 64px;
  height: 64px;
}
.rule-output-editor :deep(.el-empty__description p) {
  font-size: 13px;
  line-height: 1.8;
}
.rule-editor-grid :deep(.editor-footer) {
  padding: 14px 16px;
  border-color: var(--wb-line);
  background: var(--wb-surface);
}
.editor-footer-row,
.editor-button-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.editor-footer-row {
  justify-content: space-between;
  flex-wrap: wrap;
  row-gap: 12px;
}
.editor-button-group .el-button + .el-button {
  margin-left: 0;
}
.editor-note {
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.7;
  font-variant-numeric: tabular-nums;
}
.editor-button-group .el-button {
  min-height: 34px;
}
.editor-button-group .el-icon + span {
  margin-left: 5px;
}
.capability-note {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  padding: 13px 22px 16px;
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.8;
}
.capability-note .el-icon {
  flex-shrink: 0;
  margin-top: 4px;
}
.policy-example {
  margin: 0 22px 18px;
  padding: 12px 16px;
  border: 1px solid var(--wb-border);
  border-radius: 6px;
  background: var(--wb-blue-soft);
}
.policy-example header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
}
.policy-example pre {
  max-height: 220px;
  overflow: auto;
  margin: 8px 0 0;
  color: var(--wb-ink);
  font-family: var(--wb-font);
  font-size: 14px;
  line-height: 1.9;
  white-space: pre-wrap;
}
.rules-heading-label,
.rules-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.rules-heading-label > span {
  color: var(--wb-muted);
  font: 13px var(--wb-number);
}
.rules-toolbar :deep(.search-bar) {
  width: 240px;
}
.rules-table-wrap {
  max-width: 100%;
  overflow-x: auto;
  border-top: 1px solid var(--wb-line);
}
.rules-table {
  width: 100%;
  min-width: 820px;
}
.rules-table :deep(.el-table__cell:first-child .cell) {
  padding-left: 22px;
}
.rule-id {
  color: var(--wb-muted);
  font-family: var(--font-mono);
  font-size: 12px;
}
.rule-date {
  color: var(--wb-muted);
  font-variant-numeric: tabular-nums;
}
.rule-state {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--wb-muted);
}
.rule-state i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.rule-state.is-active {
  color: var(--wb-blue);
}
.rules-empty {
  display: grid;
  gap: 5px;
  padding: 26px 16px;
  line-height: 1.8;
}
.rules-empty strong {
  color: var(--wb-ink);
  font-size: 14px;
  font-weight: 500;
}
.rules-empty span {
  color: var(--wb-muted);
  font-size: 13px;
}
.rules-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  padding: 14px 22px;
  color: var(--wb-muted);
  font-size: 12px;
}
.rules-load-error {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 22px;
  border-top: 1px solid var(--wb-line);
  color: var(--wb-error);
  font-size: 14px;
}
.rules-load-error > div {
  flex: 1;
  min-width: 0;
}
.rules-load-error p {
  margin: 4px 0 0;
  color: var(--wb-muted);
  font-size: 13px;
  overflow-wrap: anywhere;
}
.rules-error-details {
  margin-top: 8px;
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.8;
}
.rules-error-details summary {
  width: fit-content;
  color: var(--wb-blue);
  cursor: pointer;
}
.rules-error-details summary:focus-visible {
  outline: 2px solid var(--wb-blue);
  outline-offset: 3px;
}
.dialog-description {
  margin: 0 0 20px;
  color: var(--wb-muted);
  font-size: 14px;
  line-height: 1.8;
}
.test-inputs-heading {
  margin: 24px 0 18px;
  padding-top: 20px;
  border-top: 1px solid var(--wb-line);
  color: var(--wb-ink);
  font-size: 16px;
  font-weight: 500;
}
.rule-test-form :deep(.el-form-item__label) {
  color: var(--wb-ink);
}
.result-value,
.result-status {
  color: var(--wb-ink);
  font-size: 15px;
  font-variant-numeric: tabular-nums;
}
.trace-content {
  max-height: 360px;
  overflow: auto;
  margin: 0;
  padding: 12px;
  border: 1px solid var(--wb-line);
  border-radius: 5px;
  background: var(--wb-tint);
  color: var(--wb-ink);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
@media (max-width: 1099px) {
  .rule-editor-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .policy-input-editor {
    border-right: 0 !important;
    border-bottom: 1px solid var(--wb-line) !important;
  }
}
@media (max-width: 699px) {
  .dsl-generator {
    gap: 20px;
  }
  .composer-heading,
  .rules-heading {
    align-items: flex-start;
    padding: 16px;
  }
  .generation-status {
    font-size: 12px;
  }
  .rule-editor-grid {
    margin: 0 12px;
  }
  .rule-editor-grid :deep(.editor-header) {
    flex-wrap: wrap;
    padding: 12px;
  }
  .rule-editor-grid :deep(.editor-footer) {
    padding: 12px;
  }
  .rule-editor-grid :deep(.editor-body),
  .rule-output-editor :deep(.el-empty) {
    min-height: 232px;
  }
  .policy-input-editor :deep(.el-textarea__inner) {
    min-height: 232px !important;
    height: 260px;
    font-size: 16px;
    line-height: 1.8;
  }
  .editor-footer-row {
    align-items: flex-start;
  }
  .editor-button-group {
    justify-content: flex-end;
    flex: 1 1 auto;
  }
  .editor-button-group .el-button {
    min-height: 40px;
    padding-right: 12px;
    padding-left: 12px;
  }
  .capability-note {
    padding: 12px 16px 16px;
  }
  .policy-example {
    margin-right: 12px;
    margin-left: 12px;
  }
  .rules-toolbar {
    width: 100%;
  }
  .rules-toolbar :deep(.search-bar) {
    flex: 1;
    min-width: 0;
    width: auto;
  }
  .rules-footer {
    padding: 14px 16px;
  }
  .rules-load-error {
    align-items: flex-start;
    flex-wrap: wrap;
    padding: 20px 16px;
  }
}
</style>
