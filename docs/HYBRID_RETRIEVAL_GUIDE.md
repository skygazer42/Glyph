# 混合检索使用指南 (Hybrid Retrieval Guide)

## 📚 概述

混合检索（Hybrid Retrieval）结合了关键词匹配和语义搜索的优势，能够提供更准确、更全面的检索结果。

本系统实现了两种混合检索方案：

1. **向量检索 + Reranker** ✅ 推荐 - 简单高效，精准度高
2. **BM25 + 向量检索** (基于 LlamaIndex + Milvus Sparse Index)

---

## 🎯 方案1: 向量检索 + Reranker（推荐）

### 架构说明

```
查询 Query
  ↓
向量检索 (Milvus)
  ├─ 初步召回 top_k=10
  ├─ 相似度阈值 threshold=0.50
  ↓
Reranker 重排序 (DashScope)
  ├─ 精准评分
  ├─ 重新排序
  ├─ 返回 top_k=3
  ↓
最终结果
```

### 优点

- ✅ **实现简单**：仅需2步，易于理解和维护
- ✅ **精准度高**：Reranker 专门优化相关性评分
- ✅ **速度快**：向量检索毫秒级，Reranker API 响应快
- ✅ **成本适中**：仅需向量数据库 + Reranker API

### 使用示例

#### 基本使用

```python
from knowledge_base.milvus import MilvusStore
from knowledge_base.rerank import Reranker

# 1. 创建向量存储
store = MilvusStore(
    collection_name="my_collection",
    backend="dashscope"
)

# 2. 添加文档
documents = [...]  # 你的文档列表
store.add_documents(documents)

# 3. 创建 Reranker
reranker = Reranker()

# 4. 混合检索
query = "家电以旧换新补贴政策"

# 步骤1: 向量初召回
documents, scores = store.search(
    query,
    top_k=10,  # 广召回
    threshold=0.50
)

# 步骤2: Rerank 重排序
doc_texts = [f"{doc.title}\n{doc.content}" for doc in documents]
reranked = reranker.rerank(query, doc_texts, top_n=3)

# 提取最终结果
final_docs = []
final_scores = []
for idx, score, _ in reranked:
    final_docs.append(documents[idx])
    final_scores.append(score)

# 显示结果
for doc, score in zip(final_docs, final_scores):
    print(f"[{score:.4f}] {doc.title}")
    print(f"  {doc.content[:100]}...")
```

#### 封装为函数

```python
def hybrid_search(query: str, store: MilvusStore, reranker: Reranker, top_k: int = 3):
    """混合检索封装"""
    # 初召回
    documents, _ = store.search(query, top_k=10, threshold=0.50)

    if not documents:
        return [], []

    # Rerank
    doc_texts = [f"{doc.title}\n{doc.content[:500]}" for doc in documents]
    reranked = reranker.rerank(query, doc_texts, top_n=top_k)

    # 提取结果
    final_docs = [documents[idx] for idx, _, _ in reranked]
    final_scores = [score for _, score, _ in reranked]

    return final_docs, final_scores


# 使用
docs, scores = hybrid_search("家电补贴政策", store, reranker)
```

### 配置说明

#### Milvus 配置 (`.env`)

```bash
# Milvus 连接
DATABASE__MILVUS_HOST=localhost
DATABASE__MILVUS_PORT=19530

# Embedding 配置
EMBEDDING_BACKEND=dashscope
EMBEDDING_DASHSCOPE_API_KEY=your_dashscope_key
EMBEDDING_DASHSCOPE_DIMENSION=1024
```

#### Reranker 配置 (`.env`)

```bash
# Reranker 配置
RERANKER_BACKEND=dashscope
RERANKER_MODEL=gte-rerank-v2
DASHSCOPE_RERANK_API_KEY=your_dashscope_key
RERANKER_TOP_N=5
RERANKER_TIMEOUT=30
```

### 性能指标

| 指标 | 值 |
|------|-----|
| 初召回延迟 | < 100ms |
| Rerank 延迟 | < 500ms |
| 总延迟 | < 600ms |
| 精准召回率 | 90-100% |
| 成本 | 低 (仅 Embedding + Rerank API) |

---

## 🎯 方案2: BM25 + 向量混合（LlamaIndex）

### 架构说明

```
查询 Query
  ↓
Milvus Hybrid Search
  ├─ BM25 稀疏向量检索 (关键词匹配)
  ├─ Dense 向量检索 (语义匹配)
  ├─ RRF 混合排序
  ├─ Alpha 权重调节
  ↓
最终结果
```

### 优点

- ✅ **真正的混合检索**：同时利用关键词和语义信息
- ✅ **可调节权重**：alpha 参数控制 BM25 vs 向量的比例
- ✅ **一站式方案**：单次查询完成混合检索
- ✅ **适合复杂查询**：对关键词敏感的场景效果更好

### 使用示例

```python
from knowledge_base.llamaindex_hybrid_retrieval import (
    LlamaIndexHybridRetriever,
    load_documents_from_dir
)
from pathlib import Path

# 1. 加载文档
data_dir = Path("/your/data/dir")
documents = load_documents_from_dir(data_dir)

# 2. 创建混合检索器
retriever = LlamaIndexHybridRetriever(
    collection_name="hybrid_search",
    alpha=0.5,  # 0=纯BM25, 1=纯向量, 0.5=均衡混合
    similarity_top_k=10,
    overwrite=True
)

# 3. 构建索引
retriever.build_index(documents)

# 4. 执行检索
nodes = retriever.retrieve("家电以旧换新补贴")

# 5. 显示结果
for i, node in enumerate(nodes[:5], 1):
    print(f"{i}. [{node.score:.4f}] {node.node.text[:100]}...")
```

### Alpha 权重调节

```python
# 测试不同权重
alphas = [0.0, 0.3, 0.5, 0.7, 1.0]

for alpha in alphas:
    retriever.update_alpha(alpha)

    print(f"\nAlpha = {alpha:.1f}")
    if alpha == 0.0:
        print("  → 纯BM25关键词检索")
    elif alpha == 1.0:
        print("  → 纯向量语义检索")
    else:
        print(f"  → 混合 (BM25:{1-alpha:.1f}, Vector:{alpha:.1f})")

    nodes = retriever.retrieve(query)
    for node in nodes[:3]:
        print(f"    [{node.score:.4f}] {node.node.text[:60]}...")
```

### 配置说明

```bash
# Milvus 连接
DATABASE__MILVUS_HOST=localhost
DATABASE__MILVUS_PORT=19530

# Embedding 配置 (DashScope)
EMBEDDING_BACKEND=dashscope
EMBEDDING_DASHSCOPE_API_KEY=your_key
EMBEDDING_DASHSCOPE_DIMENSION=1024

# LLM 配置 (可选，用于query_engine)
LLM_API_KEY=your_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-turbo
```

### 注意事项

1. **索引类型限制**：稀疏索引必须使用 `IP` (内积) 相似度度量
2. **集合创建**：使用 `overwrite=True` 会删除已存在的集合
3. **代理问题**：如果有代理设置，可能需要禁用（已在代码中处理）

---

## 📊 两种方案对比

| 特性 | 向量+Reranker | BM25+向量 |
|------|--------------|-----------|
| **实现复杂度** | ⭐ 简单 | ⭐⭐⭐ 复杂 |
| **精准度** | ⭐⭐⭐⭐⭐ 优秀 | ⭐⭐⭐⭐ 良好 |
| **速度** | ⭐⭐⭐⭐ 快 | ⭐⭐⭐ 中等 |
| **关键词敏感度** | ⭐⭐⭐ 中等 | ⭐⭐⭐⭐⭐ 优秀 |
| **语义理解** | ⭐⭐⭐⭐⭐ 优秀 | ⭐⭐⭐⭐ 良好 |
| **可调节性** | ⭐⭐ 有限 | ⭐⭐⭐⭐⭐ 灵活 |
| **成本** | 💰💰 低 | 💰💰💰 中等 |
| **推荐场景** | 大部分场景 | 专业/复杂查询 |

---

## 🚀 快速开始

### 方案1: 向量+Reranker (推荐新手)

```bash
# 1. 运行测试
python3 tests/test_hybrid_simple.py

# 2. 查看效果对比
# 输出会显示纯向量 vs 混合检索的效果对比
```

### 方案2: BM25+向量 (推荐进阶)

```bash
# 1. 运行测试
python3 tests/test_llamaindex_hybrid_retrieval.py

# 2. 对比不同 alpha 值的效果
# 输出会显示不同权重下的检索结果
```

---

##  最佳实践

### 1. 选择合适的方案

**使用向量+Reranker 当:**
- 你需要快速部署
- 查询相对简单直接
- 追求高精准度
- 预算有限

**使用 BM25+向量 当:**
- 查询包含专业术语或关键词
- 需要精确匹配特定词语
- 愿意投入更多成本优化
- 数据集较大且复杂

### 2. 参数调优

#### 向量+Reranker

```python
# 初召回参数
initial_top_k = 10      # 召回数量，建议 5-20
threshold = 0.50        # 相似度阈值，建议 0.4-0.6

# Rerank 参数
rerank_top_n = 3        # 最终返回数量，根据业务需求
```

#### BM25+向量

```python
# Alpha 权重建议
alpha = 0.3   # 关键词敏感场景
alpha = 0.5   # 均衡场景（推荐）
alpha = 0.7   # 语义理解场景
```

### 3. 监控和评估

```python
# 记录检索指标
metrics = {
    'query': query,
    'latency_ms': latency,
    'top1_score': scores[0],
    'num_results': len(results),
    'method': 'hybrid'
}

# 定期评估精准率
precision = calculate_precision(results, ground_truth)
```

---

## 🔧 故障排查

### 问题1: Reranker 返回分数都是 0

**原因**: API Key 未配置或无效

**解决**:
```bash
# 检查 .env 文件
grep DASHSCOPE_RERANK_API_KEY .env

# 如果没有，添加
echo "DASHSCOPE_RERANK_API_KEY=your_key" >> .env
```

### 问题2: Milvus 稀疏索引错误

**错误**: `only IP is the supported metric type for sparse index`

**解决**: 确保配置了正确的索引参数
```python
sparse_index_config = {
    "index_type": "SPARSE_INVERTED_INDEX",
    "metric_type": "IP"  # 必须是 IP
}
```

### 问题3: 维度不匹配

**错误**: `dimension mismatch`

**解决**: 确保 embedding 维度配置正确
```bash
# DashScope
EMBEDDING_DASHSCOPE_DIMENSION=1024

# OpenAI
# text-embedding-3-small: 1536
# text-embedding-3-large: 3072
```

---

## 📝 总结

**推荐使用方案1（向量+Reranker）**，因为：
- ✅ 实现简单，易于维护
- ✅ 精准度高（90-100%）
- ✅ 速度快（< 600ms）
- ✅ 成本低
- ✅ 适用于大部分场景

**进阶用户可尝试方案2（BM25+向量）**，特别是在：
- 专业领域查询
- 关键词精确匹配场景
- 需要更fine-grained控制的情况

---

## 📚 相关文档

- [Milvus 向量数据库文档](https://milvus.io/docs)
- [DashScope Rerank API](https://help.aliyun.com/zh/dashscope/developer-reference/api-rerank)
- [LlamaIndex 混合检索](https://docs.llamaindex.ai/en/stable/examples/vector_stores/milvus_hybrid_search/)
- [召回优化报告](./RECALL_OPTIMIZATION_REPORT.md)
- [检索方式对比](./RETRIEVAL_METHODS_COMPARISON.md)

---

**最后更新**: 2025-11-07
**测试状态**: ✅ 通过 (精准召回率 100%)
