# LlamaIndex 分级索引使用指南

## 📋 概述

这是一个基于 LlamaIndex 的分级索引和混合检索系统，专门为政策文档优化。系统实现了：
- **三级索引结构**：文档级 → 章节级 → 块级
- **智能切块策略**：按标题分段 + 滑动窗口
- **LLM 章节摘要**：可选使用 LLM 生成更准确的章节摘要
- **混合检索**：向量检索 + 重排序（支持 DashScope 重排）
- **多种检索模式**：hybrid（混合）、hierarchical（层级）、direct（直接）
- **无 Torch 依赖**：使用 DashScope 或简单重排，避免安装 PyTorch

## 🚀 快速开始

### 1. 使用快速启动脚本（推荐）

```bash
# 运行交互式菜单
bash /data/temp33/gov/scripts/run_llamaindex.sh
```

菜单选项：
- **1) 构建索引** - 从 Markdown 文档构建分级索引
- **2) 测试检索** - 运行预设查询测试
- **3) 交互查询** - 进入实时查询模式
- **4) 查看统计** - 显示索引信息
- **5) 重建索引** - 清除并重建索引
- **6) 安装依赖** - 安装 Python 包

### 2. 使用命令行工具

#### 构建索引
```bash
python /data/temp33/gov/scripts/batch_process.py build \
    --data-dir /data/temp33/gov/data/process \
    --storage-dir /data/temp33/gov/storage/hierarchical \
    --chunk-size 800 \
    --chunk-overlap 100

# 使用 LLM 生成章节摘要（更准确但更慢）
python /data/temp33/gov/scripts/batch_process.py build \
    --data-dir /data/temp33/gov/data/process \
    --storage-dir /data/temp33/gov/storage/hierarchical \
    --use-llm
```

#### 测试检索
```bash
python /data/temp33/gov/scripts/batch_process.py test \
    --storage-dir /data/temp33/gov/storage/hierarchical \
    --mode hybrid \
    --top-k 5 \
    --queries "家电补贴标准" "手机购新条件"
```

#### 交互查询
```bash
python /data/temp33/gov/scripts/batch_process.py query \
    --storage-dir /data/temp33/gov/storage/hierarchical \
    --mode hybrid \
    --top-k 5
```

#### 查看统计
```bash
python /data/temp33/gov/scripts/batch_process.py stats \
    --storage-dir /data/temp33/gov/storage/hierarchical
```

### 3. Python API 使用

```python
from knowledge_base.hierarchical_index import (
    HierarchicalIndexBuilder,
    HierarchicalRetriever,
    ChunkConfig
)

# 构建索引
builder = HierarchicalIndexBuilder(
    storage_dir="./storage/hierarchical",
    embed_model_name="text-embedding-3-small"  # 可选
)

# 构建索引（可选：使用 LLM 生成摘要）
stats = builder.build_from_markdown_files(
    file_paths=["/path/to/doc1.md", "/path/to/doc2.md"],
    use_llm=True  # 使用 LLM 生成章节摘要
)

# 检索（使用 DashScope 重排）
retriever = HierarchicalRetriever(
    storage_dir="./storage/hierarchical",
    use_rerank="dashscope"  # 或 "simple", "none"
)

# 混合检索
nodes = retriever.retrieve(
    query="家电以旧换新补贴标准",
    top_k=10,
    use_rerank=True,
    retrieval_mode="hybrid"  # 或 "hierarchical", "direct"
)

# 获取查询引擎（带响应生成）
engine = retriever.get_query_engine(
    retrieval_mode="hybrid",
    response_mode="compact"
)
response = engine.query("补贴申请流程是什么？")
print(response)
```

### 4. 集成到现有系统

```python
from knowledge_base.llamaindex_integration import EnhancedVectorRetrieverAgent
from agents.base.types import PolicyDocument

# 创建增强检索器（LlamaIndex + FAISS）
retriever = EnhancedVectorRetrieverAgent(
    use_llamaindex=True,
    fallback_to_faiss=True,
    llamaindex_storage="/data/temp33/gov/storage/hierarchical"
)

# 搜索（自动融合 LlamaIndex 和 FAISS 结果）
documents, scores = await retriever.search(
    query="家电补贴标准",
    top_k=10,
    threshold=0.7
)

# 添加新文档
new_docs = [
    PolicyDocument(
        id="doc1",
        title="新政策",
        content="政策内容...",
        source="政府部门"
    )
]
await retriever.add_documents(new_docs)
```

## 🔧 配置参数

### 切块参数（ChunkConfig）

| 参数 | 默认值 | 说明 |
|-----|-------|------|
| chunk_size | 800 | 每个块的字符数 |
| chunk_overlap | 100 | 块之间的重叠字符数 |
| section_summary_size | 250 | 章节摘要长度 |
| include_tables | True | 是否包含表格 |
| include_code_blocks | True | 是否包含代码块 |

### 检索模式

| 模式 | 说明 | 适用场景 |
|-----|------|---------|
| hybrid | 混合检索（推荐） | 综合性查询，兼顾精度和召回 |
| hierarchical | 层级检索 | 需要上下文的复杂查询 |
| direct | 直接检索 | 精确匹配，速度优先 |

### 重排模式

| 模式 | 说明 | 依赖 |
|-----|------|------|
| dashscope | 使用 DashScope API 重排（推荐） | 需要配置 DASHSCOPE_API_KEY |
| simple | 基于分数的简单重排 | 无额外依赖 |
| none | 不进行重排 | 无额外依赖 |

### 响应模式

| 模式 | 说明 |
|-----|------|
| compact | 紧凑响应，只返回核心信息 |
| tree_summarize | 树形总结，适合长文档 |
| simple_summarize | 简单总结 |

### LLM 摘要选项

| 参数 | 说明 | 优缺点 |
|-----|------|--------|
| --use-llm | 使用 LLM 生成章节摘要 | ✅ 更准确的语义理解<br>❌ 构建速度慢，费用高 |
| 不使用 | 简单截取前 N 字符 | ✅ 快速，无额外费用<br>❌ 摘要质量一般 |

## 📊 系统架构

```
文档（Markdown）
    ↓
分级处理器（HierarchicalMarkdownProcessor）
    ↓
├── 文档节点（doc_nodes）- Level 0
├── 章节节点（section_nodes）- Level 1
└── 块节点（chunk_nodes）- Level 2
    ↓
多级索引构建（HierarchicalIndexBuilder）
    ↓
├── doc_index（文档索引）
├── section_index（章节索引）
├── chunk_index（块索引）
└── summary_index（摘要索引）
    ↓
混合检索（HierarchicalRetriever）
    ↓
├── 父层召回（Section）
├── 子层细搜（Chunks）
└── 交叉重排（Reranker）
    ↓
最终结果
```

## 🎯 最佳实践

### 1. 中文文档优化参数
```python
config = ChunkConfig(
    chunk_size=600,  # 中文约 600-900 字最佳
    chunk_overlap=100,  # 保证语义连贯
    section_summary_size=200  # 摘要不宜过长
)
```

### 2. 检索策略选择

- **政策查询**：使用 `hybrid` 模式，兼顾精确性和覆盖面
- **条款定位**：使用 `hierarchical` 模式，保留章节上下文
- **关键词搜索**：使用 `direct` 模式，快速返回结果

### 3. 性能优化

- 首次构建索引较慢，之后会自动加载缓存
- 可调整 `top_k` 参数控制检索数量
- 使用重排器（reranker）提升精度，但会增加延迟

## 🐛 故障排除

### 索引构建失败
- 检查 Markdown 文件编码（应为 UTF-8）
- 确保有足够磁盘空间（索引大小约为原文档的 1.5-2 倍）
- 查看日志文件了解详细错误

### 检索无结果
- 确认索引已构建（运行 stats 命令检查）
- 尝试更通用的查询词
- 调整 threshold 参数（降低阈值）

### 内存不足
- 减小 chunk_size
- 分批处理文档
- 使用 FAISS 的量化索引

## 📝 示例查询

以下是一些优化过的查询示例：

```python
# 政策资格查询
"申请家电以旧换新补贴需要什么条件"
"哪些人可以享受手机购新补贴"

# 金额计算查询
"空调补贴金额如何计算"
"最高可以获得多少补贴"

# 流程咨询
"如何申请消费券"
"补贴申请流程是什么"

# 对比查询
"家电补贴和手机补贴有什么区别"
"济南和山东省的政策差异"
```

## 🔧 依赖说明

本系统特意设计为**轻量级**，避免重量级依赖：

- ✅ **无需 PyTorch**：不使用 sentence-transformers
- ✅ **使用 API 重排**：DashScope 重排器（云端 API）
- ✅ **简单重排备选**：基于分数的简单重排
- ✅ **可选 LLM 摘要**：按需使用，不是必须

需要安装的核心包：
```bash
pip install faiss-cpu llama-index llama-index-core
# 可选：DashScope 重排
pip install dashscope
```

## 🔗 相关文件

- 主程序：`/data/temp33/gov/knowledge_base/hierarchical_index.py`
- 批处理脚本：`/data/temp33/gov/scripts/batch_process.py`
- 快速启动：`/data/temp33/gov/scripts/run_llamaindex.sh`
- 集成模块：`/data/temp33/gov/knowledge_base/llamaindex_integration.py`

## 📧 支持

如有问题，请查看日志文件或运行诊断命令：
```bash
python /data/temp33/gov/scripts/batch_process.py stats --storage-dir /data/temp33/gov/storage/hierarchical
```