# 配置指南

本文档说明如何配置政策智能问答系统的所有组件。

## 📖 配置原则

所有配置遵循统一的链路：

```
.env 文件 → config/settings.py → 各模块使用
```

**禁止硬编码**：所有模块必须通过 `settings` 获取配置，不允许直接使用 `os.getenv()`。

## 🔧 配置文件

### 1. 环境变量文件 (.env)

复制 `.env.example` 创建你的配置：

```bash
cp .env.example .env
```

然后编辑 `.env` 文件设置你的 API 密钥和配置。

### 2. 配置结构 (settings.py)

配置被组织成多个类别：

| 配置类 | 作用 | 主要配置项 |
|--------|------|-----------|
| `ModelSettings` | LLM 配置（OpenAI 兼容） | llm_api_key, llm_base_url, llm_model_name |
| `EmbeddingSettings` | Embedding API 配置 | backend, openai_*, dashscope_* |
| `LlamaIndexSettings` | 文档切块配置 | chunk_strategy, chunk_size, chunk_overlap |
| `MinerUSettings` | MinerU 2.5 文档解析 | enabled, api_base_url, api_key |
| `RerankerSettings` | 重排序配置 | backend, dashscope_api_key, model_name |
| `DatabaseSettings` | 数据库配置 | milvus_*, neo4j_* |
| `DocumentSettings` | 文档处理配置 | max_file_size_mb, max_pages |
| `PerformanceSettings` | 性能配置 | max_concurrent_queries, batch_size |
| `SystemSettings` | 系统配置 | debug, data_dir, logs_dir |

## 🎯 核心配置详解

### LLM 配置

项目使用统一的 OpenAI 兼容接口，支持 DeepSeek、OpenAI、本地部署等所有 OpenAI 兼容 API。

```bash
# LLM 配置（使用 OpenAI 兼容接口）
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL_NAME=deepseek-chat
LLM_TEMPERATURE=0
LLM_CTX_BUFFER_SIZE=10
```

**使用示例**：

```python
from config.settings import settings
from openai import OpenAI

# 使用 settings.model 配置
client = OpenAI(
    api_key=settings.model.llm_api_key,
    base_url=settings.model.llm_base_url
)

response = client.chat.completions.create(
    model=settings.model.llm_model_name,
    messages=[{"role": "user", "content": "你好"}],
    temperature=settings.model.llm_temperature
)
```

**支持的 LLM 提供商**：

| 提供商 | LLM_BASE_URL | LLM_MODEL_NAME 示例 |
|--------|--------------|-------------------|
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4`, `gpt-3.5-turbo` |
| 本地部署 | `http://localhost:8000/v1` | 根据实际模型名称 |

### Embedding 配置

```bash
# 选择后端
EMBEDDING_BACKEND=openai  # 可选: openai, dashscope

# OpenAI Embedding
EMBEDDING_OPENAI_API_KEY=sk-xxx
EMBEDDING_OPENAI_BASE_URL=https://api.openai.com/v1
EMBEDDING_OPENAI_MODEL=text-embedding-3-small

# DashScope Embedding（阿里云）
EMBEDDING_DASHSCOPE_API_KEY=sk-xxx
EMBEDDING_DASHSCOPE_MODEL=text-embedding-v2

# 通用配置
EMBEDDING_DIM=1536
EMBEDDING_BATCH_SIZE=32
EMBEDDING_TIMEOUT=30
```

**使用示例**：

```python
from config.settings import settings

# ❌ 错误方式 - 直接使用 os.getenv
import os
api_key = os.getenv("EMBEDDING_OPENAI_API_KEY")

# ✅ 正确方式 - 使用 settings
api_key = settings.embedding.openai_api_key
model = settings.embedding.openai_model
```

### MinerU 2.5 文档解析配置

```bash
# 启用 MinerU
MINERU_ENABLED=true
MINERU_API_BASE_URL=http://localhost:8080
MINERU_API_KEY=your_api_key
MINERU_TIMEOUT=300

# 解析选项
MINERU_EXTRACT_IMAGES=true
MINERU_EXTRACT_TABLES=true
MINERU_EXTRACT_FORMULAS=true
```

**使用示例**：

```python
from config.settings import settings
from knowledge_base.mineru_adapter import MinerUAdapter

# 自动使用 settings.mineru 配置
adapter = MinerUAdapter()

# 或者覆盖特定配置
adapter = MinerUAdapter(config={
    "api_base_url": "http://custom:8080",
    "enabled": True
})
```

### LlamaIndex 文档切块配置

```bash
# 切块策略
LLAMAINDEX_CHUNK_STRATEGY=sentence  # sentence, semantic, fixed

# 切块大小
LLAMAINDEX_CHUNK_SIZE=1000
LLAMAINDEX_CHUNK_OVERLAP=200

# Sentence Splitter
LLAMAINDEX_SENTENCE_CHUNK_SIZE=1024
LLAMAINDEX_SENTENCE_CHUNK_OVERLAP=200

# Semantic Splitter
LLAMAINDEX_SEMANTIC_BUFFER_SIZE=1
LLAMAINDEX_SEMANTIC_THRESHOLD=0.5
```

**使用示例**：

```python
from config.settings import settings
from llama_index.core.node_parser import SentenceSplitter

# 使用 settings 配置
splitter = SentenceSplitter(
    chunk_size=settings.llamaindex.chunk_size,
    chunk_overlap=settings.llamaindex.chunk_overlap,
    separator=settings.llamaindex.separator
)
```

### Reranker 配置

```bash
# 后端选择
RERANKER_BACKEND=dashscope  # dashscope, xinference, llamaindex

# DashScope Reranker
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_RERANK_MODEL=gte-rerank-v2
RERANKER_TOP_N=5

# 策略配置
KB_RERANK_ENABLED=true
RERANKER_STRATEGY=replace  # replace 或 fuse
RERANK_WEIGHT=0.7
FAISS_WEIGHT=0.3
```

**使用示例**：

```python
from config.settings import settings
from knowledge_base.rerank import Reranker

# 自动使用 settings.reranker 配置
reranker = Reranker()

# 使用配置
results = reranker.rerank(
    query="查询文本",
    documents=docs,
    top_n=settings.reranker.top_n
)
```

### Milvus 向量数据库配置

```bash
# Milvus 配置
DATABASE__MILVUS_HOST=localhost
DATABASE__MILVUS_PORT=19530
DATABASE__MILVUS_USER=
DATABASE__MILVUS_PASSWORD=
DATABASE__MILVUS_DB_NAME=default
DATABASE__MILVUS_COLLECTION_NAME=policy_documents
```

**使用示例**：

```python
from config.settings import settings
from knowledge_base import MilvusStore

# 自动使用 settings.database.milvus_* 配置
store = MilvusStore()

# 或者覆盖特定配置
store = MilvusStore(
    host="custom-host",
    port=19531,
    collection_name="custom_collection"
)
```

## 📋 配置检查清单

### 基础配置 (必需)

- [ ] `LLM_API_KEY` - LLM API 密钥（支持所有 OpenAI 兼容 API）
- [ ] `LLM_BASE_URL` - LLM API 地址（DeepSeek、OpenAI、本地部署等）
- [ ] `LLM_MODEL_NAME` - LLM 模型名称

### Embedding 配置 (必需)

- [ ] `EMBEDDING_BACKEND` - 选择 backend (openai/dashscope)
- [ ] 对应 backend 的 API_KEY 和配置

### 可选配置

- [ ] `MINERU_ENABLED` - 是否启用 MinerU 文档解析
- [ ] `RERANKER_BACKEND` - 是否启用重排序
- [ ] `DATABASE__MILVUS_HOST` - 是否使用 Milvus
- [ ] `DATABASE__NEO4J_URI` - 是否使用 Neo4j

## 🔍 配置验证

### 1. 检查配置加载

```python
from config.settings import settings

# 打印当前配置
print("Embedding backend:", settings.embedding.backend)
print("Embedding model:", settings.embedding.openai_model)
print("MinerU enabled:", settings.mineru.enabled)
print("Milvus host:", settings.database.milvus_host)
```

### 2. 验证 API 连接

```python
from knowledge_base import VectorStore, MilvusStore
from knowledge_base.mineru_adapter import MinerUAdapter

# 测试 Embedding
store = VectorStore()
print("Vector store backend:", store.backend)
print("Vector store model:", store.model_name)

# 测试 MinerU
async def test_mineru():
    adapter = MinerUAdapter()
    health = await adapter.health_check()
    print("MinerU health:", health)

# 测试 Milvus
milvus = MilvusStore()
stats = milvus.get_stats()
print("Milvus stats:", stats)
```

### 3. 常见问题

**问题**: `ValueError: Missing API key for OpenAI backend`

**解决**: 检查 `.env` 文件中是否设置了 `EMBEDDING_OPENAI_API_KEY` 或 `LLM_API_KEY`

---

**问题**: `ConnectionError: Failed to connect to Milvus`

**解决**:
1. 确认 Milvus 服务已启动
2. 检查 `DATABASE__MILVUS_HOST` 和 `DATABASE__MILVUS_PORT` 配置

---

**问题**: MinerU 解析失败

**解决**:
1. 检查 `MINERU_ENABLED=true`
2. 验证 `MINERU_API_BASE_URL` 可访问
3. 确认 `MINERU_API_KEY` 正确

## 🚀 最佳实践

### 1. 环境隔离

为不同环境使用不同的 `.env` 文件：

```bash
.env.development  # 开发环境
.env.production   # 生产环境
.env.test         # 测试环境
```

### 2. 敏感信息保护

**不要**将 `.env` 文件提交到 git：

```bash
# .gitignore
.env
.env.*
!.env.example
```

### 3. 配置优先级

配置的优先级从高到低：

1. 函数参数直接传入
2. `.env` 文件中的环境变量
3. `settings.py` 中的默认值

示例：

```python
from knowledge_base import MilvusStore
from config.settings import settings

# 优先级 3: 使用 settings 默认值
store1 = MilvusStore()

# 优先级 2: .env 中 EMBEDDING_BACKEND=openai
store2 = MilvusStore()

# 优先级 1: 直接传参
store3 = MilvusStore(backend="dashscope")
```

### 4. 配置验证

在应用启动时验证关键配置：

```python
from config.settings import settings

def validate_config():
    """验证关键配置"""
    errors = []

    # 检查 LLM 配置
    if not settings.model.llm_api_key:
        errors.append("LLM_API_KEY 未配置")
    if not settings.model.llm_model_name:
        errors.append("LLM_MODEL_NAME 未配置")

    # 检查 Embedding 配置
    if settings.embedding.backend == "openai":
        if not settings.embedding.openai_api_key:
            errors.append("OpenAI Embedding API Key 未配置")
    elif settings.embedding.backend == "dashscope":
        if not settings.embedding.dashscope_api_key:
            errors.append("DashScope Embedding API Key 未配置")

    # 检查 MinerU 配置
    if settings.mineru.enabled:
        if not settings.mineru.api_base_url:
            errors.append("MinerU API URL 未配置")

    if errors:
        raise ValueError("配置错误:\n" + "\n".join(errors))

    print("✅ 配置验证通过")

# 在应用启动时调用
validate_config()
```

## 📚 更多信息

- [README.md](../README.md) - 项目总览
- [.env.example](../.env.example) - 完整配置模板
- [config/settings.py](../config/settings.py) - 配置类定义
