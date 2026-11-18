# Python 逐文件、逐定义审查

本轮按用户点名的 python-coding-guidelines 审查项目内全部第一方 Python 源码，包括应用、CLI、种子数据、测试、示例，以及被 Git 忽略的视觉验证夹具。先读取实现和调用方，再决定修改或保留；不是按扫描命中数推断完成。

当前覆盖 **197 个文件、439 个类、2100 个具名函数/方法、208 个匿名回调，共 2747 个定义**。其中 43 个文件没有定义，也逐一检查了包职责、显式导出和导入副作用。当前定义均有审查记录，未记录为 pending 的定义数为 0。

**reviewed 只表示源码审查已完成，不表示测试通过。** 按用户“暂时不测试”的要求，本轮没有执行 pytest、lint、构建、应用编译/导入、业务脚本、模型/数据库请求、服务启动或浏览器验证。AST 仅用于列出定义、定位当前行号、关联已有决策；没有通过导入项目代码清点。仅为确认已有框架 API，读取了官方文档和固定版本源码。

## 审查记录

[完整逐定义索引](function-review.json) 包含每个定义的文件、当前位置、参数/装饰器、修改或保留理由与源文件 SHA-256。动态 type/exec、字典操作和匿名函数也随其所属实现读取；不将 AST 清单本身当成审查。

| 分组记录 | 文件 | 当前定义 |
| --- | ---: | ---: |
| [Agent 框架与能力包](review-agent-runtime.json) | 53 | 525 |
| [Text2SQL Agent 与 SQL 工具](review-chatdb.json) | 14 | 100 |
| [政策提取、模板、DSL 运行与保存](review-dsl.json) | 10 | 134 |
| [文档解析、索引、检索和工作区](review-knowledge.json) | 15 | 254 |
| [入口、API、配置、模型、持久化、业务编排与视觉夹具](review-root.json) | 68 | 574 |
| [运维与 CLI](review-scripts.json) | 11 | 54 |
| [测试、示例与种子生成](review-tests-examples.json) | 26 | 1106 |

各记录也保存删除/重命名的定义。完整索引以当前源码为准，不把退休定义计为漏项。第一轮目录迁移说明见 [Python 代码与目录约定](../PYTHON_STRUCTURE.md)。

## 主要处理

| 规则与级别 | 位置/问题 | 已落地的处理 |
| --- | --- | --- |
| CLS-001/006（推荐）、FUN-003（强制） | 无实例状态的 DSL、对话、澄清、SQL 展示和示例包装；常量 getter、无使用参数 | 改为模块函数/常量，删除纯转发与占位实现；实际客户端、词典、缓存、状态机及框架继承保留。 |
| FUN-002（推荐）、DES-001（强制） | AgentService 第二次 Team/Router 调度不可达；禁止回退分支缺少 route | 清理重复支路、保持现有模式，并让失败路径拥有明确结构化路由。 |
| NAM-001/003（强制）、NAM-002（推荐） | 模糊动作名、缩写属性、分散模型与反向导入 | 按实际所有者显式导入，职责命名；同一数据库维护点合并，配置、脚本和示例归位，调用方随定义更新。 |
| CLS-003、DB-002（强制） | SQL 工具忽略本请求选库；缓存超时会删历史 | 连接 ID 放入当前请求上下文；只由用户显式删除持久化会话，超时只逐出内存。 |
| DB-003、ERR-001（强制） | 历史查询隐含只读前100条；快照外键阻止会话删除 | 获取真实最新历史，补齐 ORM 快照归属/删除级联；数据库列、表名和外键定义没有迁移。 |
| DAT-003/004、PYD-001/004（强制） | bool 被变为数值，小数被截成整数，NaN/Inf，优惠类型/封顶校验丢失 | 真实边界校验，保留零/False/None各自语义；优惠方式、cap/name、目录提示及模板保持同一合同。 |
| RES/ASY、ERR（强制） | 文档/图片/HTTP/流/CLI资源退出与不透明错误 | 保留并修复持有方清理、取消传播、线程边界、严格解码和配置前置；API 附件路径在读取前验证归属。 |
| DB-001（强制） | 模型 SQL 可绕过共用校验，INTO 写入与跨方言转换 | 执行前使用同一单条SELECT校验，拒绝INTO写入，MySQL/PostgreSQL按实际连接生成与转换。 |
| DES-004/007（强制） | 模型 YAML 选项不生效；最低依赖与已有接口不符 | 首次创建客户端前应用实际配置；依赖声明匹配已有 Query 模型及 GraphFlow 使用，不安装或升级环境。 |
| ERR-001、DB-003（强制） | 导入默认清库、随机向量、合成数据伪装人工核验、重建最后一批索引 | 显式--truncate才重置，DML提交/回滚；真实嵌入和稳定upsert；合成数据未核验，向量批次追加与全量分级快照分开。 |

## 必须保留的边界

- FastAPI、AutoGen、日志、ORM、fixture、装饰器与生成器的参数/返回/async/yield 属于真实协议，不能按行数或是否读取 self 随意删除。Pydantic/Enum/dataclass 也不因无业务方法变成普通字典。
- 现有两套 HTTP 入口和真实提供方模式继续保留，不在命名整理中合并不同接口或猜测新的恢复算法。
- 旧 Python 内部导入/脚本名字已迁移。数据库列 password_encrypted 仍沿用历史明文凭据存储合同；本轮未生成密钥或迁移数据，字段名不能被理解为已完成加密。
- 当前 Milvus 索引没有地区字段，地区只参与文本检索，不能承诺严格地区过滤；没有擅加数据库列或迁移。
- 分级索引是全量快照，不是增量存储。向量追加路径已分开；LlamaIndex 构建器与检索器的模型装配仍有不同入口，真实提供方/SDK组合尚未在本轮验证，没有猜测新的集成算法。
- 存量规则存在重复 rule_id；未按代码风格删政策文件或猜测哪个版本应当生效。重复记录的选择/清理属于数据治理边界。
- R2R 参考依赖本仓库没有的 core/shared 运行环境。语言协议和外部序列化没有在缺少对应 SDK 时被机械重写。
- 默认种子导入保留已有数据；主动--truncate会独立提交清空。后续插入回滚不能恢复清空前数据。历史 Docker 报告继续显式标记 executed=False，不代表本轮真实检查。

## 当前文件清单

| 文件 | 类 | 具名函数/方法 | 匿名回调 | 记录 |
| --- | ---: | ---: | ---: | --- |
| [.oil-ui/glyph-modern-implementation/qa_api.py](../../.oil-ui/glyph-modern-implementation/qa_api.py) | 0 | 25 | 0 | [review-root.json](review-root.json) |
| [api_server.py](../../api_server.py) | 1 | 3 | 0 | [review-root.json](review-root.json) |
| [app/__init__.py](../../app/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/agents/__init__.py](../../app/agents/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/agents/chatdb/__init__.py](../../app/agents/chatdb/__init__.py) | 0 | 0 | 0 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/base.py](../../app/agents/chatdb/base.py) | 2 | 13 | 0 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/db_service.py](../../app/agents/chatdb/db_service.py) | 1 | 3 | 0 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/domain_zh_gov.py](../../app/agents/chatdb/domain_zh_gov.py) | 1 | 8 | 0 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/factory.py](../../app/agents/chatdb/factory.py) | 1 | 9 | 8 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/hybrid_sql_generator.py](../../app/agents/chatdb/hybrid_sql_generator.py) | 1 | 2 | 0 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/query_analyzer.py](../../app/agents/chatdb/query_analyzer.py) | 1 | 3 | 0 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/schema_retriever.py](../../app/agents/chatdb/schema_retriever.py) | 1 | 3 | 0 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/sql_executor.py](../../app/agents/chatdb/sql_executor.py) | 1 | 3 | 0 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/sql_explainer.py](../../app/agents/chatdb/sql_explainer.py) | 1 | 3 | 0 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/sql_generator.py](../../app/agents/chatdb/sql_generator.py) | 1 | 2 | 0 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/text2sql_service.py](../../app/agents/chatdb/text2sql_service.py) | 0 | 5 | 0 | [review-root.json](review-root.json) |
| [app/agents/chatdb/text2sql_utils.py](../../app/agents/chatdb/text2sql_utils.py) | 4 | 17 | 2 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/types.py](../../app/agents/chatdb/types.py) | 3 | 0 | 0 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/chatdb/visualization_recommender.py](../../app/agents/chatdb/visualization_recommender.py) | 2 | 4 | 0 | [review-chatdb.json](review-chatdb.json) |
| [app/agents/domain/__init__.py](../../app/agents/domain/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/agents/domain/policy_domain.py](../../app/agents/domain/policy_domain.py) | 2 | 6 | 0 | [review-root.json](review-root.json) |
| [app/agents/dsl_generator/__init__.py](../../app/agents/dsl_generator/__init__.py) | 0 | 0 | 0 | [review-dsl.json](review-dsl.json) |
| [app/agents/dsl_generator/document_parser.py](../../app/agents/dsl_generator/document_parser.py) | 1 | 10 | 0 | [review-dsl.json](review-dsl.json) |
| [app/agents/dsl_generator/dsl_extractor.py](../../app/agents/dsl_generator/dsl_extractor.py) | 5 | 17 | 0 | [review-dsl.json](review-dsl.json) |
| [app/agents/dsl_generator/dsl_generator.py](../../app/agents/dsl_generator/dsl_generator.py) | 1 | 13 | 0 | [review-dsl.json](review-dsl.json) |
| [app/agents/dsl_generator/dsl_generator_domain.py](../../app/agents/dsl_generator/dsl_generator_domain.py) | 1 | 17 | 0 | [review-dsl.json](review-dsl.json) |
| [app/agents/dsl_generator/main.py](../../app/agents/dsl_generator/main.py) | 0 | 9 | 0 | [review-dsl.json](review-dsl.json) |
| [app/agents/dsl_generator/pipeline.py](../../app/agents/dsl_generator/pipeline.py) | 1 | 8 | 0 | [review-dsl.json](review-dsl.json) |
| [app/agents/dsl_generator/rule_engine.py](../../app/agents/dsl_generator/rule_engine.py) | 1 | 17 | 2 | [review-dsl.json](review-dsl.json) |
| [app/agents/dsl_generator/subsidy_calculations.py](../../app/agents/dsl_generator/subsidy_calculations.py) | 0 | 10 | 0 | [review-dsl.json](review-dsl.json) |
| [app/agents/dsl_generator/template_registry.py](../../app/agents/dsl_generator/template_registry.py) | 2 | 19 | 0 | [review-dsl.json](review-dsl.json) |
| [app/agents/framework/__init__.py](../../app/agents/framework/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/base/__init__.py](../../app/agents/framework/base/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/base/base_agent.py](../../app/agents/framework/base/base_agent.py) | 4 | 29 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/base/factory.py](../../app/agents/framework/base/factory.py) | 2 | 9 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/base/types.py](../../app/agents/framework/base/types.py) | 8 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/common/__init__.py](../../app/agents/framework/common/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/common/autogen_memory_store.py](../../app/agents/framework/common/autogen_memory_store.py) | 0 | 8 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/common/embedding_manager.py](../../app/agents/framework/common/embedding_manager.py) | 1 | 8 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/common/model_client.py](../../app/agents/framework/common/model_client.py) | 0 | 2 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/common/session_manager.py](../../app/agents/framework/common/session_manager.py) | 2 | 21 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/common/session_store.py](../../app/agents/framework/common/session_store.py) | 0 | 4 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/coordination/__init__.py](../../app/agents/framework/coordination/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/coordination/coordinator.py](../../app/agents/framework/coordination/coordinator.py) | 1 | 4 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/coordination/session_manager.py](../../app/agents/framework/coordination/session_manager.py) | 2 | 17 | 2 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/core/__init__.py](../../app/agents/framework/core/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/core/agent_base.py](../../app/agents/framework/core/agent_base.py) | 2 | 12 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/core/agent_master.py](../../app/agents/framework/core/agent_master.py) | 1 | 20 | 3 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/core/agent_registry.py](../../app/agents/framework/core/agent_registry.py) | 2 | 18 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/core/message_bus.py](../../app/agents/framework/core/message_bus.py) | 2 | 20 | 1 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/core/orchestrator.py](../../app/agents/framework/core/orchestrator.py) | 4 | 19 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/models/__init__.py](../../app/agents/framework/models/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/models/base.py](../../app/agents/framework/models/base.py) | 7 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/monitoring/monitor.py](../../app/agents/framework/monitoring/monitor.py) | 9 | 34 | 1 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/framework/security/gateway.py](../../app/agents/framework/security/gateway.py) | 14 | 31 | 2 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/__init__.py](../../app/agents/packs/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/answer_generator/__init__.py](../../app/agents/packs/answer_generator/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/answer_generator/node.py](../../app/agents/packs/answer_generator/node.py) | 1 | 20 | 1 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/answer_generator/prompt.py](../../app/agents/packs/answer_generator/prompt.py) | 0 | 1 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/chat_agent/__init__.py](../../app/agents/packs/chat_agent/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/chat_agent/node.py](../../app/agents/packs/chat_agent/node.py) | 2 | 5 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/clarifier/__init__.py](../../app/agents/packs/clarifier/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/clarifier/node.py](../../app/agents/packs/clarifier/node.py) | 1 | 2 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/graph_retriever/__init__.py](../../app/agents/packs/graph_retriever/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/graph_retriever/node.py](../../app/agents/packs/graph_retriever/node.py) | 4 | 19 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/intent_router/__init__.py](../../app/agents/packs/intent_router/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/intent_router/node.py](../../app/agents/packs/intent_router/node.py) | 2 | 17 | 1 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/intent_router/prompt.py](../../app/agents/packs/intent_router/prompt.py) | 0 | 1 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/intent_router/utils.py](../../app/agents/packs/intent_router/utils.py) | 2 | 4 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/policy_analysis/__init__.py](../../app/agents/packs/policy_analysis/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/policy_analysis/node.py](../../app/agents/packs/policy_analysis/node.py) | 2 | 18 | 1 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/policy_analysis/prompt.py](../../app/agents/packs/policy_analysis/prompt.py) | 0 | 1 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/policy_comparator/__init__.py](../../app/agents/packs/policy_comparator/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/policy_comparator/node.py](../../app/agents/packs/policy_comparator/node.py) | 2 | 15 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/policy_retriever/__init__.py](../../app/agents/packs/policy_retriever/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/policy_retriever/node.py](../../app/agents/packs/policy_retriever/node.py) | 3 | 10 | 1 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/policy_review/__init__.py](../../app/agents/packs/policy_review/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/policy_review/node.py](../../app/agents/packs/policy_review/node.py) | 3 | 10 | 1 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/query_analyzer/__init__.py](../../app/agents/packs/query_analyzer/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/query_analyzer/node.py](../../app/agents/packs/query_analyzer/node.py) | 1 | 13 | 1 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/question_builder/__init__.py](../../app/agents/packs/question_builder/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/question_builder/node.py](../../app/agents/packs/question_builder/node.py) | 2 | 8 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/vector_retriever/__init__.py](../../app/agents/packs/vector_retriever/__init__.py) | 0 | 0 | 0 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/packs/vector_retriever/node.py](../../app/agents/packs/vector_retriever/node.py) | 1 | 22 | 1 | [review-agent-runtime.json](review-agent-runtime.json) |
| [app/agents/pipeline/__init__.py](../../app/agents/pipeline/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/agents/pipeline/dialog_agent.py](../../app/agents/pipeline/dialog_agent.py) | 0 | 5 | 0 | [review-root.json](review-root.json) |
| [app/agents/pipeline/graph_agent.py](../../app/agents/pipeline/graph_agent.py) | 1 | 8 | 0 | [review-root.json](review-root.json) |
| [app/agents/pipeline/knowledge_agent.py](../../app/agents/pipeline/knowledge_agent.py) | 1 | 16 | 0 | [review-root.json](review-root.json) |
| [app/agents/pipeline/rewrite_agent.py](../../app/agents/pipeline/rewrite_agent.py) | 2 | 11 | 0 | [review-root.json](review-root.json) |
| [app/agents/pipeline/rule_agent.py](../../app/agents/pipeline/rule_agent.py) | 2 | 10 | 0 | [review-root.json](review-root.json) |
| [app/agents/pipeline/text2sql_agent.py](../../app/agents/pipeline/text2sql_agent.py) | 0 | 2 | 0 | [review-root.json](review-root.json) |
| [app/agents/pipeline/workflow_agent.py](../../app/agents/pipeline/workflow_agent.py) | 1 | 10 | 0 | [review-root.json](review-root.json) |
| [app/agents/service/__init__.py](../../app/agents/service/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/agents/service/agent_service.py](../../app/agents/service/agent_service.py) | 4 | 48 | 0 | [review-root.json](review-root.json) |
| [app/agents/service/agentchat_router.py](../../app/agents/service/agentchat_router.py) | 1 | 6 | 0 | [review-root.json](review-root.json) |
| [app/agents/service/agentchat_team.py](../../app/agents/service/agentchat_team.py) | 1 | 6 | 1 | [review-root.json](review-root.json) |
| [app/agents/service/chat_history_store.py](../../app/agents/service/chat_history_store.py) | 1 | 10 | 0 | [review-root.json](review-root.json) |
| [app/agents/service/tools.py](../../app/agents/service/tools.py) | 10 | 34 | 1 | [review-root.json](review-root.json) |
| [app/api/__init__.py](../../app/api/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/api/deps.py](../../app/api/deps.py) | 0 | 9 | 0 | [review-root.json](review-root.json) |
| [app/api/endpoints/__init__.py](../../app/api/endpoints/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/api/endpoints/agent.py](../../app/api/endpoints/agent.py) | 0 | 8 | 0 | [review-root.json](review-root.json) |
| [app/api/endpoints/db_connections.py](../../app/api/endpoints/db_connections.py) | 1 | 2 | 0 | [review-root.json](review-root.json) |
| [app/api/endpoints/dsl.py](../../app/api/endpoints/dsl.py) | 0 | 5 | 0 | [review-root.json](review-root.json) |
| [app/api/endpoints/knowledge.py](../../app/api/endpoints/knowledge.py) | 0 | 25 | 0 | [review-root.json](review-root.json) |
| [app/api/endpoints/knowledge_graph.py](../../app/api/endpoints/knowledge_graph.py) | 4 | 3 | 0 | [review-root.json](review-root.json) |
| [app/api/endpoints/uploads.py](../../app/api/endpoints/uploads.py) | 0 | 2 | 0 | [review-root.json](review-root.json) |
| [app/api/schemas.py](../../app/api/schemas.py) | 22 | 0 | 0 | [review-root.json](review-root.json) |
| [app/config/__init__.py](../../app/config/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/config/agent_config.py](../../app/config/agent_config.py) | 9 | 3 | 0 | [review-root.json](review-root.json) |
| [app/config/app_config.py](../../app/config/app_config.py) | 12 | 5 | 1 | [review-root.json](review-root.json) |
| [app/core/__init__.py](../../app/core/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/core/auth.py](../../app/core/auth.py) | 2 | 8 | 0 | [review-root.json](review-root.json) |
| [app/core/llms.py](../../app/core/llms.py) | 0 | 1 | 0 | [review-root.json](review-root.json) |
| [app/core/logging_manager.py](../../app/core/logging_manager.py) | 2 | 16 | 0 | [review-root.json](review-root.json) |
| [app/core/security.py](../../app/core/security.py) | 0 | 3 | 0 | [review-root.json](review-root.json) |
| [app/domains/__init__.py](../../app/domains/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/domains/manager.py](../../app/domains/manager.py) | 1 | 10 | 0 | [review-root.json](review-root.json) |
| [app/domains/prompt_catalog.py](../../app/domains/prompt_catalog.py) | 0 | 3 | 0 | [review-root.json](review-root.json) |
| [app/domains/schemas.py](../../app/domains/schemas.py) | 11 | 1 | 0 | [review-root.json](review-root.json) |
| [app/knowledge/__init__.py](../../app/knowledge/__init__.py) | 0 | 0 | 0 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/doc_enhanced.py](../../app/knowledge/doc_enhanced.py) | 7 | 21 | 0 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/document_loader.py](../../app/knowledge/document_loader.py) | 1 | 20 | 0 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/document_workspace.py](../../app/knowledge/document_workspace.py) | 1 | 21 | 0 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/faq_responder.py](../../app/knowledge/faq_responder.py) | 2 | 4 | 0 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/hierarchical_index.py](../../app/knowledge/hierarchical_index.py) | 5 | 30 | 1 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/hybrid_retrieval.py](../../app/knowledge/hybrid_retrieval.py) | 1 | 7 | 2 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/image_retrieval.py](../../app/knowledge/image_retrieval.py) | 3 | 13 | 0 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/llamaindex_hybrid_retrieval.py](../../app/knowledge/llamaindex_hybrid_retrieval.py) | 1 | 11 | 0 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/llamaindex_integration.py](../../app/knowledge/llamaindex_integration.py) | 2 | 15 | 0 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/milvus.py](../../app/knowledge/milvus.py) | 4 | 15 | 0 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/mineru_adapter.py](../../app/knowledge/mineru_adapter.py) | 8 | 21 | 0 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/rapid_ocr_processor.py](../../app/knowledge/rapid_ocr_processor.py) | 2 | 12 | 0 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/rerank.py](../../app/knowledge/rerank.py) | 5 | 9 | 2 | [review-knowledge.json](review-knowledge.json) |
| [app/knowledge/service.py](../../app/knowledge/service.py) | 1 | 6 | 1 | [review-knowledge.json](review-knowledge.json) |
| [app/main.py](../../app/main.py) | 7 | 7 | 0 | [review-root.json](review-root.json) |
| [app/models/__init__.py](../../app/models/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/models/base.py](../../app/models/base.py) | 1 | 1 | 0 | [review-root.json](review-root.json) |
| [app/models/chat_history.py](../../app/models/chat_history.py) | 3 | 0 | 0 | [review-root.json](review-root.json) |
| [app/models/database.py](../../app/models/database.py) | 5 | 0 | 0 | [review-root.json](review-root.json) |
| [app/models/policy.py](../../app/models/policy.py) | 17 | 2 | 0 | [review-root.json](review-root.json) |
| [app/persistence/__init__.py](../../app/persistence/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/persistence/crud/__init__.py](../../app/persistence/crud/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/persistence/crud/base.py](../../app/persistence/crud/base.py) | 1 | 7 | 0 | [review-root.json](review-root.json) |
| [app/persistence/crud/chat_history.py](../../app/persistence/crud/chat_history.py) | 3 | 7 | 0 | [review-root.json](review-root.json) |
| [app/persistence/crud/db_connection.py](../../app/persistence/crud/db_connection.py) | 1 | 5 | 0 | [review-root.json](review-root.json) |
| [app/persistence/crud/schema_metadata.py](../../app/persistence/crud/schema_metadata.py) | 4 | 12 | 0 | [review-root.json](review-root.json) |
| [app/persistence/db/__init__.py](../../app/persistence/db/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/persistence/db/access.py](../../app/persistence/db/access.py) | 1 | 22 | 0 | [review-root.json](review-root.json) |
| [app/persistence/db/init_db.py](../../app/persistence/db/init_db.py) | 0 | 2 | 0 | [review-root.json](review-root.json) |
| [app/persistence/db/registry.py](../../app/persistence/db/registry.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/persistence/db/schema_introspector.py](../../app/persistence/db/schema_introspector.py) | 1 | 5 | 0 | [review-root.json](review-root.json) |
| [app/persistence/db/session.py](../../app/persistence/db/session.py) | 0 | 1 | 0 | [review-root.json](review-root.json) |
| [app/schemas/__init__.py](../../app/schemas/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/schemas/chat_history.py](../../app/schemas/chat_history.py) | 5 | 0 | 0 | [review-root.json](review-root.json) |
| [app/schemas/database.py](../../app/schemas/database.py) | 15 | 0 | 0 | [review-root.json](review-root.json) |
| [app/schemas/knowledge.py](../../app/schemas/knowledge.py) | 25 | 1 | 0 | [review-root.json](review-root.json) |
| [app/schemas/text2sql.py](../../app/schemas/text2sql.py) | 9 | 0 | 0 | [review-root.json](review-root.json) |
| [app/utils/__init__.py](../../app/utils/__init__.py) | 0 | 0 | 0 | [review-root.json](review-root.json) |
| [app/utils/lifecycle.py](../../app/utils/lifecycle.py) | 0 | 1 | 0 | [review-root.json](review-root.json) |
| [examples/__init__.py](../../examples/__init__.py) | 0 | 0 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/ag_builder.py](../../examples/ag_builder.py) | 6 | 22 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/ag_prompt.py](../../examples/ag_prompt.py) | 0 | 0 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/ag_workflow.py](../../examples/ag_workflow.py) | 2 | 14 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/autogen_agent_tools.py](../../examples/autogen_agent_tools.py) | 0 | 1 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/autogen_streaming.py](../../examples/autogen_streaming.py) | 0 | 2 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/autogen_team_tools.py](../../examples/autogen_team_tools.py) | 0 | 1 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/enterprise_agents.py](../../examples/enterprise_agents.py) | 0 | 1 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/image_search_demo.py](../../examples/image_search_demo.py) | 0 | 1 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/mineru_demo.py](../../examples/mineru_demo.py) | 0 | 6 | 2 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/r2r/__init__.py](../../examples/r2r/__init__.py) | 0 | 0 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/r2r/base.py](../../examples/r2r/base.py) | 5 | 21 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/r2r/rag.py](../../examples/r2r/rag.py) | 5 | 7 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [examples/r2r/research.py](../../examples/r2r/research.py) | 5 | 16 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [resources/database/seed_data/generate_qa_data.py](../../resources/database/seed_data/generate_qa_data.py) | 0 | 1 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [resources/database/seed_data/policy_qa_seed.py](../../resources/database/seed_data/policy_qa_seed.py) | 0 | 1 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [scripts/__init__.py](../../scripts/__init__.py) | 0 | 0 | 0 | [review-scripts.json](review-scripts.json) |
| [scripts/create_tables.py](../../scripts/create_tables.py) | 0 | 1 | 0 | [review-scripts.json](review-scripts.json) |
| [scripts/embed_documents.py](../../scripts/embed_documents.py) | 0 | 3 | 0 | [review-scripts.json](review-scripts.json) |
| [scripts/embed_process_documents.py](../../scripts/embed_process_documents.py) | 0 | 4 | 1 | [review-scripts.json](review-scripts.json) |
| [scripts/import_data.py](../../scripts/import_data.py) | 1 | 12 | 1 | [review-scripts.json](review-scripts.json) |
| [scripts/init_milvus.py](../../scripts/init_milvus.py) | 0 | 1 | 0 | [review-scripts.json](review-scripts.json) |
| [scripts/render_docker_report.py](../../scripts/render_docker_report.py) | 0 | 1 | 0 | [review-scripts.json](review-scripts.json) |
| [scripts/seed_lightrag.py](../../scripts/seed_lightrag.py) | 0 | 5 | 1 | [review-scripts.json](review-scripts.json) |
| [scripts/seed_mysql_text2sql.py](../../scripts/seed_mysql_text2sql.py) | 1 | 15 | 0 | [review-scripts.json](review-scripts.json) |
| [scripts/sync_text2sql_schema.py](../../scripts/sync_text2sql_schema.py) | 0 | 1 | 0 | [review-scripts.json](review-scripts.json) |
| [scripts/unified_cli.py](../../scripts/unified_cli.py) | 0 | 5 | 1 | [review-scripts.json](review-scripts.json) |
| [tests/test_knowledge_workspace.py](../../tests/test_knowledge_workspace.py) | 2 | 54 | 7 | [review-tests-examples.json](review-tests-examples.json) |
| [tests/test_package_imports.py](../../tests/test_package_imports.py) | 0 | 1 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [tests/test_python_guidelines_api_config.py](../../tests/test_python_guidelines_api_config.py) | 3 | 74 | 20 | [review-tests-examples.json](review-tests-examples.json) |
| [tests/test_python_guidelines_integration.py](../../tests/test_python_guidelines_integration.py) | 0 | 4 | 0 | [review-tests-examples.json](review-tests-examples.json) |
| [tests/test_python_guidelines_knowledge_pipeline.py](../../tests/test_python_guidelines_knowledge_pipeline.py) | 17 | 162 | 53 | [review-tests-examples.json](review-tests-examples.json) |
| [tests/test_python_guidelines_packs_dsl.py](../../tests/test_python_guidelines_packs_dsl.py) | 6 | 115 | 26 | [review-tests-examples.json](review-tests-examples.json) |
| [tests/test_python_guidelines_persistence_chatdb.py](../../tests/test_python_guidelines_persistence_chatdb.py) | 4 | 65 | 17 | [review-tests-examples.json](review-tests-examples.json) |
| [tests/test_python_guidelines_runtime.py](../../tests/test_python_guidelines_runtime.py) | 8 | 149 | 17 | [review-tests-examples.json](review-tests-examples.json) |
| [tests/test_python_guidelines_runtime_monitoring.py](../../tests/test_python_guidelines_runtime_monitoring.py) | 0 | 20 | 4 | [review-tests-examples.json](review-tests-examples.json) |
| [tests/test_python_guidelines_tooling.py](../../tests/test_python_guidelines_tooling.py) | 23 | 115 | 21 | [review-tests-examples.json](review-tests-examples.json) |
