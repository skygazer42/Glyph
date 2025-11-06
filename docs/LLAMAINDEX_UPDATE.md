# LlamaIndex 分级索引系统 - 更新说明

## ✅ 已完成的优化

### 1. LLM 章节摘要支持

**之前的问题**：只是简单截取文本前 N 个字符作为章节摘要，没有语义理解。

**现在的改进**：
- 添加了 `use_llm` 参数，可选使用 LLM 生成章节摘要
- 在 `generate_section_summary()` 方法中集成了 OpenAI API 调用
- 命令行支持 `--use-llm` 参数

```bash
# 使用 LLM 生成章节摘要
python scripts/batch_process.py build \
    --data-dir /data/process \
    --use-llm
```

**优点**：
- 更准确的语义理解
- 提升检索相关性
- 摘要质量高

**缺点**：
- 构建速度慢（需要调用 API）
- 有 API 费用

### 2. 移除 PyTorch 依赖

**之前的问题**：使用 sentence-transformers 进行重排，需要安装 PyTorch（几 GB 大小）。

**现在的改进**：
- 移除了 sentence-transformers 依赖
- 实现了三种重排模式：
  - `dashscope`：使用 DashScope API 重排（云端，无本地依赖）
  - `simple`：基于分数的简单重排（纯 Python）
  - `none`：不进行重排

```python
# 使用 DashScope 重排（推荐）
retriever = HierarchicalRetriever(
    storage_dir="./storage",
    use_rerank="dashscope"  # API 重排，无需 PyTorch
)

# 使用简单重排
retriever = HierarchicalRetriever(
    storage_dir="./storage",
    use_rerank="simple"  # 基于分数，无额外依赖
)
```

### 3. DashScope 重排集成

利用了项目已有的 `knowledge_base/rerank.py` 中的 DashScope 重排器：

```python
def _init_dashscope_reranker(self):
    """初始化 DashScope 重排器"""
    try:
        from knowledge_base.rerank import Reranker
        self.reranker = Reranker()
    except ImportError:
        self.reranker = "simple"  # 自动降级到简单重排
```

### 4. 简单重排策略

当无法使用 DashScope 时，提供了基于分数的简单重排：

```python
def _simple_rerank(self, nodes, query, top_k):
    # 根据节点类型调整权重
    for node in nodes:
        if node.metadata.get('type') == 'section':
            node.score *= 1.2  # 章节权重更高
        elif node.metadata.get('type') == 'document':
            node.score *= 0.8  # 文档权重较低
    # 按分数排序
    return sorted(nodes, key=lambda x: x.score, reverse=True)[:top_k]
```

## 📊 性能对比

| 方案 | 依赖大小 | 构建速度 | 检索质量 | 费用 |
|-----|---------|---------|---------|------|
| 原方案（sentence-transformers） | ~4GB（PyTorch） | 中等 | 高 | 无 |
| DashScope 重排 + LLM 摘要 | <100MB | 慢 | 最高 | 有 API 费用 |
| DashScope 重排 + 简单摘要 | <100MB | 快 | 高 | 少量 API 费用 |
| 简单重排 + 简单摘要 | <100MB | 最快 | 中等 | 无 |

## 🔧 配置建议

### 开发环境（快速迭代）
```bash
# 不使用 LLM，使用简单重排
python scripts/batch_process.py build \
    --data-dir /data/process \
    --chunk-size 800 \
    --chunk-overlap 100
```

### 生产环境（最佳效果）
```bash
# 使用 LLM 摘要 + DashScope 重排
export DASHSCOPE_API_KEY=your_key
python scripts/batch_process.py build \
    --data-dir /data/process \
    --use-llm

# 检索时自动使用 DashScope
retriever = HierarchicalRetriever(use_rerank="dashscope")
```

### 离线环境（无网络）
```bash
# 使用简单重排，无需任何 API
retriever = HierarchicalRetriever(use_rerank="simple")
```

## 📝 环境变量配置

```bash
# .env 文件

# LLM 配置（用于生成摘要）
LLM_API_KEY=your_openai_or_compatible_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL_NAME=deepseek-chat

# DashScope 重排（可选）
DASHSCOPE_API_KEY=your_dashscope_key
RERANKER_MODEL=gte-rerank-v2
```

## 🚀 下一步建议

1. **测试不同配置的效果**
   - 对比 LLM 摘要 vs 简单摘要的检索质量
   - 对比 DashScope vs 简单重排的准确率

2. **优化 LLM 摘要 Prompt**
   - 针对政策文档特点优化提示词
   - 考虑添加关键信息提取

3. **批量处理优化**
   - LLM 摘要可以批量调用，减少 API 请求次数
   - 实现摘要缓存，避免重复生成

4. **添加 BM25 检索**
   - 考虑集成 Meilisearch 或 Elasticsearch
   - 实现真正的混合检索（向量 + 关键词）

## 📚 相关文件

- 核心实现：`knowledge_base/hierarchical_index.py`
- 批处理工具：`scripts/batch_process.py`
- 使用文档：`docs/LLAMAINDEX_GUIDE.md`
- 依赖配置：`requirements.txt`（已移除 sentence-transformers）