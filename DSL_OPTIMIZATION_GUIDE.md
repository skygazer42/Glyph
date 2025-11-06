# DSL 生成器优化说明

## 📋 优化内容

我已经优化了 DSL 生成器系统，使其使用项目中已有的 .env 和 settings.py 配置，而不是重新编写配置。

## 🔧 主要改进

### 1. 使用项目配置的 LLM

**原版本问题：**
- 硬编码 OpenAI API 配置
- 需要单独设置 API Key
- 与项目其他模块配置不统一

**优化后：**
- 自动使用项目 settings.py 中的 LLM 配置
- 支持千问（qwen-turbo）通过阿里云 DashScope API
- 与项目其他模块配置统一

### 2. 新增文件

- `dsl_extractor_v2.py` - 优化版提取器，使用项目配置
- `main_v2.py` - 优化版主程序，支持配置选择
- `test_dsl_with_config.py` - 测试文件，展示如何使用

### 3. 配置方式

```python
from agents.dsl_generator.main_v2 import DSLPipeline

# 使用项目配置（推荐）
pipeline = DSLPipeline(
    data_dir="data/guize",
    output_dir="rules",
    use_project_config=True  # 使用项目配置的 LLM
)

# 不使用项目配置（纯规则提取）
pipeline = DSLPipeline(
    data_dir="data/guize",
    output_dir="rules",
    use_project_config=False  # 不使用 LLM，仅规则提取
)
```

## 🚀 使用方法

### 1. 使用项目 LLM 配置

```python
from agents.dsl_generator.main_v2 import DSLPipeline

# 自动读取 .env 中的配置
# LLM_API_KEY=sk-xxx
# LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# LLM_MODEL_NAME=qwen-turbo

pipeline = DSLPipeline(use_project_config=True)
result = pipeline.process_document("政策文档.docx")
```

### 2. 测试系统

```bash
# 测试使用项目 LLM 配置
python test_dsl_with_config.py --mode llm

# 测试纯规则提取（不用 LLM）
python test_dsl_with_config.py --mode rule

# 比较两种模式
python test_dsl_with_config.py --mode compare
```

### 3. 快速测试

```bash
# 快速测试基本功能
python quick_test_dsl.py
```

## 📊 模式对比

| 特性 | 使用项目配置（LLM） | 纯规则提取 |
|------|-------------------|------------|
| 准确度 | 高（智能理解） | 中（基于规则） |
| 速度 | 慢（API 调用） | 快（本地处理） |
| 成本 | 有 API 费用 | 无费用 |
| 依赖 | 需要网络和 API Key | 无外部依赖 |
| 适用场景 | 复杂文档 | 标准化文档 |

## 🔍 项目配置读取

系统会自动从以下位置读取配置：

1. **LLM 配置** (`.env`)
   ```
   LLM_API_KEY=sk-xxx
   LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
   LLM_MODEL_NAME=qwen-turbo
   LLM_TEMPERATURE=0
   ```

2. **Settings 配置** (`config/settings.py`)
   ```python
   from config.settings import settings

   # 自动使用
   settings.model.llm_api_key
   settings.model.llm_base_url
   settings.model.llm_model_name
   settings.model.llm_temperature
   ```

## ✅ 优势

1. **配置统一**：与项目其他模块使用相同配置
2. **易于维护**：修改 .env 即可改变所有模块配置
3. **灵活切换**：支持 LLM 和规则两种模式
4. **降级策略**：LLM 失败时自动降级到规则提取
5. **无缝集成**：直接使用项目已有的千问模型

## 📝 注意事项

1. 确保 .env 文件中有正确的 LLM 配置
2. 如果没有 API Key，系统会自动使用规则提取模式
3. 规则提取模式适合标准化文档
4. LLM 模式适合复杂、非标准化文档

## 🎯 推荐使用方式

- **标准政策文档**：使用规则提取（快速、免费）
- **复杂政策文档**：使用项目 LLM（准确、智能）
- **混合模式**：优先 LLM，失败时自动降级

## 📂 文件结构

```
agents/dsl_generator/
├── __init__.py              # 模块初始化
├── document_parser.py       # 文档解析器
├── dsl_extractor.py        # 原版提取器
├── dsl_extractor_v2.py     # [新] 优化版提取器
├── dsl_generator.py        # DSL 生成器
├── rule_engine.py          # 规则引擎
├── main.py                 # 原版主程序
├── main_v2.py              # [新] 优化版主程序
└── README.md               # 使用文档

测试文件：
├── test_dsl_with_config.py  # [新] 配置测试
├── quick_test_dsl.py        # [新] 快速测试
└── demo_dsl.py             # 演示文件
```

## 🔗 相关文档

- [项目配置指南](config/README.md)
- [DSL 生成器文档](agents/dsl_generator/README.md)
- [.env 配置说明](.env.example)