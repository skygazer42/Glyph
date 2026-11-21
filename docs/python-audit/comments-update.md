# Python 类与函数注释补充

按 python-coding-guidelines 的 NAM-005、FUN-001/FUN-004，结合实际实现补充职责、返回形态、失败语义和资源生命周期。保留准确既有文档，不对简单构造、getter、测试辅助函数批量添加复述代码的说明。

本次修改 90 个 Python 文件，新增 432 处文档字符串，纠正 9 处说明；涉及 133 个类和 308 个函数/方法。

## 验证

- 204 个自有 Python 文件通过语法解析和 compile 检查；去文档字符串后的 AST、非文档代码 token 与任务开始版本一致。
- 90 个修改文件 Ruff 默认检查通过，git diff --check 通过。
- 独立只读交叉复核了新增注释中的职责、返回值、副作用、资源所有权与部分成功边界。
- 全量 pytest：810 通过、31 失败；31 项均在原 HEAD 源码上复现，当前独有失败为 0。原 HEAD 另外出现 1 项并发配置测试波动。
- 原有失败涉及工作区测试目录、Milvus 测试替身、旧导入合同和 SSE 事件循环；本次注释任务没有改动这些业务或测试逻辑。
- 沿用既有 mypy 参数检查 90 个修改文件：5 项错误均在原 HEAD 源码上复现，忽略位置变化后的错误内容完全一致，新增错误为 0。

## 范围与边界

重点说明会话持久化顺序、借入与自建资源的关闭归属、文档版本冲突和缓存写入、补贴公式/时间窗/输入单位、部分成功及数据库提交范围。FastAPI/Pydantic 的接口说明会随文档字符串更新；签名、权限判断、字段和执行逻辑没有改动。

未验证真实模型、数据库、解析云服务或生产部署。此前审核记录保留各自历史身份，未将其旧结果刷新成当前版本的验证。

## 修改文件

| 文件 | 新增 | 纠正 |
| --- | ---: | ---: |
| [api_server.py](F:/Glyph/api_server.py) | 0 | 2 |
| [app/agents/chatdb/db_service.py](F:/Glyph/app/agents/chatdb/db_service.py) | 2 | 0 |
| [app/agents/chatdb/domain_zh_gov.py](F:/Glyph/app/agents/chatdb/domain_zh_gov.py) | 3 | 0 |
| [app/agents/chatdb/text2sql_service.py](F:/Glyph/app/agents/chatdb/text2sql_service.py) | 1 | 0 |
| [app/agents/chatdb/text2sql_utils.py](F:/Glyph/app/agents/chatdb/text2sql_utils.py) | 1 | 0 |
| [app/agents/chatdb/visualization_recommender.py](F:/Glyph/app/agents/chatdb/visualization_recommender.py) | 1 | 0 |
| [app/agents/domain/policy_domain.py](F:/Glyph/app/agents/domain/policy_domain.py) | 3 | 0 |
| [app/agents/dsl_generator/dsl_extractor.py](F:/Glyph/app/agents/dsl_generator/dsl_extractor.py) | 4 | 0 |
| [app/agents/dsl_generator/pipeline.py](F:/Glyph/app/agents/dsl_generator/pipeline.py) | 2 | 0 |
| [app/agents/dsl_generator/rule_engine.py](F:/Glyph/app/agents/dsl_generator/rule_engine.py) | 1 | 0 |
| [app/agents/dsl_generator/subsidy_calculations.py](F:/Glyph/app/agents/dsl_generator/subsidy_calculations.py) | 7 | 0 |
| [app/agents/dsl_generator/template_registry.py](F:/Glyph/app/agents/dsl_generator/template_registry.py) | 4 | 0 |
| [app/agents/framework/base/base_agent.py](F:/Glyph/app/agents/framework/base/base_agent.py) | 1 | 0 |
| [app/agents/framework/base/factory.py](F:/Glyph/app/agents/framework/base/factory.py) | 1 | 0 |
| [app/agents/framework/common/autogen_memory_store.py](F:/Glyph/app/agents/framework/common/autogen_memory_store.py) | 6 | 0 |
| [app/agents/framework/common/model_client.py](F:/Glyph/app/agents/framework/common/model_client.py) | 1 | 0 |
| [app/agents/framework/common/session_manager.py](F:/Glyph/app/agents/framework/common/session_manager.py) | 15 | 0 |
| [app/agents/framework/common/session_store.py](F:/Glyph/app/agents/framework/common/session_store.py) | 4 | 0 |
| [app/agents/framework/coordination/session_manager.py](F:/Glyph/app/agents/framework/coordination/session_manager.py) | 2 | 0 |
| [app/agents/framework/core/agent_registry.py](F:/Glyph/app/agents/framework/core/agent_registry.py) | 1 | 0 |
| [app/agents/packs/answer_generator/node.py](F:/Glyph/app/agents/packs/answer_generator/node.py) | 1 | 0 |
| [app/agents/packs/clarifier/node.py](F:/Glyph/app/agents/packs/clarifier/node.py) | 2 | 0 |
| [app/agents/packs/graph_retriever/node.py](F:/Glyph/app/agents/packs/graph_retriever/node.py) | 6 | 0 |
| [app/agents/packs/intent_router/utils.py](F:/Glyph/app/agents/packs/intent_router/utils.py) | 3 | 0 |
| [app/agents/packs/policy_retriever/node.py](F:/Glyph/app/agents/packs/policy_retriever/node.py) | 1 | 0 |
| [app/agents/packs/policy_review/node.py](F:/Glyph/app/agents/packs/policy_review/node.py) | 1 | 0 |
| [app/agents/packs/question_builder/node.py](F:/Glyph/app/agents/packs/question_builder/node.py) | 1 | 0 |
| [app/agents/packs/vector_retriever/node.py](F:/Glyph/app/agents/packs/vector_retriever/node.py) | 4 | 0 |
| [app/agents/pipeline/dialog_agent.py](F:/Glyph/app/agents/pipeline/dialog_agent.py) | 3 | 0 |
| [app/agents/pipeline/graph_agent.py](F:/Glyph/app/agents/pipeline/graph_agent.py) | 2 | 0 |
| [app/agents/pipeline/knowledge_agent.py](F:/Glyph/app/agents/pipeline/knowledge_agent.py) | 6 | 0 |
| [app/agents/pipeline/rewrite_agent.py](F:/Glyph/app/agents/pipeline/rewrite_agent.py) | 2 | 0 |
| [app/agents/pipeline/rule_agent.py](F:/Glyph/app/agents/pipeline/rule_agent.py) | 5 | 0 |
| [app/agents/pipeline/text2sql_agent.py](F:/Glyph/app/agents/pipeline/text2sql_agent.py) | 2 | 0 |
| [app/agents/pipeline/workflow_agent.py](F:/Glyph/app/agents/pipeline/workflow_agent.py) | 3 | 0 |
| [app/agents/service/agent_service.py](F:/Glyph/app/agents/service/agent_service.py) | 17 | 0 |
| [app/agents/service/agentchat_router.py](F:/Glyph/app/agents/service/agentchat_router.py) | 5 | 0 |
| [app/agents/service/agentchat_team.py](F:/Glyph/app/agents/service/agentchat_team.py) | 5 | 0 |
| [app/agents/service/chat_history_store.py](F:/Glyph/app/agents/service/chat_history_store.py) | 8 | 0 |
| [app/agents/service/tools.py](F:/Glyph/app/agents/service/tools.py) | 18 | 0 |
| [app/api/endpoints/agent.py](F:/Glyph/app/api/endpoints/agent.py) | 4 | 0 |
| [app/api/endpoints/auth.py](F:/Glyph/app/api/endpoints/auth.py) | 7 | 0 |
| [app/api/endpoints/db_connections.py](F:/Glyph/app/api/endpoints/db_connections.py) | 1 | 0 |
| [app/api/endpoints/knowledge.py](F:/Glyph/app/api/endpoints/knowledge.py) | 9 | 2 |
| [app/api/endpoints/knowledge_graph.py](F:/Glyph/app/api/endpoints/knowledge_graph.py) | 13 | 0 |
| [app/api/endpoints/rule_preview.py](F:/Glyph/app/api/endpoints/rule_preview.py) | 3 | 0 |
| [app/api/endpoints/uploads.py](F:/Glyph/app/api/endpoints/uploads.py) | 7 | 0 |
| [app/api/schemas.py](F:/Glyph/app/api/schemas.py) | 3 | 0 |
| [app/core/access.py](F:/Glyph/app/core/access.py) | 7 | 0 |
| [app/core/auth.py](F:/Glyph/app/core/auth.py) | 9 | 0 |
| [app/core/logging_manager.py](F:/Glyph/app/core/logging_manager.py) | 9 | 1 |
| [app/domains/manager.py](F:/Glyph/app/domains/manager.py) | 1 | 0 |
| [app/domains/prompt_catalog.py](F:/Glyph/app/domains/prompt_catalog.py) | 3 | 0 |
| [app/knowledge/doc_enhanced.py](F:/Glyph/app/knowledge/doc_enhanced.py) | 8 | 0 |
| [app/knowledge/document_workspace.py](F:/Glyph/app/knowledge/document_workspace.py) | 18 | 2 |
| [app/knowledge/faq_responder.py](F:/Glyph/app/knowledge/faq_responder.py) | 3 | 0 |
| [app/knowledge/hierarchical_index.py](F:/Glyph/app/knowledge/hierarchical_index.py) | 4 | 0 |
| [app/knowledge/llamaindex_integration.py](F:/Glyph/app/knowledge/llamaindex_integration.py) | 7 | 0 |
| [app/knowledge/mineru_adapter.py](F:/Glyph/app/knowledge/mineru_adapter.py) | 8 | 0 |
| [app/knowledge/rerank.py](F:/Glyph/app/knowledge/rerank.py) | 11 | 0 |
| [app/knowledge/service.py](F:/Glyph/app/knowledge/service.py) | 3 | 0 |
| [app/main.py](F:/Glyph/app/main.py) | 11 | 0 |
| [app/models/base.py](F:/Glyph/app/models/base.py) | 1 | 0 |
| [app/models/database.py](F:/Glyph/app/models/database.py) | 5 | 0 |
| [app/models/policy.py](F:/Glyph/app/models/policy.py) | 1 | 0 |
| [app/persistence/crud/base.py](F:/Glyph/app/persistence/crud/base.py) | 7 | 1 |
| [app/persistence/crud/chat_history.py](F:/Glyph/app/persistence/crud/chat_history.py) | 3 | 0 |
| [app/persistence/crud/db_connection.py](F:/Glyph/app/persistence/crud/db_connection.py) | 4 | 0 |
| [app/persistence/crud/schema_metadata.py](F:/Glyph/app/persistence/crud/schema_metadata.py) | 16 | 0 |
| [app/persistence/db/access.py](F:/Glyph/app/persistence/db/access.py) | 11 | 0 |
| [app/persistence/db/init_db.py](F:/Glyph/app/persistence/db/init_db.py) | 2 | 0 |
| [app/persistence/db/schema_introspector.py](F:/Glyph/app/persistence/db/schema_introspector.py) | 1 | 0 |
| [app/persistence/db/session.py](F:/Glyph/app/persistence/db/session.py) | 1 | 0 |
| [app/schemas/chat_history.py](F:/Glyph/app/schemas/chat_history.py) | 5 | 0 |
| [app/schemas/database.py](F:/Glyph/app/schemas/database.py) | 15 | 0 |
| [app/schemas/knowledge.py](F:/Glyph/app/schemas/knowledge.py) | 12 | 0 |
| [app/schemas/text2sql.py](F:/Glyph/app/schemas/text2sql.py) | 8 | 0 |
| [scripts/create_tables.py](F:/Glyph/scripts/create_tables.py) | 1 | 0 |
| [scripts/embed_documents.py](F:/Glyph/scripts/embed_documents.py) | 0 | 1 |
| [scripts/embed_process_documents.py](F:/Glyph/scripts/embed_process_documents.py) | 2 | 0 |
| [scripts/import_data.py](F:/Glyph/scripts/import_data.py) | 4 | 0 |
| [scripts/seed_lightrag.py](F:/Glyph/scripts/seed_lightrag.py) | 3 | 0 |
| [scripts/seed_mysql_text2sql.py](F:/Glyph/scripts/seed_mysql_text2sql.py) | 10 | 0 |
| [scripts/sync_text2sql_schema.py](F:/Glyph/scripts/sync_text2sql_schema.py) | 1 | 0 |
| [examples/autogen_agent_tools.py](F:/Glyph/examples/autogen_agent_tools.py) | 1 | 0 |
| [examples/autogen_streaming.py](F:/Glyph/examples/autogen_streaming.py) | 1 | 0 |
| [examples/autogen_team_tools.py](F:/Glyph/examples/autogen_team_tools.py) | 1 | 0 |
| [examples/r2r/base.py](F:/Glyph/examples/r2r/base.py) | 7 | 0 |
| [examples/r2r/rag.py](F:/Glyph/examples/r2r/rag.py) | 2 | 0 |
| [examples/r2r/research.py](F:/Glyph/examples/r2r/research.py) | 3 | 0 |
