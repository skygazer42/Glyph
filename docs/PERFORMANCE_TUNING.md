# 推理性能优化速记

目标：在保持答复质量的前提下，把单轮响应时间和 token 成本压到可接受范围。以下措施按“影响大/修改小”优先排序。

## 模型与调用次数
- 选用低延迟模型：首选 qwen-plus 或同级低时延模型；确保所有链路（AgentChat、Graph/LightRAG、Summarize）共用同一快速端点/模型，避免混用慢模型（如 qwen-max）。
- 减少工具迭代：`AGENTCHAT_MAX_TOOL_ITERATIONS=1`，`AGENTCHAT_REFLECT=false`，必要时关闭 AgentChat（`AGENTCHAT_ENABLED/TEAM_ENABLED=false`）回到单轮路由。
- 关闭不必要的意图/改写：若业务允许，可缓存或跳过改写/意图检测，减少额外 LLM 调用。

## 上下文与召回
- 截断单文档上下文：`KNOWLEDGE_MAX_CONTEXT_PER_DOC=1500~3000`，避免把长文大段送入模型。
- 降低召回 Top-K：向量/混合检索 `top_k=3~4`，减少拼接段数；必要时关闭混合检索：`SYSTEM__HYBRID_RETRIEVAL_ENABLED=false`。
- 调整早停阈值：`EARLY_STOP_CONF=0.70~0.80`，高置信度直接走要点抽取/单轮总结，跳过重排+长上下文。

## 重排与附加检索
- 关闭或收紧重排：`KB_RERANK_ENABLED=false`，`LLAMA_INDEX_RERANK_ENABLED=false`；若必须开启，设 `RERANKER_TOP_N/RERANK_TOP_K=3` 并使用低延迟后端或内网端点。
- Graph/LightRAG 模式：将 `LIGHTRAG_QUERY_MODE=local`/`naive`，关闭重排，减少多跳和额外 LLM 总结。

## 特殊链路
- Text2SQL：强制模式时绕过 AgentChat，直接调用 Text2SQLAgent；确认有有效的 `connection_id` 缓存，避免空转。
- Workflow/多模态：只在有附件或明确视觉需求时启用，其他场景走知识/规则路径。

## 配置清单（速度优先示例）
```
LLM_MODEL_NAME=qwen-plus
LLM_MODEL=qwen-plus
AGENTCHAT_REFLECT=false
AGENTCHAT_MAX_TOOL_ITERATIONS=1
SYSTEM__HYBRID_RETRIEVAL_ENABLED=false
KB_RERANK_ENABLED=false
LLAMA_INDEX_RERANK_ENABLED=false
KNOWLEDGE_MAX_CONTEXT_PER_DOC=1500
EARLY_STOP_CONF=0.70
LIGHTRAG_QUERY_MODE=local
```

## 观测与验证
- 启用性能 trace：确认 `performance.trace_latency` 为 true，查看 `metadata.performance_trace`、`agentchat_meta.duration_ms` 分段耗时。
- 对比前后耗时和 token：采样同一组问题，记录平均响应时间/平均 tokens，确认优化有效。
- 若仍慢：检查网络延迟（外部 API）、重排调用次数、Graph/Workflow 是否被误触发。
