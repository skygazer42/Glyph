# 知识库召回模式说明

当前知识检索有三条主路径，核心差异在于召回来源、上下文形态与性能取舍。

## 1) 向量召回（Milvus 单路）
- **做法**：用户问题经 Embedding 后，在 Milvus 向量库里召回 Top-K 文档片段（`PolicyDocument`），可选再走 DashScope 重排（`KB_RERANK_ENABLED`）。
- **配置要点**：`SYSTEM__HYBRID_RETRIEVAL_ENABLED=false`，`LLAMA_INDEX_RERANK_ENABLED` 可关；`KNOWLEDGE_MAX_CONTEXT_PER_DOC` 控制每段送入 LLM 的截断长度。
- **适用**：速度优先、数据干净、段落粒度较均匀。延迟最低，但对长文跨段关联较弱。

## 2) 混合召回（Milvus + LlamaIndex 分层）
- **做法**：同时跑分层索引（LlamaIndex Hierarchical Index）与 Milvus 向量检索，各自取 Top-K*2，合并去重后再裁剪 Top-K。可选对分层结果重排（`LLAMA_INDEX_RERANK_ENABLED`）及向量重排（`KB_RERANK_ENABLED`）。
- **配置要点**：`SYSTEM__HYBRID_RETRIEVAL_ENABLED=true`；分层索引存储目录 `LLAMAINDEX_STORAGE_DIR`，截断 `KNOWLEDGE_MAX_CONTEXT_PER_DOC`，重排参数同上。
- **适用**：长文/章节结构明显的政策文档，需要“章节导航 + 语义相似”双保险。召回质量高但耗时高于纯向量。

## 3) 分层召回（LlamaIndex 分层索引侧重）
- **做法**：基于 LlamaIndex 的层次化节点（标题→小节→段落）做检索与可选重排，可单独理解为“分层索引通路”；在混合模式下它与向量结果合并，若仅想侧重分层，可降低向量 Top-K 或关闭向量重排。
- **配置要点**：保持 `SYSTEM__HYBRID_RETRIEVAL_ENABLED=true`，同时可将向量侧 Top-K 调低或 `KB_RERANK_ENABLED=false` 以减少向量干扰；`LLAMA_INDEX_RERANK_ENABLED` 影响分层重排。
- **适用**：问题更依赖目录/章节定位（如“第三章资金管理”），或者向量召回易跑偏时。

## 取舍与调优提示
- **延迟优先**：用模式 1，关闭所有重排（`KB_RERANK_ENABLED=false`，`LLAMA_INDEX_RERANK_ENABLED=false`），缩短 `KNOWLEDGE_MAX_CONTEXT_PER_DOC`。
- **质量优先**：用模式 2，适度保留重排，但收紧 `RERANKER_TOP_N/RERANK_TOP_K`（3~4）与上下文截断。
- **混合轻量版**：模式 2 开启但重排关闭，或仅保留向量重排；适合兼顾质量/速度。
- **早停**：`EARLY_STOP_CONF` 决定高置信度是否直接用要点抽取/单轮总结，数值越低越容易走快路。

## 常用调参示例
- **极限快返（纯向量）**  
  ```
  SYSTEM__HYBRID_RETRIEVAL_ENABLED=false
  KB_RERANK_ENABLED=false
  LLAMA_INDEX_RERANK_ENABLED=false
  KNOWLEDGE_MAX_CONTEXT_PER_DOC=1500
  EARLY_STOP_CONF=0.70
  top_k=3  # 在调用处/代码里设置
  ```
- **质量优先（混合 + 轻量重排）**  
  ```
  SYSTEM__HYBRID_RETRIEVAL_ENABLED=true
  KB_RERANK_ENABLED=true         # DashScope 重排，RERANKER_TOP_N=3
  LLAMA_INDEX_RERANK_ENABLED=true
  RERANKER_TOP_N=3
  RERANK_TOP_K=3
  KNOWLEDGE_MAX_CONTEXT_PER_DOC=2000
  EARLY_STOP_CONF=0.80
  top_k=4
  ```
- **折中方案（混合，无重排）**  
  ```
  SYSTEM__HYBRID_RETRIEVAL_ENABLED=true
  KB_RERANK_ENABLED=false
  LLAMA_INDEX_RERANK_ENABLED=false
  KNOWLEDGE_MAX_CONTEXT_PER_DOC=1800
  EARLY_STOP_CONF=0.75
  top_k=3
  ```

## 默认 Top-K/截断的代码位置
- 向量召回 Top-K 默认 5：`app/agents/pipeline/knowledge_agent.py` 初始化参数；向量检索节点会把 Milvus/分层结果取 Top-K*2 再裁剪。
- 每篇上下文截断：环境变量 `KNOWLEDGE_MAX_CONTEXT_PER_DOC`，在知识总结前截断文档文本。
- 早停阈值：`EARLY_STOP_CONF`（读取到 `settings.system.early_stop_conf`），在 `KnowledgeAgent.answer` 中决定是否直接要点提取/单轮总结。
- 重排开关：`KB_RERANK_ENABLED`（向量重排），`LLAMA_INDEX_RERANK_ENABLED`（分层重排）；Top-N 配置 `RERANKER_TOP_N`、`RERANK_TOP_K`。
