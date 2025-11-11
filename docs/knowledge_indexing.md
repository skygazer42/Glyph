# 知识库分级索引方案

本文档说明当前知识检索链路如何利用 **LlamaIndex 多层索引 + Milvus 向量库** 实现“先粗后细”的召回流程，以及相关配置/构建步骤。

## 1. 架构总览

```
MinerU / OCR
   ↓
Markdown/JSON 文本
   ↓
LlamaIndex Hierarchical Index
        ├─ 文档节点（Document）
        ├─ 章节节点（Section）
        └─ Chunk 节点（600± overlap）
   ↓                         ↘
Milvus 向量库 (叶子)          Neo4j / 其它索引（可选）
```

检索阶段：
1. `KnowledgeService` 先尝试调用 `HierarchicalRetriever`（如果存在存储目录），在“章节/chunk”两层上进行混合召回（内部使用 `AutoMergingRetriever + RecursiveRetriever`）。
2. 将结果短名单写入 `PolicyDocument`，标记 `retrieval_origin=hierarchical_index`。
3. 若命中不足或未启用，回退到 Milvus 检索，返回 `retrieval_origin=knowledge_base`。
4. `KnowledgeAgent` 根据 `doc_origins` 在 metadata 中写入 `["hierarchical_index", "knowledge_base", ...]`，并在回答中引用对应片段；若仍无结果，再触发 Tavily WebSearch。

## 2. 配置

在 `.env` 中启用多级检索并指定索引存储路径：

```ini
SYSTEM__HYBRID_RETRIEVAL_ENABLED=true
LLAMAINDEX_STORAGE_DIR=resources/storage/hierarchical
```

系统启动时会自动创建该目录；若配置关闭，则 `KnowledgeService` 只会使用 Milvus。

## 3. 构建/刷新索引

> 由于 `HierarchicalIndexBuilder` 目前以“全量重建”为主，建议 **按批次/整库** 重建，而不是对单篇文档增量追加。

1. 准备解析后的 Markdown / 文本（推荐使用 `MinerUAdapter` + `HierarchicalMarkdownProcessor`）。
2. 运行示例脚本（如 `scripts/embed_documents.py` 或 `scripts/batch_process.py`），它会调用 `HierarchicalIndexBuilder.build_from_markdown_files(...)`，并将索引写入 `LLAMAINDEX_STORAGE_DIR`。
3. 检查输出：目录下应包含 `doc_index/`, `section_index/`, `chunk_index/`, `summary_index/` 等子目录。
4. 服务重启后，`KnowledgeService` 会自动检测 `storage_dir` 是否存在索引，从而开启分级检索。

## 4. 检索策略细节

- **Hierarchical → Vector**：默认同时查询两个索引，分级结果优先；如果分数不足或 `top_k` 未满，会在 Milvus 中继续补齐。
- **重排**：`HierarchicalRetriever` 内置 `simple` rerank；如需 DashScope/BGE rerank，可在 `app/knowledge/hierarchical_index.py` 中调整 `use_rerank` 参数。
- **上下文还原**：`AutoMergingRetriever` 会在叶子召回后自动向上合并，确保回答时能看到完整段落，而不是零散片段。
- **Metadata**：每个节点保留 `path, level, chunk_idx`，`KnowledgeAgent` 会在 `FinalAnswer.metadata.doc_origins` 中回传，便于前端调试或日志分析。

## 5. 常见操作

| 需求 | 操作 |
|------|------|
| 全量重建索引 | 清空 `LLAMAINDEX_STORAGE_DIR` 后运行 `scripts/embed_documents.py` |
| 查看索引大小 | `python -m app.knowledge.llamaindex_integration --stats`（可自建脚本调用 `LlamaIndexIntegration.get_stats()`） |
| 强制仅用向量库 | 将 `SYSTEM__HYBRID_RETRIEVAL_ENABLED=false` 或删除索引目录 |
| Debug 检索 | 在 `KnowledgeService.search` 中开 `logger.debug`，可看到"hierarchical / vector"分别命中了哪些文档 |
| 知识库文档存储 | 文档应存放在 `resources/knowledge_base/documents/` 目录下 |

> 如果需要进一步增强（例如结合 Neo4j 图谱或 RAPTOR 多层摘要），可基于 `app/knowledge/hierarchical_index.py` 继续扩展节点生成和检索策略。

## 6. 注意事项

- `HierarchicalIndexBuilder` 当前为同步实现，重建耗时与文档大小成正比；建议在离线批处理任务中执行。
- 由于索引重建会覆盖旧数据，请确保重建任务包含所有需要上线的文档。
- 若要接入其它检索器（SQL、GraphRAG 等），可以在 `KnowledgeAgent` 中根据 `doc_origins` 决定组合策略，或将新的 retriever 注册到 `HierarchicalRetriever`。
