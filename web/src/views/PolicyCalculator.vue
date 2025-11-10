<template>
  <div class="policy-calculator">
    <div class="calculator-container">
      <!-- 左侧 - 计算器 -->
      <el-card class="calculator-card">
        <template #header>
          <div class="card-header">
            <h2>🧮 政策补贴计算器</h2>
            <p>快速计算您可享受的补贴额度</p>
          </div>
        </template>

        <!-- 选择政策类型 -->
        <div class="policy-selector">
          <el-tabs v-model="selectedPolicyType" @tab-change="handlePolicyChange">
            <el-tab-pane label="🚗 汽车补贴" name="car" />
            <el-tab-pane label="🏠 家电补贴" name="appliance" />
            <el-tab-pane label="🎫 消费券" name="voucher" />
          </el-tabs>
        </div>

        <!-- 输入表单 -->
        <el-form
          ref="calculatorForm"
          :model="formData"
          :rules="formRules"
          label-width="120px"
          class="calculator-form"
        >
          <template v-if="selectedPolicyType === 'car'">
            <el-form-item label="车辆类型" prop="carType">
              <el-radio-group v-model="formData.carType">
                <el-radio label="new_energy">新能源汽车</el-radio>
                <el-radio label="fuel">燃油车</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="车辆价格" prop="price">
              <el-input v-model.number="formData.price" placeholder="请输入车辆价格">
                <template #append>元</template>
              </el-input>
            </el-form-item>
            <el-form-item label="能效等级" prop="energyLevel" v-if="formData.carType === 'new_energy'">
              <el-select v-model="formData.energyLevel" placeholder="请选择能效等级">
                <el-option label="一级" value="1" />
                <el-option label="二级" value="2" />
                <el-option label="三级" value="3" />
              </el-select>
            </el-form-item>
          </template>

          <template v-else-if="selectedPolicyType === 'appliance'">
            <el-form-item label="家电类型" prop="applianceType">
              <el-select v-model="formData.applianceType" placeholder="请选择家电类型">
                <el-option label="空调" value="air_conditioner" />
                <el-option label="冰箱" value="refrigerator" />
                <el-option label="洗衣机" value="washing_machine" />
                <el-option label="电视" value="tv" />
              </el-select>
            </el-form-item>
            <el-form-item label="购买价格" prop="price">
              <el-input v-model.number="formData.price" placeholder="请输入购买价格">
                <template #append>元</template>
              </el-input>
            </el-form-item>
            <el-form-item label="能效等级" prop="energyLevel">
              <el-select v-model="formData.energyLevel" placeholder="请选择能效等级">
                <el-option label="一级能效" value="1" />
                <el-option label="二级能效" value="2" />
                <el-option label="三级能效" value="3" />
              </el-select>
            </el-form-item>
            <el-form-item label="以旧换新" prop="tradeIn">
              <el-switch v-model="formData.tradeIn" />
            </el-form-item>
          </template>

          <template v-else-if="selectedPolicyType === 'voucher'">
            <el-form-item label="消费金额" prop="amount">
              <el-input v-model.number="formData.amount" placeholder="请输入消费金额">
                <template #append>元</template>
              </el-input>
            </el-form-item>
            <el-form-item label="消费类别" prop="category">
              <el-select v-model="formData.category" placeholder="请选择消费类别">
                <el-option label="餐饮消费" value="dining" />
                <el-option label="零售购物" value="retail" />
                <el-option label="文旅消费" value="culture" />
              </el-select>
            </el-form-item>
          </template>

          <el-form-item>
            <el-button
              type="primary"
              @click="calculate"
              :loading="calculating"
              size="large"
              style="width: 100%"
            >
              {{ calculating ? '计算中...' : '开始计算' }}
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 右侧 - 结果显示 -->
      <div class="result-section">
        <!-- 计算结果 -->
        <el-card v-if="calculationResult" class="result-card">
          <template #header>
            <div class="result-header">
              <h3>💰 计算结果</h3>
              <el-tag :type="calculationResult.status === 'QUALIFIED' ? 'success' : 'danger'" size="large">
                {{ calculationResult.status === 'QUALIFIED' ? '✅ 符合条件' : '❌ 不符合条件' }}
              </el-tag>
            </div>
          </template>

          <div class="result-content">
            <div class="subsidy-amount">
              <div class="amount-label">可获得补贴</div>
              <div class="amount-value">¥ {{ calculationResult.subsidy || 0 }}</div>
            </div>

            <el-divider />

            <div class="result-details">
              <h4>详细说明</h4>
              <div class="detail-item" v-if="calculationResult.trace">
                <pre class="trace-text">{{ calculationResult.trace }}</pre>
              </div>
            </div>

            <el-button type="primary" @click="saveCalculation" style="width: 100%; margin-top: 20px">
              保存计算记录
            </el-button>
          </div>
        </el-card>

        <!-- 空状态 -->
        <el-empty
          v-else
          description="请填写信息并点击"开始计算"查看结果"
          :image-size="200"
        />

        <!-- 历史记录 -->
        <el-card v-if="calculationHistory.length > 0" class="history-card">
          <template #header>
            <h3>📋 计算历史</h3>
          </template>
          <div class="history-list">
            <div
              v-for="(record, index) in calculationHistory"
              :key="index"
              class="history-item"
              @click="viewHistory(record)"
            >
              <div class="history-icon">{{ getPolicyIcon(record.policyType) }}</div>
              <div class="history-content">
                <div class="history-title">{{ getPolicyName(record.policyType) }}</div>
                <div class="history-time">{{ record.timestamp }}</div>
              </div>
              <div class="history-amount">¥{{ record.subsidy }}</div>
            </div>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { dslApi } from '@/api'

const selectedPolicyType = ref('car')
const calculating = ref(false)
const calculationResult = ref(null)
const calculationHistory = ref([])

const formData = reactive({
  carType: 'new_energy',
  applianceType: '',
  category: '',
  price: null,
  amount: null,
  energyLevel: '',
  tradeIn: false
})

const formRules = {
  price: [
    { required: true, message: '请输入价格', trigger: 'blur' },
    { type: 'number', message: '请输入有效的数字', trigger: 'blur' }
  ],
  amount: [
    { required: true, message: '请输入金额', trigger: 'blur' },
    { type: 'number', message: '请输入有效的数字', trigger: 'blur' }
  ]
}

const handlePolicyChange = () => {
  calculationResult.value = null
  Object.keys(formData).forEach(key => {
    if (key !== 'carType' && key !== 'applianceType' && key !== 'category') {
      formData[key] = key === 'tradeIn' ? false : key === 'energyLevel' ? '' : null
    }
  })
}

const calculate = async () => {
  calculating.value = true
  calculationResult.value = null

  try {
    // 构建测试参数
    const testParams = {}
    if (selectedPolicyType.value === 'car') {
      testParams.price = formData.price
      testParams.energy_level = formData.energyLevel
      testParams.category = formData.carType
    } else if (selectedPolicyType.value === 'appliance') {
      testParams.price = formData.price
      testParams.energy_level = formData.energyLevel
      testParams.category = formData.applianceType
    } else if (selectedPolicyType.value === 'voucher') {
      testParams.amount = formData.amount
      testParams.category = formData.category
    }

    // 调用DSL测试API（这里需要先知道rule_id，实际使用中可能需要先查询规则列表）
    const response = await dslApi.testDSL(`${selectedPolicyType.value}_policy`, testParams)

    calculationResult.value = {
      status: response.result.status,
      subsidy: response.result.final_result,
      trace: response.result.trace
    }

    ElMessage.success('计算完成')
  } catch (error) {
    ElMessage.error(`计算失败: ${error.message || '未知错误'}`)
  } finally {
    calculating.value = false
  }
}

const saveCalculation = () => {
  const record = {
    policyType: selectedPolicyType.value,
    subsidy: calculationResult.value.subsidy,
    timestamp: new Date().toLocaleString('zh-CN'),
    params: { ...formData }
  }

  calculationHistory.value.unshift(record)
  ElMessage.success('已保存到计算历史')
}

const viewHistory = (record) => {
  ElMessage.info('查看历史记录: ' + record.timestamp)
}

const getPolicyIcon = (type) => {
  const icons = {
    car: '🚗',
    appliance: '🏠',
    voucher: '🎫'
  }
  return icons[type] || '📄'
}

const getPolicyName = (type) => {
  const names = {
    car: '汽车补贴',
    appliance: '家电补贴',
    voucher: '消费券'
  }
  return names[type] || '政策补贴'
}
</script>

<style scoped>
.policy-calculator {
  min-height: 100%;
  padding: var(--spacing-xl);
  background: var(--bg-secondary);
}

.calculator-container {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-xl);
}

.card-header h2 {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: var(--font-size-xxl);
}

.card-header p {
  margin: 0;
  color: var(--text-secondary);
}

.policy-selector {
  margin-bottom: var(--spacing-xl);
}

.calculator-form {
  margin-top: var(--spacing-lg);
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-header h3 {
  margin: 0;
}

.subsidy-amount {
  text-align: center;
  padding: var(--spacing-xxl) 0;
}

.amount-label {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
}

.amount-value {
  font-size: 48px;
  font-weight: 700;
  color: var(--success-color);
}

.result-details h4 {
  margin-bottom: var(--spacing-md);
}

.trace-text {
  background: var(--bg-tertiary);
  padding: var(--spacing-md);
  border-radius: var(--radius-base);
  font-family: var(--font-family-mono);
  font-size: var(--font-size-sm);
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-x: auto;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.history-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-base);
  cursor: pointer;
  transition: var(--transition-fast);
}

.history-item:hover {
  background: var(--bg-tertiary);
  transform: translateX(5px);
}

.history-icon {
  font-size: 32px;
}

.history-content {
  flex: 1;
}

.history-title {
  font-weight: 600;
  margin-bottom: var(--spacing-xs);
}

.history-time {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.history-amount {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--success-color);
}

@media (max-width: 1024px) {
  .calculator-container {
    grid-template-columns: 1fr;
  }
}
</style>
