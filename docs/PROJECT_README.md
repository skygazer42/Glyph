# Glyph - 政策DSL生成和知识库管理系统

政策文本自动化处理系统,支持政策文本的DSL生成、知识库存储、向量检索和规则执行。

## 主要功能

### 1. DSL自动生成
- 从自然语言政策文本自动提取结构化信息
- 支持多种政策类型:消费券、家电补贴、汽车补贴
- 自动检测政策类型并使用对应模板
- 生成可执行的YAML格式规则文件

### 2. 知识库管理
- 基于Milvus的向量存储
- 支持多种嵌入模型(DashScope、OpenAI等)
- 文档分块和向量化
- 向量检索和语义搜索

### 3. 规则执行引擎
- 加载和执行DSL规则
- 支持复杂的计算逻辑
- 提供可解释性跟踪
- RESTful API接口

## 快速开始

### 环境要求
- Python 3.8+
- Docker & Docker Compose
- LLM API访问权限(如DashScope)

### 安装依赖
```bash
pip install -r requirements.txt
```

### 配置环境变量
复制 `.env.example` 到 `.env` 并配置:
```env
# LLM配置
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-turbo

# 嵌入模型配置
EMBEDDING_BACKEND=dashscope
EMBEDDING_DASHSCOPE_API_KEY=your_api_key
EMBEDDING_DASHSCOPE_MODEL=text-embedding-v3
EMBEDDING_DASHSCOPE_DIMENSION=1024

# 数据库配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

### 启动服务

#### 1. 启动Docker服务(Milvus、Redis等)
```bash
docker-compose up -d
```

#### 2. 启动API服务
```bash
python api_server.py
```

服务将运行在 http://localhost:8000

### API使用示例

#### 生成DSL
```bash
curl -X POST http://localhost:8000/api/dsl/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "济南市2025年家电补贴政策..."
  }'
```

#### 测试规则执行
```bash
curl -X POST http://localhost:8000/api/dsl/test \
  -H "Content-Type: application/json" \
  -d '{
    "rule_id": "Rule_Test_Consumer_Coupon",
    "inputs": {
      "consumption_amount": 250.0,
      "coupon_type": "AMOUNT"
    }
  }'
```

#### 知识库搜索
```bash
curl -X POST http://localhost:8000/api/knowledge/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "家电补贴政策",
    "top_k": 5
  }'
```

## 项目结构

```
Glyph/
├── agents/                      # 智能体模块
│   ├── dsl_generator/          # DSL生成器
│   │   ├── dsl_extractor.py   # LLM文本提取
│   │   ├── dsl_generator.py   # YAML生成
│   │   ├── document_parser.py # 文档解析
│   │   └── rule_engine.py     # 规则执行引擎
│   └── base/                   # 基础类型定义
├── knowledge_base/             # 知识库模块
│   ├── milvus.py              # Milvus向量存储
│   ├── embedding.py           # 嵌入模型
│   └── retrieval.py           # 检索器
├── config/                     # 配置模块
│   └── settings.py            # 项目配置
├── templates/                  # DSL模板
│   ├── consumer_coupon.yaml.j2    # 消费券模板
│   ├── appliance_subsidy.yaml.j2  # 家电补贴模板
│   └── auto_subsidy.yaml.j2       # 汽车补贴模板
├── rules/                      # 生成的规则文件
├── data/                       # 数据目录
│   ├── guize/                 # 政策文本
│   └── process/               # 处理后的文档
├── tests/                      # 测试文件
│   └── README.md              # 测试说明
├── api_server.py              # API服务器
├── docker-compose.yaml        # Docker配置
└── .env                       # 环境变量配置
```

## 核心模块说明

### DSL生成器 (agents/dsl_generator/)

**dsl_extractor.py**
- 使用LLM从政策文本提取结构化信息
- 支持多种政策类型的专门提示词
- 自动检测政策类型: `_detect_policy_type()`
- 提取方法:
  - `_build_coupon_prompt()` - 消费券提示词
  - `_build_appliance_prompt()` - 家电补贴提示词
  - `_build_auto_prompt()` - 汽车补贴提示词

**dsl_generator.py**
- 使用Jinja2模板生成YAML规则文件
- 支持外部模板自动加载
- 模板自动检测: `detect_template_type()`
- 数据预处理和验证

**rule_engine.py**
- 加载和执行YAML规则
- 支持Jinja2表达式求值
- 提供可解释性跟踪

### 知识库 (knowledge_base/)

**milvus.py**
- Milvus向量数据库封装
- 文档添加、搜索、删除
- 自动处理collection创建和维护

**embedding.py**
- 支持多种嵌入模型:
  - DashScope (阿里云)
  - OpenAI
  - LocalAI
- 统一的嵌入接口

## 测试

详细测试说明请参考 [tests/README.md](tests/README.md)

### 运行完整测试
```bash
cd tests
python test_complete_dsl.py
```

### 运行知识库测试
```bash
cd tests
python test_kb_simple.py
```

## 最新测试结果 (2025-11-08)

### ✅ DSL生成
- 消费券政策: 自动使用consumer_coupon模板 ✓
- 家电补贴政策: 自动使用appliance_subsidy模板 ✓
- 所有关键字段验证通过 ✓

### ✅ 知识库召回
- 4个测试查询全部成功 ✓
- 召回分数: 0.6-0.8 ✓
- Milvus向量库正常运行 ✓

### ✅ 规则执行
- 消费券: 250元 → 满200减40 → 实付210元 ✓
- 返回完整的可解释性跟踪 ✓

## API文档

API服务运行后,访问 http://localhost:8000/docs 查看完整API文档(Swagger UI)。

### 主要端点

**DSL生成**
- `POST /api/dsl/generate` - 从文本生成DSL
- `POST /api/dsl/save` - 保存DSL到文件
- `GET /api/dsl/list` - 获取所有规则
- `GET /api/dsl/{rule_id}` - 获取规则详情
- `POST /api/dsl/test` - 测试规则执行

**知识库**
- `POST /api/knowledge/upload` - 上传文档
- `POST /api/knowledge/embed` - 嵌入文档到向量库
- `POST /api/knowledge/search` - 搜索知识库
- `GET /api/knowledge/documents` - 获取文档列表
- `DELETE /api/knowledge/documents/{doc_id}` - 删除文档

## 配置说明

### LLM配置
系统使用LLM进行政策文本提取。支持的模型:
- qwen-turbo (推荐)
- qwen-plus
- qwen-max

### 嵌入模型配置
支持的后端:
- `dashscope` - 阿里云DashScope (推荐)
- `openai` - OpenAI
- `localai` - 本地模型

### 向量库配置
使用Milvus v2.3.3作为向量数据库:
- 默认端口: 19530
- 支持的索引类型: HNSW, IVF_FLAT等
- 向量维度: 根据嵌入模型自动配置

## 模板系统

DSL生成使用Jinja2模板系统,支持:
- 外部模板目录: `templates/`
- 自动模板检测
- 模板继承和包含
- 自定义过滤器

### 可用模板

**consumer_coupon.yaml.j2** - 消费券模板
- 券种类型(满减/折扣)
- 分档设置
- 发放规则
- 使用限制

**appliance_subsidy.yaml.j2** - 家电补贴模板
- 能效补贴率
- 类别限额
- 单品封顶

**auto_subsidy.yaml.j2** - 汽车补贴模板
- 价格分档
- 车辆类型
- 补贴金额

## 故障排查

### Milvus连接失败
```bash
# 检查Docker服务
docker-compose ps

# 重启Milvus
docker-compose restart milvus-standalone
```

### 向量维度不匹配
```bash
# 删除并重建collection
cd tests
python reset_collection.py
```

### API服务无法启动
- 检查 `.env` 配置是否正确
- 确认LLM API密钥有效
- 检查端口8000是否被占用

## 开发

### 添加新的政策类型

1. 在 `templates/` 创建新模板
2. 在 `dsl_extractor.py` 添加检测逻辑到 `_detect_policy_type()`
3. 添加专门的提示词方法 `_build_xxx_prompt()`
4. 在 `dsl_generator.py` 的 `detect_template_type()` 添加模板匹配规则

### 添加新的嵌入模型

1. 在 `knowledge_base/embedding.py` 添加新的嵌入类
2. 在 `config/settings.py` 添加配置选项
3. 更新 `.env.example`

## 许可证

[待添加]

## 贡献

[待添加]
