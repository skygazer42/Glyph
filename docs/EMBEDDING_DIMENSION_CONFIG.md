# Milvus Embedding 维度配置指南

## 概述

Milvus 向量数据库的 collection 需要在创建时指定向量维度，且创建后无法修改。本系统会根据 embedding 模型自动推断正确的维度。

## 支持的 Embedding 模型和维度

### DashScope (阿里云)

**text-embedding-v3** 支持的维度：
- 64
- 128
- 256
- 512
- 768
- 1024 (默认)

**text-embedding-v2** 固定维度：
- 1536

### OpenAI

| 模型 | 维度 |
|------|------|
| text-embedding-3-small | 1536 |
| text-embedding-3-large | 3072 |
| text-embedding-ada-002 | 1536 |

## 配置方式

### 方式 1: 使用 EMBEDDING_DASHSCOPE_DIMENSION（推荐）

在 `.env` 文件中明确指定 DashScope 的维度：

```bash
# DashScope Embedding
EMBEDDING_BACKEND=dashscope
EMBEDDING_DASHSCOPE_MODEL=text-embedding-v3
EMBEDDING_DASHSCOPE_DIMENSION=1024  # 可选: 64, 128, 256, 512, 768, 1024

# 通用 Embedding 配置
EMBEDDING_DIM=1024  # 应与 DASHSCOPE_DIMENSION 一致
```

### 方式 2: 只使用 EMBEDDING_DIM

如果维度在支持范围内，系统会自动使用：

```bash
# DashScope Embedding
EMBEDDING_BACKEND=dashscope
EMBEDDING_DASHSCOPE_MODEL=text-embedding-v3

# 通用 Embedding 配置
EMBEDDING_DIM=768  # 必须是 DashScope 支持的维度之一
```

### 方式 3: 使用默认值

如果不指定，系统使用模型的默认维度：

```bash
# DashScope Embedding
EMBEDDING_BACKEND=dashscope
EMBEDDING_DASHSCOPE_MODEL=text-embedding-v3
# 将自动使用 1024 维（text-embedding-v3 的默认值）
```

## OpenAI 配置示例

```bash
# OpenAI Embedding
EMBEDDING_BACKEND=openai
EMBEDDING_OPENAI_MODEL=text-embedding-3-small
# 自动推断为 1536 维

# 或使用 large 模型
EMBEDDING_OPENAI_MODEL=text-embedding-3-large
# 自动推断为 3072 维
```

## 维度不匹配处理

如果尝试连接到已存在的 collection，但维度不匹配，系统会抛出清晰的错误：

```
ValueError: Collection 'policy_documents' already exists with dimension 1024,
but current embedding model requires dimension 1536.

Please either:
1. Drop the existing collection: utility.drop_collection('policy_documents')
2. Use a different collection name
3. Switch to an embedding model with dimension 1024
```

### 解决方案

#### 方案 1: 删除旧 collection（数据会丢失）

```python
from pymilvus import utility, connections

connections.connect(
    alias="default",
    host="localhost",
    port="19530"
)

utility.drop_collection("policy_documents")
```

#### 方案 2: 使用不同的 collection 名称

```bash
DATABASE__MILVUS_COLLECTION_NAME=policy_documents_v2
```

#### 方案 3: 切换到匹配的 embedding 模型

修改 `.env` 使用与现有 collection 维度匹配的模型。

## 自动维度推断逻辑

系统按以下优先级推断维度：

1. **DashScope**:
   - `EMBEDDING_DASHSCOPE_DIMENSION`（如果配置）
   - `EMBEDDING_DIM`（如果在支持范围内）
   - 默认 1024

2. **OpenAI**:
   - 根据模型名称自动识别
   - text-embedding-3-large → 3072
   - text-embedding-3-small → 1536
   - ada-002 → 1536
   - 默认 1536

3. **其他后端**:
   - `EMBEDDING_DIM`
   - 默认 1024

## 测试维度配置

运行测试脚本验证配置：

```bash
python3 tests/test_dimension_inference.py
```

测试内容：
- ✓ DashScope backend 维度推断
- ✓ OpenAI small 模型 (1536维)
- ✓ OpenAI large 模型 (3072维)
- ✓ 维度不匹配检测

## 最佳实践

1. **明确配置**: 始终在 `.env` 中明确配置 `EMBEDDING_DASHSCOPE_DIMENSION` 和 `EMBEDDING_DIM`
2. **保持一致**: 确保 `EMBEDDING_DIM` 与实际模型的维度一致
3. **测试验证**: 修改配置后运行测试脚本验证
4. **文档记录**: 在项目文档中记录使用的 embedding 模型和维度
5. **迁移计划**: 如需更换模型，提前规划数据迁移策略

## 常见问题

### Q: 为什么 text-embedding-v3 不支持 1536 维？

A: DashScope 的 text-embedding-v3 只支持 [64, 128, 256, 512, 768, 1024]。如需 1536 维，请使用 text-embedding-v2 或 OpenAI 模型。

### Q: 已有数据如何迁移到新维度？

A: 需要重新生成 embedding 并插入新 collection：

```python
# 1. 从旧 collection 读取原始文本
old_docs = old_store.get_all_documents()

# 2. 创建新配置的 store（新维度）
new_store = MilvusStore(collection_name="policy_documents_v2")

# 3. 重新插入（会自动生成新维度的 embedding）
new_store.add_documents(old_docs)
```

### Q: 可以同时使用多个 embedding 模型吗？

A: 可以，但需要使用不同的 collection 名称：

```python
store_1024 = MilvusStore(
    backend="dashscope",
    collection_name="docs_dashscope_1024"
)

store_1536 = MilvusStore(
    backend="openai",
    collection_name="docs_openai_1536"
)
```

## 参考

- [DashScope Embedding API](https://help.aliyun.com/zh/dashscope/developer-reference/text-embedding-api-details)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [Milvus Collection Schema](https://milvus.io/docs/schema.md)
