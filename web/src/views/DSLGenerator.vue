<template>
  <div class="workspace-module dsl-generator">
    <header class="dsl-page-heading"><h1>规则管理</h1><p>依据政策原文编制规则，核对条件与计算结果</p></header>
    <div class="rule-workspace">
    <section class="rule-composer" aria-labelledby="rule-composer-heading">
      <header class="composer-heading">
        <div>
          <h2 id="rule-composer-heading">规则编制</h2>
        </div>
        <div class="composer-actions">
          <span class="generation-status" :class="{ 'is-ready': appStore.hasGeneratedDSL && !appStore.dslState.generating }" role="status" :aria-busy="appStore.dslState.generating">
            <el-icon v-if="appStore.dslState.generating" class="is-loading"><Loading /></el-icon>
            <el-icon v-else-if="appStore.hasGeneratedDSL"><DocumentChecked /></el-icon>
            <span>{{ appStore.dslState.generating ? '正在生成' : appStore.hasGeneratedDSL ? '已生成 · 请核对' : '等待输入' }}</span>
          </span>
          <el-button type="primary" plain :icon="FolderChecked" :loading="saving" :disabled="!canSaveDSL" @click="saveDSL">{{ isCurrentRuleSaved ? '已保存' : '保存规则' }}</el-button>
        </div>
      </header>

      <p v-if="generationError || saveError" class="rule-operation-error" role="alert">{{ generationError || saveError }}</p>

      <div class="rule-editor-grid">
        <RuleEditorLayout v-model="editorTab" :has-rule="appStore.hasGeneratedDSL">
          <template #source>
            <CodeEditor
              id="policy-source-panel"
              v-model="appStore.dslState.inputText"
              class="policy-input-editor"
              title="政策原文"
              mode="input"
              :show-header="false"
              :rows="10"
              :disabled="appStore.dslState.generating"
              placeholder="请粘贴完整政策条款作为生成依据，保留适用对象、条件、标准和有效期限。"
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
              :empty-text="appStore.dslState.generating ? '正在解析政策条款，请稍候…' : '生成后，结构化规则将在这里显示'"
              :aria-busy="appStore.dslState.generating"
            >
              <template #title>
                <span class="editor-note">结构化规则 · YAML</span>
              </template>
              <template #footer>
                <div class="editor-footer-row">
                  <span class="editor-note">{{ isCurrentRuleSaved ? '当前版本已保存' : appStore.hasGeneratedDSL ? '可先试算，核对后再保存' : '生成后可试算与保存' }}</span>
                  <div class="editor-button-group">
                    <el-button :disabled="!appStore.hasGeneratedDSL || appStore.dslState.generating" @click="testCurrentDSL">填写测试参数</el-button>
                  </div>
                </div>
              </template>
            </CodeEditor>
          </template>
        </RuleEditorLayout>
      </div>
    </section>
        <section ref="testPanelRef" class="rule-test-panel" aria-labelledby="rule-test-heading" :aria-busy="testing || testPanelLoading">
          <header class="test-panel-heading"><h2 id="rule-test-heading">条件试算</h2><span>核对执行结果</span></header>
          <div class="test-panel-body">
            <p v-if="testPanelLoading" class="test-placeholder" role="status">正在读取规则与测试参数…</p>
            <template v-else-if="testForm.ruleId">
              <div class="test-rule-identity"><strong>{{ testContext }}</strong><span>{{ testForm.ruleId }}</span></div>
              <p v-if="testOrigin === 'generated'" class="test-draft-note">试算当前生成版本，核对后可保存规则。</p>
              <el-form :model="testForm" label-position="top" class="rule-test-form" @submit.prevent="executeTest">
                <div class="test-fields">
                  <el-form-item v-for="input in testInputSpecs" :key="input.name" :label="formatParamLabel(input.name)">
                    <el-input-number v-if="['float', 'number', 'int', 'integer'].includes(input.type)" v-model="testForm.inputs[input.name]" :controls="false" :step-strictly="['int', 'integer'].includes(input.type)" :disabled="testing" :placeholder="`请输入${formatParamLabel(input.name)}`" :aria-label="formatParamLabel(input.name)" />
                    <el-select v-else-if="['bool', 'boolean'].includes(input.type)" v-model="testForm.inputs[input.name]" :disabled="testing" clearable placeholder="请选择" :aria-label="formatParamLabel(input.name)"><el-option label="是" :value="true" /><el-option label="否" :value="false" /></el-select>
                    <el-input v-else v-model="testForm.inputs[input.name]" :disabled="testing" :placeholder="`请输入${formatParamLabel(input.name)}`" :aria-label="formatParamLabel(input.name)" />
                  </el-form-item>
                </div>
                <p v-if="Object.keys(testForm.inputs).length === 0" class="test-placeholder">此规则没有需要填写的输入参数。</p>
                <el-button native-type="submit" type="primary" plain :loading="testing" :disabled="!canExecuteTest" class="run-test-button">执行试算</el-button>
              </el-form>
            </template>
            <div v-else class="test-placeholder test-empty-state">
              <div><strong>先生成规则，再核对条件</strong><p>试算可在保存前进行，也可选择下方已保存的规则。</p></div>
              <ol class="test-steps">
                <li><span aria-hidden="true">1</span><div><strong>生成规则</strong><p>从政策条款提取条件与计算逻辑</p></div></li>
                <li><span aria-hidden="true">2</span><div><strong>填写实际条件</strong><p>按规则提供数字、文本或是非值</p><div class="test-input-shapes" aria-hidden="true"><i>数字</i><i>文本</i><i>是 / 否</i></div></div></li>
                <li><span aria-hidden="true">3</span><div><strong>核对执行结果</strong><p>查看执行状态、原始返回值与计算过程</p></div></li>
              </ol>
            </div>
            <p v-if="testError" class="test-error" role="alert">{{ testError }}</p>
            <p v-if="testResultStale" class="test-result-stale" role="status">参数或规则已改变，请重新执行测试。</p>
            <section v-if="testResult" class="test-result" aria-labelledby="test-result-heading" aria-live="polite">
              <h4 id="test-result-heading">测试结果</h4>
              <dl><div><dt>执行状态</dt><dd>{{ testStatusText }}</dd></div><div v-if="testResult.final_result != null"><dt>原始返回值</dt><dd class="result-value">{{ testResult.final_result }}</dd></div></dl>
              <p v-if="testResult.final_result != null" class="test-result-note">按接口原样展示，含义与单位请结合规则和执行跟踪核对。</p>
              <p v-if="testResult.message" class="test-result-message">{{ testResult.message }}</p>
              <ul v-if="Array.isArray(testResult.errors) && testResult.errors.length" class="test-result-errors"><li v-for="(error, index) in testResult.errors" :key="index">{{ error }}</li></ul>
              <details v-if="testResult.explainability_trace?.length || testResult.trace"><summary>执行跟踪</summary><pre class="trace-content">{{ testResult.explainability_trace?.length ? JSON.stringify(testResult.explainability_trace, null, 2) : testResult.trace }}</pre></details>
              <details><summary>完整返回结果</summary><pre class="trace-content">{{ JSON.stringify(testResult, null, 2) }}</pre></details>
            </section>
          </div>
        </section>
    </div>

    <section class="saved-rules" aria-labelledby="saved-rules-heading">
      <header class="rules-heading">
        <div class="rules-heading-label"><h2 id="saved-rules-heading">已保存的规则</h2><span v-if="!tableLoading && !listError">{{ appStore.dslState.dslList.length }} 条</span></div>
        <div class="rules-toolbar">
          <SearchBar v-model="searchQuery" placeholder="搜索规则名称或 ID" :disabled="tableLoading || !!listError" :show-button="false" :debounce="300" @input="filterRules" />
          <el-tooltip v-if="!listError" content="刷新规则列表" placement="top">
            <el-button :icon="Refresh" :disabled="tableLoading" aria-label="刷新规则列表" @click="loadDSLList" />
          </el-tooltip>
        </div>
      </header>
      <UnavailableState v-if="listError && !tableLoading" class="rules-unavailable" title="规则列表加载失败" description="暂时无法读取规则列表，请稍后重试。" :detail="listError" @retry="loadDSLList" />
      <div v-else class="rules-table-wrap">
        <el-table :data="filteredRules" class="rules-table" :aria-busy="tableLoading">
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
          <template #empty>
            <div v-if="tableLoading" class="rules-skeleton" role="status" aria-label="正在读取规则列表">
              <el-skeleton :animated="false">
                <template #template><div v-for="row in 3" :key="row" class="rules-skeleton-row"><el-skeleton-item v-for="column in 6" :key="column" variant="text" /></div></template>
              </el-skeleton>
            </div>
            <div v-else class="rules-empty"><strong>{{ searchQuery ? '未找到匹配规则' : '暂无已保存的规则' }}</strong><span>{{ searchQuery ? '换个名称或规则 ID 试试' : '在上方生成并核对规则后，保存到规则库' }}</span></div>
          </template>
        </el-table>
      </div>
      <footer v-if="!listError && (!tableLoading || appStore.dslState.dslList.length)" class="rules-footer">
        <span>{{ tableLoading ? '正在更新规则列表…' : searchQuery ? `匹配 ${matchingRules.length} 条规则` : '选择规则可查看内容或填写测试参数' }}</span>
        <el-pagination v-if="!tableLoading && !listError && matchingRules.length > pageSize" v-model:current-page="currentPage" :page-size="pageSize" :total="matchingRules.length" layout="total, prev, pager, next" />
      </footer>
    </section>

    <el-dialog v-model="showDetailDialog" title="规则详情" width="800px" class="glyph-dialog dsl-detail-dialog">
      <CodeEditor v-model="currentRuleDetail" class="rule-detail-editor" title="结构化规则内容" mode="display" language="json" :show-copy="true" />
      <template #footer><el-button @click="showDetailDialog = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useAppStore } from '@/stores/app'
import { dslApi } from '@/api'
import { CodeEditor, SearchBar } from '@/components'
import UnavailableState from '@/components/UnavailableState.vue'
import RuleEditorLayout from '@/components/rules/RuleEditorLayout.vue'
import { DocumentChecked, FolderChecked, Loading, MagicStick, Refresh } from '@element-plus/icons-vue'

// Store
const appStore = useAppStore()

// Refs
const searchQuery = ref('')
const editorTab = ref(appStore.hasGeneratedDSL ? 'rule' : 'source')
const currentPage = ref(1)
const pageSize = ref(10)
const tableLoading = ref(false)
const listError = ref('')
const saving = ref(false)
const showDetailDialog = ref(false)
const testing = ref(false)
const currentRuleDetail = ref('')
const testPanelRef = ref(null)
const testPanelLoading = ref(false)
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
const testStatusText = computed(() => {
  const status = testResult.value?.status
  return ({ VALID: '执行完成', QUALIFIED: '符合规则条件', NOT_QUALIFIED: '不符合规则条件', EXPIRED: '政策不在适用期', INVALID_INPUT: '输入未通过校验', ERROR: '执行出错' })[status] || status || '未返回状态'
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
  testPanelLoading.value = true
  testError.value = ''
  testResult.value = null
  testPanelRef.value?.scrollIntoView({ block: 'nearest' })
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
  testPanelRef.value?.scrollIntoView({ block: 'nearest' })
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
  gap: 20px;
  min-width: 0;
  min-height: 100%;
}
.dsl-page-heading {
  display: grid;
  gap: 4px;
}
.dsl-page-heading h1 {
  margin: 0;
  color: var(--wb-ink);
  font-size: var(--wb-title-size);
  line-height: 32px;
}
.dsl-page-heading p {
  margin: 0;
  color: var(--wb-muted);
  font-size: 13px;
  line-height: 1.8;
}
.rule-workspace {
  display: grid;
  flex: none;
  grid-template-columns: minmax(0, 1.95fr) minmax(320px, 1fr);
  align-items: stretch;
  gap: 24px;
  min-width: 0;
}
.rule-composer,
.saved-rules,
.rule-test-panel {
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
  flex: 1;
  flex-direction: column;
  min-height: 260px;
}
.composer-heading,
.rules-heading {
  display: flex;
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
.composer-heading p {
  margin: 5px 0 0;
  color: var(--wb-muted);
  font-size: var(--wb-text-size);
  line-height: 1.7;
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
  --rule-editor-height: clamp(280px, 34vh, 360px);
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
.rule-editor-grid :deep(.editor-header),
.test-panel-heading {
  min-height: 54px;
  gap: 8px;
  padding: 12px 22px;
  background: var(--wb-surface);
  border-bottom: 1px solid var(--wb-line);
}
.rule-editor-grid :deep(.editor-body) {
  flex: 1;
  min-height: var(--rule-editor-height);
  background: var(--wb-surface);
}
.policy-input-editor :deep(.el-textarea__inner) {
  min-height: var(--rule-editor-height) !important;
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
  height: var(--rule-editor-height);
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
.rule-output-editor :deep(.el-empty) {
  min-height: var(--rule-editor-height);
  padding: 36px 20px;
}
.rule-output-editor :deep(.el-empty__image) {
  display: none;
}
.rule-output-editor :deep(.el-empty__description p) {
  font-size: var(--wb-text-size);
  line-height: 1.8;
}
.rule-editor-grid :deep(.editor-footer) {
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
.rules-heading-label,
.rules-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.rules-heading-label > span {
  color: var(--wb-muted);
  font: var(--wb-text-size) var(--wb-number);
}
.rules-toolbar :deep(.search-bar) {
  width: 240px;
}
.rules-table-wrap {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  max-width: 100%;
  overflow-x: auto;
  border-top: 1px solid var(--wb-line);
}
.rules-table {
  flex: 1;
  width: 100%;
  min-width: 820px;
}
.rules-table :deep(.el-table__empty-block) {
  min-height: 144px;
  align-items: flex-start;
}
.rules-table :deep(.el-table__empty-text) {
  width: 100%;
  line-height: 1.8;
}
.rules-skeleton-row {
  display: grid;
  grid-template-columns: minmax(210px, 1fr) minmax(190px, 1fr) 110px 100px 168px 130px;
  align-items: center;
  min-height: 48px;
  border-bottom: 1px solid var(--wb-line);
}
.rules-skeleton-row :deep(.el-skeleton__item) {
  width: calc(100% - 24px);
  height: 12px;
  margin: 0 12px;
}
.rules-skeleton-row :deep(.el-skeleton__item:first-child) {
  width: calc(100% - 34px);
  margin-left: 22px;
}
.rules-table :deep(.el-table__cell:first-child .cell) {
  padding-left: 22px;
}
.rule-id {
  color: var(--wb-muted);
  font-family: var(--font-mono);
  font-size: var(--wb-text-size);
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
  font-size: var(--wb-text-size);
  font-weight: 500;
}
.rules-empty span {
  color: var(--wb-muted);
  font-size: var(--wb-text-size);
}
.rules-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  padding: 14px 22px;
  color: var(--wb-muted);
  font-size: var(--wb-text-size);
}
.rules-unavailable {
  flex: 1;
  border-top: 1px solid var(--wb-line);
}
.rule-test-form :deep(.el-form-item__label) {
  color: var(--wb-ink);
}
.result-value {
  color: var(--wb-ink);
  font: 500 32px/1.5 var(--wb-number);
  font-variant-numeric: tabular-nums;
}
.trace-content {
  max-height: 240px;
  overflow: auto;
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
.rule-test-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--wb-surface);
}
.test-panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.test-panel-heading h2 {
  margin: 0;
  color: var(--wb-ink);
  font-size: var(--wb-text-size);
  font-weight: 500;
}
.test-panel-heading > span {
  color: var(--wb-muted);
  font-size: 12px;
}
.test-panel-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  padding: 22px;
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
.test-placeholder p {
  margin: 0;
}
.test-placeholder p + p {
  margin-top: 10px;
}
.test-empty-state {
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: flex-start;
  gap: 20px;
  margin: 0;
  padding: 0;
}
.test-empty-state strong {
  color: var(--wb-ink);
  font-size: 14px;
  font-weight: 500;
}
.test-empty-state > div > p {
  margin-top: 8px;
  font-size: 12.5px;
  line-height: 1.75;
}
.test-steps {
  display: grid;
  gap: 20px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.test-steps li {
  position: relative;
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}
.test-steps li:not(:last-child)::after {
  position: absolute;
  top: 26px;
  bottom: -16px;
  left: 10px;
  border-left: 1px dashed var(--wb-line);
  content: '';
}
.test-steps li > span {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border: 1px solid var(--wb-line);
  border-radius: 50%;
  background: var(--wb-tint);
  color: var(--wb-muted);
  font-family: var(--wb-number);
  font-size: 12px;
}
.test-steps p {
  margin: 4px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
}
.test-input-shapes {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.test-input-shapes i {
  padding: 2px 9px;
  border: 1px solid var(--wb-line);
  border-radius: 4px;
  background: var(--wb-tint);
  font-size: 12px;
  font-style: normal;
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
.run-test-button {
  width: 100%;
}
.test-result {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--wb-line);
}
.test-result h4 {
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
@media (min-width: 1536px) {
  .rule-workspace {
    grid-template-columns: minmax(0, 2.7fr) minmax(300px, 1fr);
  }
}
@media (max-width: 1099px) {
  .rule-workspace {
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
  }
  .rule-composer {
    min-height: 0;
  }
  .test-fields {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0 20px;
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
  .rule-editor-grid :deep(.editor-body),
  .rule-output-editor :deep(.el-empty) {
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
  .test-panel-body {
    padding: 16px;
  }
  .test-panel-heading {
    padding-right: 16px;
    padding-left: 16px;
  }
  .test-fields {
    grid-template-columns: minmax(0, 1fr);
  }
  .rule-operation-error {
    margin-right: 16px;
    margin-left: 16px;
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
}
</style>
