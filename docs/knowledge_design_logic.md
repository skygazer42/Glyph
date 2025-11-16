# 知识库设计逻辑（按数据流）

这里按“数据流”的顺序，把知识库的设计逻辑理一遍：  
**文档进来 → 切片/分块 → 建索引 → 召回 → Agent 生成答案**，并在每一步说明可以用的方式，以及 `.env` 里如何配置。



---

## 1. 文档进入系统（原始数据 → PolicyDocument）

**目标**：把各种来源的政策文档（Markdown/PDF/Word 等）统一变成内部的 `PolicyDocument` 结构。

- 入口模块：
  - `app/knowledge/document_loader.py:DocumentLoader`
  - 可配合 `MinerUAdapter`、OCR、批处理脚本使用。

- 常用脚本：
  - `scripts/5_embed_process_documents.py`
    - 从目录（默认 `resources/data/process`）遍历文件；
    - 调用 `DocumentLoader.iter_documents_from_directory` 生成 `PolicyDocument`。

- 关键点：
  - 这一层只负责“规范化文档”：标题、正文、来源、元数据；
  - 和“怎么切块、怎么建索引”解耦，上层可以统一复用。

---

## 2. 切片 / 分块（PolicyDocument → 多级节点）

**目标**：把一篇长政策切成“文档级 → 章节级 → Chunk 级”的层次结构，为后续分级索引和召回做准备。

- 核心模块：`app/knowledge/hierarchical_index.py`
  - `HierarchicalMarkdownProcessor`：
    - `extract_hierarchy(text, doc_id)`：按 Markdown 标题 (`#` / `##`) 拆出文档/章节结构。
    - `create_nodes_from_hierarchy(...)`：
      - 生成文档节点（document）
      - 生成章节节点（section），可选用 LLM 做摘要
      - 调用 `_split_into_chunks` 生成 Chunk 节点（chunk）
  - `ChunkConfig`：
    - `chunking_strategy`: `'simple' | 'sentence' | 'keyword_aware'`
    - `chunk_size` / `chunk_overlap`：块大小与重叠度

- 切片策略（按需求选）：
  - `simple`：固定字符窗口，简单粗暴，适合快速试验；
  - `sentence`：按句子边界切，再做滑动窗口（推荐，用于中文政策长文档）；
  - `keyword_aware`：对包含“补贴标准/申请条件”等关键词的区域扩充上下文，使关键条款更完整地落在同一块中。

- `.env` 中相关配置（通过 `LlamaIndexSettings` 生效）：
  ```ini
  LLAMAINDEX_CHUNK_STRATEGY=sentence           # simple / sentence / keyword_aware
  LLAMAINDEX_CHUNK_SIZE=800                    # 每块大致长度
  LLAMAINDEX_CHUNK_OVERLAP=150                 # 相邻块的重叠字符数
  ```

> 实际构建时，`scripts/4_embed_documents.py` 会根据这些配置，调用 `HierarchicalMarkdownProcessor` 按设定策略分块。

---

## 3. 建索引（节点 → LlamaIndex + Milvus）

**目标**：为上一步产出的节点构建检索索引；同时把 `PolicyDocument` 向量化写入 Milvus。

### 3.1 分级索引（LlamaIndex）

- 构建器：`HierarchicalIndexBuilder`
  - 输入：Markdown 文件路径列表（或 `LlamaIndexIntegration` 生成的临时 Markdown）；
  - 输出：
    - `doc_index/`：文档级 VectorStoreIndex
    - `section_index/`：章节级 VectorStoreIndex
    - `chunk_index/`：块级 VectorStoreIndex
    - `summary_index/`：基于 section 节点的 SummaryIndex
  - 持久化位置：`LLAMAINDEX_STORAGE_DIR`（默认为 `resources/storage/hierarchical` 或 `.env` 中指定）。

- 典型脚本：
  ```bash
  # 离线方式：从 Markdown 目录构建分级索引
  python scripts/4_embed_documents.py \
    --data-dir resources/data/process \
    --storage-dir resources/storage/hierarchical
  ```

- `.env` 配置：
  ```ini
  SYSTEM__HYBRID_RETRIEVAL_ENABLED=true
  LLAMAINDEX_STORAGE_DIR=resources/storage/hierarchical
  ```

  开启 `SYSTEM__HYBRID_RETRIEVAL_ENABLED=true` 且指定 `LLAMAINDEX_STORAGE_DIR` 后：
  - `KnowledgeService` 会尝试初始化 `LlamaIndexIntegration`；
  - 若检测到该目录下存在 `doc_index/section_index/chunk_index`，则开启分级检索。

### 3.2 向量索引（Milvus）

- 存储层：`app/knowledge/milvus.py:MilvusStore`
  - 负责集合创建、写入向量、按相似度检索。

- 统一入口：`KnowledgeService.index_documents`：
  - 把 `PolicyDocument` 列表写入 Milvus（embedding 模型由 `settings.embedding` 配置）；
  - 在 Hybrid 打开的情况下，同时调用 `LlamaIndexIntegration.build_index_from_documents` 用同一批文档刷新分级索引。

- 常用脚本：
  ```bash
  # 使用 KnowledgeService 统一写入向量库（推荐）
  python scripts/5_embed_process_documents.py --input-dir resources/data/process
  ```

- `.env` 配置：
  ```ini
  DATABASE__MILVUS_HOST=localhost
  DATABASE__MILVUS_PORT=19530
  DATABASE__MILVUS_COLLECTION_NAME=policy_documents

  EMBEDDING_BACKEND=openai                  # 或 dashscope
  EMBEDDING_OPENAI_API_KEY=...
  EMBEDDING_OPENAI_MODEL=text-embedding-3-small
  ```

> 通过 `SYSTEM__HYBRID_RETRIEVAL_ENABLED` 和 `LLAMAINDEX_STORAGE_DIR` 决定“是否在向量库之外再带一层 LlamaIndex 分级索引”；所有写入动作仍然走 `KnowledgeService` 单一入口。

---

## 4. 召回（Query → 文档列表）

**目标**：给一个用户问题，返回一组相关 `PolicyDocument` 和对应置信度分数，供 `KnowledgeAgent` 使用。

### 4.1 统一召回入口：`KnowledgeService.search`

整体流程：

1. 初始化一个合并容器 `combined: {doc_id: (doc, score)}`。
2. 若 Hybrid 打开且分级索引存在：
   - 调用 `LlamaIndexIntegration.search(query, top_k, threshold, retrieval_mode="hybrid")`：
     - 实际由 `HierarchicalRetriever.retrieve` 执行：
       - 从 `section_index/chunk_index/summary_index` 组合召回；
       - 返回带 `retrieval_origin="hierarchical_index"` 的 `PolicyDocument` 和分数列表。
     - 将结果写入 `combined`。
3. 无论是否有分级索引，都执行 Milvus 向量检索：
   - 调用 `MilvusStore.search(query, top_k*2, threshold, filters)`；
   - 结果标记 `retrieval_origin="knowledge_base"`，写入 `combined`。
4. 按分数降序排序 `combined`，取前 `top_k`，返回给上层。

### 4.2 检索模式选择（只改 .env）

1. **仅向量检索（Milvus-only）**
   ```ini
   SYSTEM__HYBRID_RETRIEVAL_ENABLED=false
   ```
   - 不管是否有 LlamaIndex 索引，`KnowledgeService` 只调用 Milvus；
   - 适合轻量部署或不想引入 LlamaIndex 依赖的环境。

2. **分级索引 + 向量混合（推荐）**
   ```ini
   SYSTEM__HYBRID_RETRIEVAL_ENABLED=true
   LLAMAINDEX_STORAGE_DIR=resources/storage/hierarchical
   ```
   - `KnowledgeService` 先走分级索引（LlamaIndex），再用 Milvus 补齐；
   - 召回质量更稳定，尤其对长政策文件、章节结构较复杂的场景效果更好。

3. **只用分级索引（实验场景，不推荐线上）**
   - 理论上可以在 `KnowledgeService.search` 中关掉 Milvus 分支，只保留 LlamaIndex 调用；
   - 当前默认实现仍然会保留 Milvus 兜底，建议作为 debug 场景手动修改，不在 `.env` 里提供开关。

---

## 5. Agent 生成答案（文档列表 → 最终回答）

**目标**：基于召回的文档列表和分数，生成一个结构化的政策回答，兼顾速度和质量。

入口：`app/agents/pipeline/knowledge_agent.py:KnowledgeAgent.answer`

1. `KnowledgeAgent` 调用 `KnowledgeService.search` 获取 `(docs, scores)`；
2. 用 `_estimate_confidence(scores)` 估计检索置信度；
3. 与 `settings.system.early_stop_conf`（`.env` 中的 `EARLY_STOP_CONF`）比较：
   - 若 `confidence >= EARLY_STOP_CONF`：
     - 触发“早停路径”：优先用 `_extract_policy_points` 从首篇文档做规则抽取；
     - 抽取不到再用一次 LLM 汇总；
     - 标记 `metadata.early_stopped=True`。
   - 否则：
     - 正常路径：格式化若干篇文档内容，构造总结 prompt 调用 LLM。
4. `_format_documents(docs)` 控制给 LLM 的上下文体积：
   - 每篇文档在传给 LLM 之前会截断到：
     ```python
     max_chars = settings.system.knowledge_max_context_per_doc  # 对应 KNOWLEDGE_MAX_CONTEXT_PER_DOC
     ```
   - 默认值为 6000，可通过 `.env` 调整。

### 5.1 与回答质量/速度直接相关的配置

```ini
# 早停阈值：检索置信度 >= 该值时走快速通道
EARLY_STOP_CONF=0.80

# 每篇文档传给 LLM 的最大字符数（KnowledgeAgent 内部截断使用）
KNOWLEDGE_MAX_CONTEXT_PER_DOC=2500
```

调参建议：

- 若希望“快、便宜”，可以：
  - 略微降低 `EARLY_STOP_CONF`（如 0.70），让更多请求走早停；
  - 降低 `KNOWLEDGE_MAX_CONTEXT_PER_DOC`（如 1500–2000），减少 tokens。
- 若希望“稳”，可以：
  - 提高 `EARLY_STOP_CONF`（如 0.90），让更多问题走“重排+深度总结”；
  - 在模型上下文足够的前提下适度提高 `KNOWLEDGE_MAX_CONTEXT_PER_DOC`。

---

## 6. 小结：数据流顺序 + 关键 .env 开关

1. **文档进来 → `DocumentLoader` 生成 `PolicyDocument`**
2. **切片/分块 → `HierarchicalMarkdownProcessor`（受 `LLAMAINDEX_CHUNK_*` 控制）**
3. **建索引 → `HierarchicalIndexBuilder` + `MilvusStore`（是否启用 Hybrid 由 `SYSTEM__HYBRID_RETRIEVAL_ENABLED` 决定）**
4. **召回 → `KnowledgeService.search`（分级索引 + 向量混合或仅向量）**
5. **生成答案 → `KnowledgeAgent.answer`（受 `EARLY_STOP_CONF`、`KNOWLEDGE_MAX_CONTEXT_PER_DOC` 控制）**

只要记住这几个关键环境变量，就能控制大部分“切片/索引/召回/生成”的行为，而不用去改代码：

- `SYSTEM__HYBRID_RETRIEVAL_ENABLED`
- `LLAMAINDEX_STORAGE_DIR`
- `LLAMAINDEX_CHUNK_STRATEGY`
- `LLAMAINDEX_CHUNK_SIZE`
- `LLAMAINDEX_CHUNK_OVERLAP`
- `EARLY_STOP_CONF`
- `KNOWLEDGE_MAX_CONTEXT_PER_DOC`

按这个顺序看，你就能从“数据是怎么进来的”一路追踪到“最终答案是怎么被算出来的”，同时知道每一步在哪个模块实现、用哪些 `.env` 可以调。 
