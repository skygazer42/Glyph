<template>
  <div class="workspace-module dsl-generator">
    <h1 class="dsl-visually-hidden">规则管理</h1>
    <div class="rule-workspace">
      <section class="rule-composer" aria-labelledby="rule-composer-heading">
        <header class="composer-heading">
          <div>
            <h2 id="rule-composer-heading">规则编制</h2>
          </div>
          <div class="composer-actions">
            <span v-if="appStore.hasGeneratedDSL || appStore.dslState.generating" class="generation-status" :class="{ 'is-ready': appStore.hasGeneratedDSL && !appStore.dslState.generating }" role="status" :aria-busy="appStore.dslState.generating">
              <el-icon v-if="appStore.dslState.generating" class="is-loading"><Loading /></el-icon>
              <el-icon v-else-if="appStore.hasGeneratedDSL"><DocumentChecked /></el-icon>
              <span>{{ appStore.dslState.generating ? '正在生成' : '已生成 · 请核对' }}</span>
            </span>
            <el-button type="primary" plain :icon="FolderChecked" :loading="saving" :disabled="!canSaveDSL" @click="saveDSL">{{ isCurrentRuleSaved ? '已保存' : '保存规则' }}</el-button>
          </div>
        </header>

        <p v-if="generationError || saveError" class="rule-operation-error" role="alert">{{ generationError || saveError }}</p>

        <div class="rule-editor-grid">
          <RuleEditorLayout v-model="editorTab" :has-rule="appStore.hasGeneratedDSL">
            <template #source>
              <div class="policy-source-surface">
                <CodeEditor
                  id="policy-source-panel"
                  v-model="appStore.dslState.inputText"
                  class="policy-input-editor"
                  title="政策原文"
                  mode="input"
                  :show-header="false"
                  :rows="10"
                  :disabled="appStore.dslState.generating"
                >
                  <template #footer>
                    <div class="editor-footer-row">
                      <span class="editor-note">{{ inputCharacterCount.toLocaleString('zh-CN') }} 字</span>
                      <div class="editor-button-group">
                        <el-button :disabled="saving || (!appStore.dslState.inputText && !appStore.hasGeneratedDSL)" @click="clearInput">
                          {{ appStore.dslState.generating ? '取消并清空' : '清空' }}
                        </el-button>
                        <el-button type="primary" :loading="appStore.dslState.generating" :disabled="saving || inputCharacterCount === 0" @click="generateDSL">
                          <el-icon v-if="!appStore.dslState.generating"><MagicStick /></el-icon>
                          <span>生成规则</span>
                        </el-button>
                      </div>
                    </div>
                  </template>
                </CodeEditor>
                <div v-if="inputCharacterCount === 0" class="source-empty-state" aria-hidden="true">
                  <el-icon><Document /></el-icon>
                  <strong>粘贴政策原文</strong>
                  <p>保留适用对象、条件、补贴标准和有效期。</p>
                </div>
              </div>
            </template>
            <template #rule>
              <CodeEditor
                id="generated-rule-panel"
                v-model="appStore.dslState.generatedYAML"
                class="rule-output-editor"
                title="结构化规则"
                mode="display"
                language="yaml"
                :show-copy="true"
                :aria-busy="appStore.dslState.generating"
              >
                <template #empty>
                  <div class="rule-empty-state" role="status">
                    <el-icon><component :is="appStore.dslState.generating ? Loading : SetUp" :class="{ 'is-loading': appStore.dslState.generating }" /></el-icon>
                    <strong>{{ appStore.dslState.generating ? '正在提取规则' : '等待生成规则' }}</strong>
                    <p>{{ appStore.dslState.generating ? '正在解析适用条件与计算逻辑…' : '生成后，在这里对照原文核对条件与计算逻辑。' }}</p>
                  </div>
                </template>
                <template #title>
                  <span class="editor-note">结构化规则 · YAML</span>
                </template>
                <template #footer>
                  <div class="editor-footer-row">
                    <span v-if="appStore.hasGeneratedDSL" class="editor-note">{{ isCurrentRuleSaved ? '当前版本已保存' : '可先试算，核对后再保存' }}</span>
                    <div class="editor-button-group">
                      <el-button :disabled="!appStore.hasGeneratedDSL || appStore.dslState.generating" @click="testCurrentDSL">条件试算</el-button>
                    </div>
                  </div>
                </template>
              </CodeEditor>
            </template>
          </RuleEditorLayout>
        </div>
      </section>

      <section class="saved-rules" aria-labelledby="saved-rules-heading">
        <header class="rules-heading">
          <div class="rules-heading-label"><h2 id="saved-rules-heading">已保存的规则</h2><span v-if="!tableLoading && !listError">{{ appStore.dslState.dslList.length }} 条</span></div>
          <div class="rules-toolbar">
            <SearchBar v-model="searchQuery" placeholder="搜索规则名称或 ID" :disabled="tableLoading || !!listError" :show-button="false" />
            <el-tooltip v-if="!listError" content="刷新规则列表" placement="top">
              <el-button :icon="Refresh" :disabled="tableLoading" aria-label="刷新规则列表" @click="loadDSLList" />
            </el-tooltip>
          </div>
        </header>
        <UnavailableState v-if="listError && !tableLoading" class="rules-unavailable" title="规则列表加载失败" description="暂时无法读取规则列表，请稍后重试。" :detail="listError" @retry="loadDSLList" />
        <div v-else class="rules-body" :aria-busy="tableLoading">
          <ul v-if="filteredRules.length" class="rules-list" aria-labelledby="saved-rules-heading">
            <li
              v-for="rule in filteredRules"
              :key="rule.rule_id"
              class="rule-row"
              :class="{ 'is-testing': testOrigin === 'saved' && testForm.ruleId === rule.rule_id && !testPanelLoading }"
            >
              <div class="rule-row-heading">
                <h3 :title="rule.title">{{ rule.title }}</h3>
                <span class="rule-state" :class="{ 'is-active': rule.is_active }">
                  <i aria-hidden="true"></i>{{ rule.is_active ? '适用期内' : '不在适用期' }}
                </span>
              </div>
              <div class="rule-row-footer">
                <span class="rule-id" :title="rule.rule_id">{{ rule.rule_id }}</span>
                <div class="rule-row-actions">
                  <el-button link type="primary" :aria-label="`查看 ${rule.title}`" @click="viewRule(rule)">查看</el-button>
                  <el-button link type="primary" :aria-label="`测试 ${rule.title}`" @click="testRule(rule)">测试</el-button>
                </div>
              </div>
              <div v-if="rule.doc_type || rule.created_at" class="rule-meta">
                <span v-if="rule.doc_type">{{ rule.doc_type }}</span>
                <time v-if="rule.created_at" :datetime="rule.created_at">{{ formatDate(rule.created_at) }}</time>
              </div>
            </li>
          </ul>
          <div v-else-if="tableLoading" class="rules-skeleton" role="status" aria-label="正在读取规则列表">
            <el-skeleton :animated="false">
              <template #template>
                <div v-for="row in 3" :key="row" class="rules-skeleton-row">
                  <el-skeleton-item variant="text" />
                  <el-skeleton-item variant="text" />
                </div>
              </template>
            </el-skeleton>
          </div>
          <div v-else class="rules-empty" role="status">
            <strong>{{ searchQuery ? '未找到匹配规则' : '暂无已保存的规则' }}</strong>
            <span>{{ searchQuery ? '换个名称或规则 ID 试试' : '生成并核对规则后，即可保存到这里' }}</span>
          </div>
        </div>
        <footer v-if="!listError && (ruleListStatus || matchingRules.length > pageSize)" class="rules-footer">
          <span v-if="ruleListStatus" role="status">{{ ruleListStatus }}</span>
          <el-pagination v-if="matchingRules.length > pageSize" v-model:current-page="currentPage" :page-size="pageSize" :total="matchingRules.length" :pager-count="5" layout="prev, pager, next" aria-label="规则列表分页" />
        </footer>
      </section>
    </div>

    <el-dialog
      v-model="showTestDialog"
      title="条件试算"
      width="760px"
      class="glyph-dialog rule-test-dialog"
      :close-on-click-modal="false"
      align-center
    >
      <div class="test-rule-identity">
        <strong>{{ testContext }}</strong>
        <span v-if="testForm.ruleId">{{ testForm.ruleId }}</span>
      </div>
      <div :aria-busy="testing || testPanelLoading">
        <p v-if="testPanelLoading" class="test-placeholder" role="status">正在读取规则与测试参数…</p>
        <template v-else-if="testForm.ruleId">
          <p v-if="testOrigin === 'generated'" class="test-draft-note">试算当前生成版本，核对后可保存规则。</p>
          <el-form id="rule-test-form" :model="testForm" label-position="top" class="rule-test-form" @submit.prevent="executeTest">
            <div class="test-fields">
              <el-form-item
                v-for="input in testInputSpecs"
                :key="input.name"
                :label="input.label || formatParamLabel(input.name)"
              >
                <el-select
                  v-if="Array.isArray(input.options) && input.options.length > 0"
                  v-model="testForm.inputs[input.name]"
                  :disabled="testing"
                  clearable
                  placeholder="请选择"
                  :aria-label="input.label || formatParamLabel(input.name)"
                >
                  <el-option
                    v-for="option in input.options"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <el-input-number
                  v-else-if="['float', 'number', 'int', 'integer'].includes(input.type)"
                  v-model="testForm.inputs[input.name]"
                  :controls="false"
                  :step-strictly="['int', 'integer'].includes(input.type)"
                  :disabled="testing"
                  :placeholder="`请输入${input.label || formatParamLabel(input.name)}`"
                  :aria-label="input.label || formatParamLabel(input.name)"
                />
                <el-select
                  v-else-if="['bool', 'boolean'].includes(input.type)"
                  v-model="testForm.inputs[input.name]"
                  :disabled="testing"
                  clearable
                  placeholder="请选择"
                  :aria-label="input.label || formatParamLabel(input.name)"
                >
                  <el-option label="是" :value="true" />
                  <el-option label="否" :value="false" />
                </el-select>
                <el-input
                  v-else
                  v-model="testForm.inputs[input.name]"
                  :disabled="testing"
                  :placeholder="`请输入${input.label || formatParamLabel(input.name)}`"
                  :aria-label="input.label || formatParamLabel(input.name)"
                />
                <p v-if="input.description" class="test-placeholder">{{ input.description }}</p>
              </el-form-item>
            </div>
            <p v-if="Object.keys(testForm.inputs).length === 0" class="test-placeholder">此规则没有需要填写的输入参数。</p>
          </el-form>
        </template>
        <p v-if="testError" ref="testErrorRef" class="test-error" role="alert">{{ testError }}</p>
        <p v-if="testResultStale" class="test-result-stale" role="status">参数或规则已改变，请重新执行测试。</p>
        <section v-if="testResult" ref="testResultRef" class="test-result" aria-labelledby="test-result-heading" aria-live="polite">
          <h3 id="test-result-heading">试算结果</h3>
          <dl><div><dt>执行状态</dt><dd>{{ testStatusText }}</dd></div><div v-if="testHasAmount"><dt>原始返回值</dt><dd class="result-value">{{ testResult.final_result }}</dd></div></dl>
          <p v-if="testHasAmount" class="test-result-note">按接口原样展示，含义与单位请结合规则和执行跟踪核对。</p>
          <p v-else class="test-result-note">本次未得出金额，请根据执行状态和说明补充核验。</p>
          <p v-if="testResult.message" class="test-result-message">{{ testResult.message }}</p>
          <ul v-if="Array.isArray(testResult.errors) && testResult.errors.length" class="test-result-errors"><li v-for="(error, index) in testResult.errors" :key="index">{{ error }}</li></ul>
          <details v-if="testResult.explainability_trace?.length || testResult.trace"><summary>执行跟踪</summary><pre class="trace-content">{{ testResult.explainability_trace?.length ? JSON.stringify(testResult.explainability_trace, null, 2) : testResult.trace }}</pre></details>
          <details><summary>完整返回结果</summary><pre class="trace-content">{{ JSON.stringify(testResult, null, 2) }}</pre></details>
        </section>
      </div>
      <template #footer>
        <div class="test-dialog-footer">
          <el-button @click="showTestDialog = false">关闭</el-button>
          <el-button form="rule-test-form" native-type="submit" type="primary" :loading="testing" :disabled="!canExecuteTest">执行试算</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="showDetailDialog" title="规则详情" width="800px" class="glyph-dialog dsl-detail-dialog">
      <CodeEditor v-model="currentRuleDetail" class="rule-detail-editor" title="结构化规则内容" mode="display" language="json" :show-copy="true" />
      <template #footer><el-button @click="showDetailDialog = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { useAppStore } from '@/stores/app'
import { dslApi } from '@/api'
import { CodeEditor, SearchBar } from '@/components'
import UnavailableState from '@/components/UnavailableState.vue'
import RuleEditorLayout from '@/components/rules/RuleEditorLayout.vue'
import { Document, DocumentChecked, FolderChecked, Loading, MagicStick, Refresh, SetUp } from '@element-plus/icons-vue'

// Store
const appStore = useAppStore()

// Refs
const searchQuery = ref('')
const editorTab = ref(appStore.hasGeneratedDSL ? 'rule' : 'source')
const currentPage = ref(1)
const pageSize = 10
const tableLoading = ref(false)
const listError = ref('')
const saving = ref(false)
const showDetailDialog = ref(false)
const showTestDialog = ref(false)
const testing = ref(false)
const currentRuleDetail = ref('')
const testPanelLoading = ref(false)
const testResultRef = ref(null)
const testErrorRef = ref(null)
const testContext = ref('')
const testOrigin = ref('')
const testInputSpecs = ref([])
const failureDetail = (error, fallback) => typeof error.response?.data?.detail === 'string' ? error.response.data.detail : fallback
const generationError = ref('')
const saveError = ref('')
const testError = ref('')

// Test form
const testForm = ref({
  ruleId: '',
  inputs: {}
})

// Test result
const testResult = ref(null)
const testHasAmount = computed(() => ['VALID', 'QUALIFIED', 'SUCCESS', 'CALCULATED'].includes(testResult.value?.status) && testResult.value.final_result != null)
const testStatusText = computed(() => {
  const status = testResult.value?.status
  return ({
    VALID: '执行完成',
    QUALIFIED: '符合规则条件',
    CALCULATED: '金额测算完成（需审核）',
    INELIGIBLE: '不满足本次测算条件',
    NOT_QUALIFIED: '不符合规则条件',
    MANUAL_REVIEW: '需主管部门人工核实',
    SUSPENDED: '该业务当前暂停办理',
    NOT_IN_PERIOD: '不在本次业务受理时段',
    EXPIRED: '政策不在适用期',
    INVALID_INPUT: '输入未通过校验',
    ERROR: '执行出错'
  })[status] || status || '未返回状态'
})
const testResultStale = ref(false)

// Computed
const inputCharacterCount = computed(() => appStore.dslState.inputText.trim().length)
const isCurrentRuleSaved = computed(() => !!appStore.dslState.generatedRuleId && appStore.dslState.savedRule?.ruleId === appStore.dslState.generatedRuleId && appStore.dslState.savedRule?.yaml === appStore.dslState.generatedYAML)
const canSaveDSL = computed(() => appStore.hasGeneratedDSL && !!appStore.dslState.generatedRuleId && !appStore.dslState.generating && !saving.value && !isCurrentRuleSaved.value)
const canExecuteTest = computed(() => !!testForm.value.ruleId && !testPanelLoading.value && (testOrigin.value === 'saved' || (testOrigin.value === 'generated' && !appStore.dslState.generating && testForm.value.ruleId === appStore.dslState.generatedRuleId && appStore.hasGeneratedDSL)))
const testSignature = computed(() => JSON.stringify([testForm.value.ruleId, testForm.value.inputs, testOrigin.value, testOrigin.value === 'generated' ? appStore.dslState.generatedYAML : null]))
watch(testSignature, () => {
  if (testResult.value) {
    testResult.value = null
    testResultStale.value = true
  }
  testError.value = ''
})

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
  const start = (currentPage.value - 1) * pageSize
  const end = start + pageSize
  return matchingRules.value.slice(start, end)
})

const ruleListStatus = computed(() => {
  if (filteredRules.value.length === 0) return ''
  if (tableLoading.value) return '正在更新规则列表…'
  return searchQuery.value ? `匹配 ${matchingRules.value.length} 条规则` : ''
})

watch(searchQuery, () => {
  currentPage.value = 1
})

watch(matchingRules, rules => {
  const lastPage = Math.max(1, Math.ceil(rules.length / pageSize))
  currentPage.value = Math.min(currentPage.value, lastPage)
})

// Methods
let generationRequest = null
let listRequest = null
let detailRequest = null
let testRequest = null
let testFormRequest = null
let saveRequest = null

const clearInput = () => {
  generationRequest = null
  testRequest = null
  testFormRequest = null
  testing.value = false
  appStore.resetDSLState()
  editorTab.value = 'source'
  testForm.value.ruleId = ''
  testForm.value.inputs = {}
  testInputSpecs.value = []
  testResultStale.value = false
  testResult.value = null
  testError.value = ''
  generationError.value = ''
  saveError.value = ''
  testPanelLoading.value = false
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
  generationError.value = ''
  saveError.value = ''
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
    editorTab.value = 'rule'
    prepareTestForm(rule_id, inputs || [], 'generated', '当前生成的规则')
    appStore.showNotification('success', 'DSL 规则生成成功')
  } catch (error) {
    if (generationRequest !== request) {
      return
    }
    generationError.value = `生成失败：${failureDetail(error, '请求未完成，请稍后重试。')}`
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

  if (!canSaveDSL.value) {
    return
  }
  saving.value = true
  saveError.value = ''
  const request = {}
  saveRequest = request
  const ruleId = appStore.dslState.generatedRuleId
  const yamlContent = appStore.dslState.generatedYAML
  try {
    await dslApi.saveDSL({
      rule_id: ruleId,
      yaml_content: yamlContent
    })
    if (saveRequest !== request) {
      return
    }
    appStore.dslState.savedRule = { ruleId, yaml: yamlContent }
    if (testOrigin.value === 'saved' && testForm.value.ruleId === ruleId) {
      if (testResult.value || testing.value) testResultStale.value = true
      testRequest = null
      testing.value = false
      testResult.value = null
    }
    appStore.showNotification('success', 'DSL 规则保存成功')
    loadDSLList()
  } catch (error) {
    if (saveRequest === request) {
      saveError.value = `保存失败：${failureDetail(error, '请求未完成，请稍后重试。')}`
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
  const request = {}
  listRequest = request
  try {
    const response = await dslApi.listDSL()
    if (listRequest !== request) {
      return
    }
    appStore.dslState.dslList = response.rules || []
    listError.value = ''
  } catch (error) {
    if (listRequest !== request) {
      return
    }
    listError.value = failureDetail(error, error.message || '请检查连接后重试')
  } finally {
    if (listRequest === request) {
      tableLoading.value = false
    }
  }
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
  showTestDialog.value = true
  if (testOrigin.value === 'saved' && testForm.value.ruleId === rule.rule_id) return

  const request = {}
  testFormRequest = request
  testRequest = null
  testing.value = false
  testPanelLoading.value = true
  testContext.value = rule.title || rule.rule_id
  testForm.value = { ruleId: '', inputs: {} }
  testInputSpecs.value = []
  testResultStale.value = false
  testError.value = ''
  testResult.value = null
  try {
    const response = await dslApi.getDSL(rule.rule_id)
    if (testFormRequest !== request) {
      return
    }
    prepareTestForm(rule.rule_id, response.rule.inputs || [], 'saved', rule.title || rule.rule_id)
  } catch (error) {
    if (testFormRequest !== request) {
      return
    }
    testError.value = `加载测试参数失败：${error.message}`
  } finally {
    if (testFormRequest === request) testPanelLoading.value = false
  }
}

const prepareTestForm = (ruleId, inputs, origin, title) => {
  testFormRequest = null
  testPanelLoading.value = false
  testRequest = null
  testing.value = false
  testInputSpecs.value = inputs
  testForm.value = { ruleId, inputs: Object.fromEntries(inputs.map(input => [input.name, 'default' in input ? input.default : ['float', 'number', 'int', 'integer', 'bool', 'boolean'].includes(input.type) ? undefined : ''])) }
  testOrigin.value = origin
  testContext.value = title
  testResultStale.value = false
  testResult.value = null
  testError.value = ''
}

const testCurrentDSL = () => {
  if (!appStore.dslState.generatedRuleId) {
    appStore.showNotification('warning', '请先生成 DSL 规则')
    return
  }
  testFormRequest = null
  testPanelLoading.value = false
  if (testOrigin.value !== 'generated' || testForm.value.ruleId !== appStore.dslState.generatedRuleId) {
    prepareTestForm(appStore.dslState.generatedRuleId, appStore.dslState.generatedInputs, 'generated', '当前生成的规则')
  }
  showTestDialog.value = true
}

const executeTest = async () => {
  if (testing.value || !canExecuteTest.value) return
  testing.value = true
  testError.value = ''
  testResult.value = null
  testResultStale.value = false
  const request = {}
  testRequest = request
  const ruleId = testForm.value.ruleId
  const inputs = { ...testForm.value.inputs }
  const origin = testOrigin.value
  const yamlContent = appStore.dslState.generatedYAML
  const signature = testSignature.value
  try {
    const response = origin === 'generated'
      ? await dslApi.previewDSL(yamlContent, inputs)
      : await dslApi.testDSL(ruleId, inputs)
    if (testRequest !== request) {
      return
    }
    if (testSignature.value !== signature) {
      return
    }
    testResult.value = response.result
  } catch (error) {
    if (testRequest !== request || testSignature.value !== signature) {
      return
    }
    testError.value = `测试失败：${failureDetail(error, '请求未完成，请稍后重试。')}`
  } finally {
    if (testRequest === request) {
      testing.value = false
      await nextTick()
      if (showTestDialog.value && testSignature.value === signature) {
        const feedback = testError.value ? testErrorRef.value : testResultRef.value
        feedback?.scrollIntoView({ block: 'nearest' })
      }
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
    amount: '消费金额',
    consumption_amount: '消费金额',
    coupon_type: '消费券类型',
    claim_time: '领取时间',
    user_id: '用户 ID',
    merchant_id: '商户 ID',
    product_id: '商品 ID',
    using_other_coupon: '是否使用其他消费券',
    has_merchant_discount: '是否享受商家优惠'
  }
  return labels[key] || key
}

// Lifecycle
onMounted(() => {
  loadDSLList()
  if (appStore.hasGeneratedDSL) prepareTestForm(appStore.dslState.generatedRuleId, appStore.dslState.generatedInputs, 'generated', '当前生成的规则')
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
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  min-height: 0;
}
.dsl-visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.rule-workspace {
  display: grid;
  flex: 1;
  grid-template-columns: minmax(0, 1fr) clamp(336px, 29%, 408px);
  grid-template-rows: minmax(0, 1fr);
  gap: 20px;
  min-width: 0;
  min-height: 0;
}
.rule-composer,
.saved-rules {
  min-width: 0;
  border: 1px solid var(--wb-line);
  border-radius: var(--wb-radius);
  background: var(--wb-surface);
}
.rule-composer {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.saved-rules {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.composer-heading {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  min-height: 54px;
  padding: 12px 22px;
}
.composer-heading h2,
.rules-heading h2 {
  margin: 0;
  color: var(--wb-ink);
  font-size: var(--wb-text-size);
  font-weight: 500;
  line-height: 1.5;
}
.generation-status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 3px 9px;
  border-radius: 999px;
  color: var(--wb-muted);
  background: var(--wb-tint);
  font-size: 12px;
}
.generation-status.is-ready {
  padding: 3px 9px;
  border: 1px solid var(--wb-line);
  border-radius: 999px;
  background: var(--wb-blue-soft);
  white-space: nowrap;
}
.composer-heading {
  border-bottom: 1px solid var(--wb-line);
}
.composer-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}
.rule-editor-grid {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border-radius: 0 0 var(--wb-radius) var(--wb-radius);
}
.rule-editor-grid :deep(.code-editor) {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  border: 0;
  border-radius: 0;
}
.rule-editor-grid :deep(.editor-header) {
  min-height: 54px;
  gap: 8px;
  padding: 12px 22px;
  background: var(--wb-surface);
  border-bottom: 1px solid var(--wb-line);
}
.rule-editor-grid :deep(.editor-body) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: var(--wb-surface);
}
.policy-source-surface {
  position: relative;
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
}
.source-empty-state,
.rule-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
  color: var(--wb-muted);
  text-align: center;
}
.source-empty-state {
  position: absolute;
  inset: 0 0 64px;
  pointer-events: none;
}
.policy-source-surface:focus-within .source-empty-state {
  visibility: hidden;
}
.source-empty-state > .el-icon,
.rule-empty-state > .el-icon {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  margin-bottom: 2px;
  border: 1px solid var(--wb-line);
  border-radius: var(--wb-radius);
  background: var(--wb-tint);
  color: var(--wb-blue);
  font-size: 24px;
}
.source-empty-state strong,
.rule-empty-state strong {
  color: var(--wb-ink);
  font-size: 16px;
  font-weight: 500;
}
.source-empty-state p,
.rule-empty-state p {
  max-width: 280px;
  margin: 0;
  font-size: 13px;
  line-height: 1.8;
}
.rule-empty-state {
  flex: 1;
  min-height: 0;
}
.policy-input-editor :deep(.el-textarea__inner) {
  min-height: 0 !important;
  height: 100%;
  padding: 18px 22px;
  box-shadow: none;
  font-family: var(--wb-font);
  color: var(--wb-ink);
  font-size: 14px;
  line-height: 1.65;
  resize: none;
}
.policy-input-editor :deep(.editor-body) {
  display: flex;
}
.policy-input-editor :deep(.el-textarea) {
  display: flex;
  flex: 1;
}
.policy-input-editor :deep(.el-textarea__inner:focus) {
  box-shadow: inset 0 0 0 1px var(--wb-blue);
}
.rule-output-editor :deep(.code-display),
.rule-detail-editor :deep(.code-display) {
  max-height: 560px;
  background: var(--wb-surface);
  color: var(--wb-ink);
}
.rule-output-editor :deep(.code-display) {
  flex: 1;
  min-height: 0;
  max-height: none;
  padding: 18px 22px;
}
.rule-output-editor :deep(.code-display pre),
.rule-detail-editor :deep(.code-display pre) {
  color: var(--wb-ink);
  font-family: var(--font-mono);
  font-size: var(--wb-text-size);
  line-height: 1.85;
  white-space: pre;
  overflow-wrap: normal;
  word-break: normal;
}
.rule-output-editor :deep(.editor-body) {
  background: color-mix(in srgb, var(--wb-tint) 55%, var(--wb-surface));
}
.rule-editor-grid :deep(.editor-footer) {
  flex: none;
  padding: 14px 22px;
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
.rule-output-editor .editor-button-group {
  margin-left: auto;
}
.editor-note {
  color: var(--wb-muted);
  font-size: 13px;
  line-height: 1.7;
  font-variant-numeric: tabular-nums;
}
.editor-button-group .el-button {
  min-height: 34px;
}
.editor-button-group .el-icon + span {
  margin-left: 5px;
}
.rules-heading {
  display: grid;
  flex: none;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--wb-line);
}
.rules-heading-label {
  display: flex;
  align-items: center;
  gap: 10px;
}
.rules-heading-label > span {
  color: var(--wb-muted);
  font: 13px var(--wb-number);
}
.rules-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}
.rules-toolbar :deep(.search-bar) {
  min-width: 0;
}
.rules-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.rules-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
}
.rule-row {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 14px 16px 10px;
  box-shadow: inset 2px 0 transparent;
}
.rule-row + .rule-row,
.rules-skeleton-row + .rules-skeleton-row {
  border-top: 1px solid var(--wb-line);
}
.rule-row:focus-within {
  background: var(--wb-tint);
}
.rule-row.is-testing {
  background: var(--wb-blue-soft);
  box-shadow: inset 2px 0 var(--wb-blue);
}
.rule-row h3 {
  display: -webkit-box;
  min-width: 0;
  margin: 0;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  color: var(--wb-ink);
  font-size: var(--wb-text-size);
  font-weight: 500;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
.rule-row-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 10px;
}
.rules-skeleton-row {
  display: grid;
  align-content: center;
  gap: 8px;
  min-height: 84px;
  padding: 12px 16px;
}
.rules-skeleton-row :deep(.el-skeleton__item) {
  width: 58%;
  height: 10px;
}
.rules-skeleton-row :deep(.el-skeleton__item:first-child) {
  width: 78%;
  height: 13px;
}
.rule-id {
  min-width: 0;
  overflow: hidden;
  color: var(--wb-muted);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.rule-row-footer,
.rule-meta,
.rule-row-actions {
  display: flex;
  align-items: center;
}
.rule-row-footer {
  justify-content: space-between;
  gap: 10px;
}
.rule-meta {
  flex-wrap: wrap;
  gap: 2px 8px;
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 1.5;
  font-variant-numeric: tabular-nums;
}
.rule-row-actions {
  flex: none;
  gap: 6px;
  margin-left: auto;
}
.rule-row-actions .el-button {
  height: auto;
  padding: 4px 6px;
  border-radius: var(--wb-radius);
}
.rule-row-actions .el-button + .el-button {
  margin-left: 0;
}
.rule-row-actions .el-button:hover {
  background: var(--wb-blue-soft);
}
.rule-state {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--wb-tint);
  color: var(--wb-muted);
  font-size: 12px;
  line-height: 20px;
  white-space: nowrap;
}
.rule-state i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.rule-state.is-active {
  background: var(--wb-blue-soft);
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
  font-size: var(--wb-text-size);
  font-weight: 500;
}
.rules-empty span {
  color: var(--wb-muted);
  font-size: var(--wb-text-size);
}
.rules-footer {
  display: flex;
  flex: none;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px 12px;
  padding: 9px 16px;
  border-top: 1px solid var(--wb-line);
  color: var(--wb-muted);
  font-size: 13px;
}
.rules-footer > span {
  margin-right: auto;
}
.rules-unavailable {
  min-height: 180px;
}
.dsl-generator :deep(.rule-test-dialog) {
  display: flex;
  flex-direction: column;
  max-width: calc(100vw - 32px);
  max-height: calc(100dvh - 48px);
  padding: 0;
  overflow: hidden;
  font: var(--wb-text-size)/1.6 var(--wb-font);
}
.dsl-generator :deep(.rule-test-dialog .el-dialog__header) {
  flex: none;
  margin: 0;
  padding: 18px 24px;
  border-bottom: 1px solid var(--wb-line);
}
.dsl-generator :deep(.rule-test-dialog .el-dialog__title) {
  font-size: 18px;
}
.dsl-generator :deep(.rule-test-dialog .el-dialog__headerbtn) {
  top: 7px;
  right: 10px;
}
.dsl-generator :deep(.rule-test-dialog .el-dialog__body) {
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 24px;
}
.dsl-generator :deep(.rule-test-dialog .el-dialog__footer) {
  flex: none;
  padding: 16px 24px;
  border-top: 1px solid var(--wb-line);
}
.test-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.test-dialog-footer .el-button + .el-button {
  margin-left: 0;
}
.rule-test-form :deep(.el-input__wrapper),
.rule-test-form :deep(.el-select__wrapper) {
  min-height: var(--wb-control-height);
  background: var(--wb-surface);
  box-shadow: 0 0 0 1px var(--wb-border) inset;
}
.rule-test-form :deep(.el-input__wrapper.is-focus),
.rule-test-form :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px var(--wb-blue) inset;
}
.rule-test-form :deep(.el-form-item__label) {
  height: auto;
  color: var(--wb-ink);
  line-height: 1.6;
}
.result-value {
  color: var(--wb-ink);
  font: 500 32px/1.5 var(--wb-number);
  font-variant-numeric: tabular-nums;
}
.trace-content {
  overflow-x: auto;
  margin: 0;
  padding: 12px;
  border: 1px solid var(--wb-line);
  border-radius: var(--wb-radius);
  background: var(--wb-tint);
  color: var(--wb-ink);
  font-family: var(--font-mono);
  font-size: var(--wb-text-size);
  line-height: 1.8;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.test-rule-identity {
  display: grid;
  gap: 5px;
  margin-bottom: 20px;
  font-size: var(--wb-text-size);
  overflow-wrap: anywhere;
}
.test-rule-identity strong {
  font-weight: 500;
}
.test-rule-identity span {
  color: var(--wb-muted);
  font-family: var(--font-mono);
  font-size: 12px;
}
.test-placeholder,
.test-draft-note {
  margin: 0 0 20px;
  color: var(--wb-muted);
  font-size: var(--wb-text-size);
  line-height: 1.8;
}
.test-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 20px;
}
.test-result-stale {
  margin: 18px 0 0;
  padding: 10px 12px;
  color: var(--wb-muted);
  background: var(--wb-tint);
  border-left: 3px solid var(--wb-border);
  font-size: var(--wb-text-size);
  line-height: 1.8;
}
.rule-test-form :deep(.el-input-number),
.rule-test-form :deep(.el-select) {
  width: 100%;
}
.test-result {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--wb-line);
}
.test-result h3 {
  margin: 0 0 14px;
  font-size: var(--wb-text-size);
}
.test-result dl {
  display: grid;
  gap: 12px;
  margin: 0;
  font-size: var(--wb-text-size);
}
.test-result dl > div {
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr);
  align-items: baseline;
  gap: 12px;
}
.test-result dt {
  color: var(--wb-muted);
}
.test-result dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.test-result-message,
.test-result-errors {
  margin: 14px 0 0;
  font-size: var(--wb-text-size);
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.test-result-note { margin: 12px 0 0; color: var(--wb-muted); font-size: 12px; line-height: 1.8; }
.test-result-errors {
  padding-left: 20px;
  color: var(--wb-error);
}
.test-result details {
  margin-top: 16px;
}
.test-result summary {
  width: fit-content;
  margin-bottom: 10px;
  color: var(--wb-blue);
  cursor: pointer;
}
.test-result summary:focus-visible {
  outline: 2px solid var(--wb-blue);
  outline-offset: 3px;
}
.rule-operation-error,
.test-error {
  color: var(--wb-error);
  font-size: var(--wb-text-size);
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.rule-operation-error {
  margin: 14px 22px;
}
.test-error {
  margin: 16px 0 0;
}
@media (max-width: 1099px) {
  .dsl-generator {
    height: auto;
    min-height: 100%;
  }
  .rule-workspace {
    flex: none;
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto;
    align-items: start;
    gap: 20px;
  }
  .rule-composer {
    min-height: 540px;
  }
  .rule-editor-grid :deep(.editor-body) {
    min-height: 320px;
  }
  .policy-input-editor :deep(.el-textarea__inner) {
    min-height: 320px !important;
  }
  .rule-output-editor :deep(.code-display) {
    height: 320px;
    max-height: 320px;
  }
  .rules-body {
    overflow: visible;
  }
}
@media (max-width: 699px) {
  .dsl-generator {
    gap: 20px;
  }
  .composer-heading {
    align-items: flex-start;
    padding: 16px;
  }
  .generation-status {
    font-size: 12px;
  }
  .composer-heading {
    align-items: center;
    gap: 10px;
  }
  .composer-actions {
    gap: 10px;
  }
  .generation-status > .el-icon {
    display: none;
  }
  .rule-editor-grid :deep(.editor-header) {
    flex-wrap: wrap;
    padding: 12px 16px;
  }
  .rule-editor-grid :deep(.editor-footer) {
    padding: 12px 16px;
  }
  .rule-editor-grid :deep(.editor-body) {
    min-height: 280px;
  }
  .policy-input-editor :deep(.el-textarea__inner) {
    min-height: 280px !important;
    height: 300px;
    padding: 16px;
    font-size: 16px;
    line-height: 1.8;
  }
  .editor-footer-row {
    align-items: flex-start;
  }
  .rule-output-editor :deep(.code-display) {
    height: 300px;
    padding: 16px;
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
  .dsl-generator :deep(.rule-test-dialog) {
    max-height: calc(100dvh - 24px);
  }
  .dsl-generator :deep(.rule-test-dialog .el-dialog__header),
  .dsl-generator :deep(.rule-test-dialog .el-dialog__footer) {
    padding: 16px;
  }
  .dsl-generator :deep(.rule-test-dialog .el-dialog__body) {
    padding: 20px 16px;
  }
  .rule-test-form :deep(input),
  .rule-test-form :deep(.el-select__selected-item) {
    font-size: 16px;
  }
  .test-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .rule-operation-error {
    margin-right: 16px;
    margin-left: 16px;
  }
}
</style>
