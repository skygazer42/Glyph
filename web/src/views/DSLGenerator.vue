<template>
  <div class="dsl-generator">
    <el-card class="page-card">
      <template #header>
        <div class="page-header">
          <h2 class="page-title">DSL 规则生成器</h2>
          <div class="page-actions">
            <el-button @click="showExamples = !showExamples">
              {{ showExamples ? '隐藏示例' : '查看示例' }}
            </el-button>
            <el-button type="primary" @click="showBatchDialog = true">
              批量生成
            </el-button>
          </div>
        </div>
      </template>

      <!-- 示例展示 -->
      <el-collapse-transition>
        <el-alert
          v-show="showExamples"
          type="info"
          :closable="false"
          style="margin-bottom: 20px"
        >
          <template #title>
            <div class="example-header">
              <span>政策文本示例</span>
              <el-button size="small" @click="useExample">使用此示例</el-button>
            </div>
          </template>
          <pre class="example-content">{{ exampleText }}</pre>
        </el-alert>
      </el-collapse-transition>

      <!-- 主要内容区 -->
      <el-row :gutter="20">
        <!-- 输入区域 -->
        <el-col :span="12">
          <CodeEditor
            v-model="appStore.dslState.inputText"
            title="输入政策文本"
            mode="input"
            :rows="20"
            placeholder="请输入或粘贴政策文档内容..."
          >
            <template #actions>
              <el-button size="small" @click="clearInput">清空</el-button>
            </template>
            <template #footer>
              <div class="editor-actions">
                <FileUploader
                  :upload-url="'/api/dsl/upload'"
                  :multiple="false"
                  :accept="'.txt,.docx,.pdf'"
                  :drag="false"
                  :show-file-list="false"
                  button-text="上传文档"
                  @success="handleFileUpload"
                />
                <el-button
                  type="primary"
                  :loading="appStore.dslState.generating"
                  @click="generateDSL"
                  :disabled="!appStore.dslState.inputText"
                >
                  生成 DSL
                </el-button>
              </div>
            </template>
          </CodeEditor>
        </el-col>

        <!-- 输出区域 -->
        <el-col :span="12">
          <CodeEditor
            v-model="appStore.dslState.generatedYAML"
            title="生成的 DSL 规则"
            mode="display"
            language="yaml"
            :show-copy="true"
            empty-text="生成的 DSL 规则将显示在这里"
          >
            <template #footer v-if="appStore.hasGeneratedDSL">
              <div class="editor-actions">
                <el-button @click="testCurrentDSL">测试规则</el-button>
                <el-button type="success" @click="saveDSL">保存规则</el-button>
              </div>
            </template>
          </CodeEditor>
        </el-col>
      </el-row>

      <!-- DSL 规则列表 -->
      <el-card shadow="never" style="margin-top: 20px">
        <template #header>
          <div class="card-header">
            <h3>已保存的规则</h3>
            <div class="header-actions">
              <SearchBar
                v-model="searchQuery"
                placeholder="搜索规则..."
                :show-button="false"
                :debounce="300"
                @input="filterRules"
                size="small"
              />
              <el-button size="small" @click="loadDSLList">
                刷新
              </el-button>
            </div>
          </div>
        </template>

        <el-table
          :data="filteredRules"
          style="width: 100%"
          v-loading="tableLoading"
        >
          <el-table-column prop="rule_id" label="规则 ID" width="200" />
          <el-table-column prop="title" label="标题" show-overflow-tooltip />
          <el-table-column prop="doc_type" label="文档类型" width="120">
            <template #default="scope">
              <el-tag size="small">{{ scope.row.doc_type || '通用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #default="scope">
              <el-tag
                :type="scope.row.is_active ? 'success' : 'info'"
                size="small"
              >
                {{ scope.row.is_active ? '已激活' : '未激活' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="180">
            <template #default="scope">
              {{ formatDate(scope.row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="scope">
              <el-button-group size="small">
                <el-button @click="viewRule(scope.row)">查看</el-button>
                <el-button @click="editRule(scope.row)">编辑</el-button>
                <el-button type="primary" @click="testRule(scope.row)">
                  测试
                </el-button>
                <el-button type="danger" @click="deleteRule(scope.row)">
                  删除
                </el-button>
              </el-button-group>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <el-pagination
          v-if="appStore.dslState.dslList.length > pageSize"
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="appStore.dslState.dslList.length"
          layout="total, prev, pager, next"
          style="margin-top: 20px; justify-content: center"
        />
      </el-card>
    </el-card>

    <!-- 测试对话框 -->
    <el-dialog v-model="showTestDialog" title="测试 DSL 规则" width="700px">
      <el-form :model="testForm" label-width="120px">
        <el-form-item label="规则 ID">
          <el-input v-model="testForm.ruleId" disabled />
        </el-form-item>

        <el-divider>输入参数</el-divider>

        <el-form-item
          v-for="(value, key) in testForm.inputs"
          :key="key"
          :label="formatParamLabel(key)"
        >
          <el-input
            v-model="testForm.inputs[key]"
            :placeholder="`请输入${formatParamLabel(key)}`"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showTestDialog = false">取消</el-button>
        <el-button type="primary" @click="executeTest" :loading="testing">
          执行测试
        </el-button>
      </template>
    </el-dialog>

    <!-- 测试结果对话框 -->
    <el-dialog v-model="showResultDialog" title="测试结果" width="700px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="执行状态">
          <el-tag
            :type="testResult.status === 'QUALIFIED' ? 'success' : 'danger'"
            size="large"
          >
            {{ testResult.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="最终结果">
          <span class="result-value">{{ testResult.final_result }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="执行跟踪" v-if="testResult.trace">
          <pre class="trace-content">{{ testResult.trace }}</pre>
        </el-descriptions-item>
      </el-descriptions>

      <template #footer>
        <el-button type="primary" @click="showResultDialog = false">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量生成对话框 -->
    <el-dialog v-model="showBatchDialog" title="批量生成 DSL" width="600px">
      <FileUploader
        ref="batchUploader"
        :upload-url="'/api/dsl/batch-upload'"
        :multiple="true"
        :limit="10"
        :accept="'.txt,.docx,.pdf'"
        :show-custom-list="true"
        tip-text="支持上传多个文档，每个文档将生成一个独立的 DSL 规则"
        @success="handleBatchUpload"
      />

      <template #footer>
        <el-button @click="showBatchDialog = false">取消</el-button>
        <el-button
          type="primary"
          @click="executeBatchGenerate"
          :loading="batchGenerating"
        >
          批量生成
        </el-button>
      </template>
    </el-dialog>

    <!-- 规则详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="规则详情" width="800px">
      <CodeEditor
        v-model="currentRuleDetail"
        mode="display"
        language="yaml"
        :show-copy="true"
      />
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { dslApi } from '@/api'
import { CodeEditor, FileUploader, SearchBar } from '@/components'

// Store
const appStore = useAppStore()

// Refs
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const tableLoading = ref(false)
const showExamples = ref(false)
const showTestDialog = ref(false)
const showResultDialog = ref(false)
const showBatchDialog = ref(false)
const showDetailDialog = ref(false)
const testing = ref(false)
const batchGenerating = ref(false)
const batchUploader = ref(null)
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
适用于全市���与活动的餐饮、零售、文旅等商户。

三、发放时间
2025年1月1日至2025年3月31日

四、使用规则
1. 每人每日限用1张消费券
2. 消费券不可叠加使用
3. 消费券不可兑换现金`

// Computed
const filteredRules = computed(() => {
  let rules = appStore.dslState.dslList

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    rules = rules.filter(rule =>
      rule.rule_id.toLowerCase().includes(query) ||
      rule.title.toLowerCase().includes(query)
    )
  }

  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return rules.slice(start, end)
})

// Methods
const useExample = () => {
  appStore.dslState.inputText = exampleText
  showExamples.value = false
  appStore.showNotification('success', '示例已加载')
}

const clearInput = () => {
  appStore.resetDSLState()
}

const generateDSL = async () => {
  if (!appStore.dslState.inputText.trim()) {
    appStore.showNotification('warning', '请输入政策文本')
    return
  }

  appStore.dslState.generating = true
  try {
    const response = await dslApi.generateFromText(
      appStore.dslState.inputText,
      {
        source: 'manual_input',
        generated_at: new Date().toISOString()
      }
    )

    appStore.dslState.generatedYAML = response.yaml_content
    testForm.value.ruleId = response.dsl_data.rule_id

    // Prepare test inputs
    testForm.value.inputs = {}
    if (response.dsl_data.inputs) {
      response.dsl_data.inputs.forEach(input => {
        testForm.value.inputs[input.name] = ''
      })
    }

    appStore.showNotification('success', 'DSL 规则生成成功')
  } catch (error) {
    appStore.showNotification('error', `生成失败: ${error.message}`)
  } finally {
    appStore.dslState.generating = false
  }
}

const saveDSL = async () => {
  if (!appStore.dslState.generatedYAML) {
    appStore.showNotification('warning', '没有可保存的 DSL 规则')
    return
  }

  try {
    await dslApi.saveDSL({
      rule_id: testForm.value.ruleId,
      yaml_content: appStore.dslState.generatedYAML
    })
    appStore.showNotification('success', 'DSL 规则保存成功')
    loadDSLList()
  } catch (error) {
    appStore.showNotification('error', `保存失败: ${error.message}`)
  }
}

const loadDSLList = async () => {
  tableLoading.value = true
  try {
    const response = await dslApi.listDSL()
    appStore.dslState.dslList = response.rules || []
  } catch (error) {
    appStore.showNotification('error', `加载列表失败: ${error.message}`)
  } finally {
    tableLoading.value = false
  }
}

const filterRules = () => {
  currentPage.value = 1
}

const viewRule = async (rule) => {
  try {
    const response = await dslApi.getDSL(rule.rule_id)
    currentRuleDetail.value = response.yaml_content
    showDetailDialog.value = true
  } catch (error) {
    appStore.showNotification('error', `查看失败: ${error.message}`)
  }
}

const editRule = (rule) => {
  // TODO: Implement edit functionality
  appStore.showNotification('info', '编辑功能开发中...')
}

const testRule = (rule) => {
  testForm.value.ruleId = rule.rule_id
  testForm.value.inputs = {}

  if (rule.inputs) {
    rule.inputs.forEach(input => {
      testForm.value.inputs[input.name] = ''
    })
  }

  showTestDialog.value = true
}

const testCurrentDSL = () => {
  if (!testForm.value.ruleId) {
    appStore.showNotification('warning', '请先生成 DSL 规则')
    return
  }
  showTestDialog.value = true
}

const deleteRule = async (rule) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除规则 "${rule.title}" 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await dslApi.deleteDSL(rule.rule_id)
    appStore.showNotification('success', '规则删除成功')
    loadDSLList()
  } catch (error) {
    if (error !== 'cancel') {
      appStore.showNotification('error', `删除失败: ${error.message}`)
    }
  }
}

const executeTest = async () => {
  testing.value = true
  try {
    const response = await dslApi.testDSL(
      testForm.value.ruleId,
      testForm.value.inputs
    )
    Object.assign(testResult.value, response.result)
    showTestDialog.value = false
    showResultDialog.value = true
  } catch (error) {
    appStore.showNotification('error', `测试失败: ${error.message}`)
  } finally {
    testing.value = false
  }
}

const handleFileUpload = (data) => {
  if (data.response && data.response.text) {
    appStore.dslState.inputText = data.response.text
    appStore.showNotification('success', '文档上传成功')
  }
}

const handleBatchUpload = (data) => {
  appStore.showNotification('success', `已上传 ${data.file.name}`)
}

const executeBatchGenerate = async () => {
  const files = batchUploader.value?.getFiles()
  if (!files || files.length === 0) {
    appStore.showNotification('warning', '请先上传文档')
    return
  }

  batchGenerating.value = true
  try {
    const documents = files.map(file => ({
      id: file.uid,
      name: file.name,
      content: file.response?.text || ''
    }))

    const response = await dslApi.batchGenerate(documents)
    appStore.showNotification(
      'success',
      `成功生成 ${response.success_count} 个规则`
    )

    showBatchDialog.value = false
    loadDSLList()
  } catch (error) {
    appStore.showNotification('error', `批量生成失败: ${error.message}`)
  } finally {
    batchGenerating.value = false
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
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
</script>

<style scoped>
.dsl-generator {
  animation: fadeIn 0.4s ease;
}

.page-card {
  background: white;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  border: none;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-title {
  margin: 0;
  font-size: var(--text-2xl);
  font-weight: 700;
  background: var(--primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.page-actions {
  display: flex;
  gap: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-actions :deep(.search-bar) {
  width: 300px;
}

.editor-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.example-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.example-content {
  margin: var(--spacing-md) 0 0 0;
  padding: var(--spacing-md);
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.6;
  white-space: pre-wrap;
}

.result-value {
  font-size: 16px;
  font-weight: 500;
  color: var(--el-color-success);
}

.trace-content {
  margin: 0;
  padding: var(--spacing-md);
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.5;
  max-height: 400px;
  overflow-y: auto;
}

/* Table styles */
:deep(.el-table) {
  font-size: var(--text-sm);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

:deep(.el-table th) {
  font-weight: 600;
  background: linear-gradient(to bottom, #f9fafb, #f3f4f6);
}

:deep(.el-table tbody tr):hover {
  background-color: rgba(102, 126, 234, 0.03) !important;
}

/* Responsive design */
@media (max-width: 1200px) {
  .el-row {
    flex-direction: column;
  }

  .el-col {
    max-width: 100%;
    flex: 1;
  }
}
</style>