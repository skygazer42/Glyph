# 知识库检索流程概览

## 1. 数据进入（切片）
1. 使用 MinerU / OCR 将 PDF、Word 等原文转为 Markdown/纯文本。
2. 通过 `HierarchicalIndexBuilder`（LlamaIndex）把文档拆成三层：
   - 叶子 chunk（~600 tokens，带 overlap）
   - 小节/章节摘要节点
   - 文档级摘要
3. 同一批 chunk 也写入 Milvus（向量库），保留 doc_id/source 等元数据。

## 2. 索引结构
| 索引 | 作用 | 存储 |
|------|------|------|
| LlamaIndex 层级索引 | 存结构（parent/child、path、level）+摘要；支持 AutoMerging/Recursive 检索 | `LLAMAINDEX_STORAGE_DIR` |
| Milvus 向量库 | 保存叶子向量，兼容传统语义检索 | Milvus 集群 |

> 自 `KnowledgeService.index_documents()` 起，Milvus 写入完成后会自动调用 `LlamaIndexIntegration.build_index_from_documents()`，保持两套索引一致。

## 3. 在线召回
1. `KnowledgeService.search()` 先调用 `HierarchicalRetriever`：
   - 章节 → 下钻到 chunk；
   - 可选 DashScope/BGE rerank；
   - `PolicyDocument.retrieval_origin = "hierarchical_index"`。
2. 若 `top_k` 不足或分级索引不存在，则回退 Milvus：
   - `retrieval_origin = "knowledge_base"`。
3. 两路结果合并去重，按统一 score 排序，记录 `doc_origins`。
4. 若仍无结果，触发 `WebSearchTool`（Tavily）兜底，`origin = "web_search"`。

## 4. LLM 总结 & 回答
`KnowledgeAgent` 读取合并后的文档片段：
- 生成特定 prompt（含 focus / intent）调用 LLM；
- 在 `FinalAnswer.metadata` 中附带 `doc_origins`、来源数量、兜底原因等；
- 上层 API/CLI 根据 metadata 呈现引用或 debug 信息。

## 5. 常见配置
```ini
SYSTEM__HYBRID_RETRIEVAL_ENABLED=true
LLAMAINDEX_STORAGE_DIR=resources/storage/hierarchical
WEB_SEARCH__ENABLED=true
```

## 6. 维护建议
1. 首次部署前用 `scripts/embed_documents.py` 全量构建分级索引。
2. 在线新增文档直接调用 `KnowledgeService.index_documents()`（会自动更新两套索引）。
3. 定期检查 `LLAMAINDEX_STORAGE_DIR` 容量与 Milvus 数据量是否同步。
4. 如需只观察向量检索，将 `SYSTEM__HYBRID_RETRIEVAL_ENABLED=false`，或删除分级索引目录。

## 7. 代码入口
- 切片与索引：`app/knowledge/hierarchical_index.py`
- 混合检索入口：`app/knowledge/service.py`
- LlamaIndex 集成：`app/knowledge/llamaindex_integration.py`
- 回答生成：`app/agents/pipeline/knowledge_agent.py`
