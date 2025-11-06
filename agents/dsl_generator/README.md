# DSL 生成器系统

> 🚀 将政策文档（.docx/.txt）一键转换为可执行的 Policy-as-Code DSL

## 📋 功能特性

- **📄 多格式支持**: 支持 .docx、.txt、.doc、.pdf 文档解析
- **🤖 智能提取**: 使用 LLM 或规则引擎自动提取政策要素
- **📐 标准化输出**: 生成标准 YAML 格式的 DSL 规则文件
- **⚙️ 规则引擎**: 可直接执行生成的 DSL 规则
- **🧪 自动测试**: 自动生成测试用例并验证规则正确性
- **♻️ 热更新**: 支持规则热加载，无需重启系统

## 🏗️ 系统架构

```
文档输入 (.docx/.txt)
        ↓
[1] 文档解析器 (DocumentParser)
    - 提取文本内容
    - 识别章节结构
    - 提取关键信息
        ↓
[2] DSL 提取器 (DSLExtractor)
    - LLM 结构化提取
    - 规则引擎提取（备选）
    - 数据验证
        ↓
[3] DSL 生成器 (DSLGenerator)
    - 模板渲染
    - YAML 生成
    - 格式验证
        ↓
[4] 规则引擎 (PolicyEngine)
    - 加载规则
    - 执行计算
    - 生成追踪
        ↓
输出结果 (JSON)
```

## 📦 安装依赖

```bash
pip install python-docx pyyaml jinja2 openai PyPDF2
```

## 🚀 快速开始

### 1. 基本使用

```python
from agents.dsl_generator.main import DSLPipeline

# 创建转换管道
pipeline = DSLPipeline(
    data_dir="data/guize",     # 输入文档目录
    output_dir="rules"          # DSL 输出目录
)

# 处理单个文档
result = pipeline.process_document("data/guize/消费活动.docx")

if result['status'] == 'success':
    print(f"转换成功: {result['dsl_file']}")
```

### 2. 批量处理

```python
# 处理整个目录
results = pipeline.process_directory()

for result in results:
    print(f"{result['file']}: {result['status']}")
```

### 3. 测试生成的规则

```python
# 测试规则
test_inputs = {
    'price': 10000.0,
    'energy_level': 1,
    'category': '空调'
}

result = pipeline.test_rule('Rule_Jinan_Appliance_2025', test_inputs)
print(f"补贴金额: {result['final_result']}")
```

## 📝 DSL 规范

生成的 DSL 遵循以下 YAML 格式：

```yaml
rule_id: Rule_City_Type_Year
policy_source:
  doc_id: "文档编号"
  title: "政策标题"
  clause: "条款位置"
valid_period:
  start: "2025-01-01"
  end: "2025-12-31"

inputs:
  - name: price
    type: float
    required: true
    description: "商品价格"

limits:
  per_item_cap: 2000
  per_user_per_category:
    空调: 3
    default: 1

calc:
  base_rate: 0.15
  subsidy: |
    rate = base_rate
    if energy_level == 1:
        rate += 0.05
    min(price * rate, per_item_cap)

output:
  status: "QUALIFIED"
  final_result: "{{ calc.subsidy }}"
  trace_template: |
    - 补贴比例 → {{ rate * 100 }}%
    - 补贴金额 = {{ calc.subsidy }}
```

## 🧪 测试

运行完整测试套件：

```bash
python test_dsl_generator.py
```

运行使用示例：

```bash
python example_dsl_usage.py
```

## 📂 目录结构

```
agents/dsl_generator/
├── __init__.py              # 模块初始化
├── document_parser.py       # 文档解析器
├── dsl_extractor.py        # DSL 提取器
├── dsl_generator.py        # DSL 生成器
├── rule_engine.py          # 规则引擎
└── main.py                 # 主程序入口

data/guize/                 # 输入文档目录
├── 消费活动.docx
└── 以旧换新.docx

rules/                      # 生成的 DSL 规则
├── Rule_Jinan_Appliance_2025.yaml
└── Rule_Jinan_Car_2025.yaml
```

## 🔧 配置选项

### 环境变量

```bash
# LLM 配置（可选）
export OPENAI_API_KEY="your-api-key"
export OPENAI_API_BASE="https://api.openai.com/v1"
export LLM_MODEL="gpt-4-turbo-preview"
```

### 初始化参数

```python
pipeline = DSLPipeline(
    data_dir="data/guize",      # 输入文档目录
    output_dir="rules",          # 输出目录
    api_key="your-api-key"       # API密钥（可选）
)
```

## 📊 支持的政策类型

- ✅ 家电补贴政策（分级补贴、限额限购）
- ✅ 汽车消费政策（分档补贴、礼包组合）
- ✅ 消费促进政策（满减优惠、比例补贴）
- ✅ 以旧换新政策（回收补贴、能效加成）
- ✅ 其他标准政策（可通过模板定制）

## 🎯 使用场景

1. **政策数字化**: 将纸质政策文档快速转换为可执行规则
2. **政务服务**: 在政务平台中自动计算补贴金额
3. **合规检查**: 验证申请是否符合政策要求
4. **政策对比**: 分析不同政策的差异和影响
5. **自动审批**: 基于规则自动处理补贴申请

## 🛠️ 扩展开发

### 添加新的文档格式

```python
class DocumentParser:
    def _parse_custom(self, path: Path) -> str:
        """解析自定义格式"""
        # 实现自定义解析逻辑
        return extracted_text
```

### 自定义规则模板

```python
generator.generate_from_template(
    'custom_type',
    rule_id='Rule_Custom_2025',
    custom_param='value'
)
```

### 扩展规则引擎

```python
class CustomPolicyEngine(PolicyEngine):
    def custom_calculation(self, inputs):
        # 自定义计算逻辑
        return result
```

## 🔍 故障排查

### 常见问题

1. **文档解析失败**
   - 检查文档格式是否支持
   - 确保文档不是加密或损坏的
   - 安装必要的解析库（python-docx、PyPDF2）

2. **LLM 提取失败**
   - 检查 API 密钥是否正确
   - 确认网络连接正常
   - 系统会自动降级到规则提取

3. **规则执行错误**
   - 验证输入参数格式
   - 检查规则文件是否有效
   - 查看日志获取详细错误信息

### 日志配置

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## 📈 性能优化

- 批量处理使用并行处理提高效率
- 规则缓存减少重复加载
- LLM 调用使用低温度参数保证一致性
- 支持增量更新，只处理新文档

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 发起 Pull Request

## 📄 许可证

MIT License

## 👥 作者

政策数字化团队

## 🔗 相关链接

- [政策即代码规范](https://policy-as-code.org)
- [YAML 语法参考](https://yaml.org)
- [Jinja2 模板文档](https://jinja.palletsprojects.com)