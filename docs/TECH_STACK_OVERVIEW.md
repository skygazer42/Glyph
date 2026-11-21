# Glyph 技术栈与回答链路

本文对应当前仓库代码，说明实际入口、默认配置与可选能力。版本来自依赖声明或容器配置，实际安装版本以运行环境为准，服务兼容性需通过对应环境联调确认。

## 组件与版本声明

| 层次 | 依赖与版本声明 | 实际职责 |
| --- | --- | --- |
| Python 服务 | 项目使用 Python 3.10；FastAPI `>=0.115.0`、Uvicorn `>=0.30.0` | REST API、认证、会话和 SSE。 |
| 问答事件协议 | `ag-ui-protocol >=1.0.0,<2.0`；Vue 使用原生 fetch 读取 SSE | 标准运行、步骤、工具和文本事件，以及来源与最终答复的业务事件。 |
| 数据契约与配置 | Pydantic `>=2.9.0`、pydantic-settings `>=2.6.0` | 请求响应模型、环境配置与处理参数校验。 |
| 模型与智能体 | AutoGen Core / AgentChat / Ext `>=0.6.0`、OpenAI SDK `>=1.50.0` | 模型客户端、工具调用、对话编排与模型上下文。 |
| 关系存储 | SQLAlchemy `>=2.0.0`、PyMySQL；Compose 使用 MySQL `8.0` | ORM、业务数据、连接元数据与聊天记录。 |
| 向量检索 | PyMilvus `>=2.4.0`；Compose 镜像为 Milvus `v2.3.3` | 保存向量与资料元数据，执行过滤和相似度检索。SDK 与服务版本分别声明，升级时需要核对兼容性。 |
| 解析与索引 | LlamaIndex `>=0.10.0`、PyMuPDF、python-docx；MinerU 为外部服务 | 文档解析、可选分级索引及 PDF 页图。 |
| 图谱 | `lightrag-hku`，未固定版本 | 图谱构建、查询与原生工作目录存储，输出 GraphML 供页面读取。 |
| 前端 | Vue `^3.4.0`、Vite `^5.0.0`、Vue Router `^4.2.5`、Pinia `^2.1.7`、Element Plus `^2.5.0` | 咨询、工作人员后台、知识库与规则界面。 |
| 图可视化 | AntV G6 `^5.1.1` | 当前知识图谱页的搜索、子图、邻居展开与视图操作。 |
| 开发辅助服务 | Compose 使用 Redis `7-alpine`、etcd `v3.5.5` 与 MinIO | Redis 为相关功能的可选基础服务，etcd / MinIO 支撑 Milvus。Redis 不承担当前模型记忆持久化。 |

完整声明见 [requirements.txt](../requirements.txt)、[package.json](../web/package.json) 和 [开发 Compose](../docker-compose.dev.yaml)。依赖清单还保留 CodeMirror、D3、X6、ECharts 等包；当前页面使用情况以具体源码导入为准，不能仅因安装了某个库就宣称整项产品能力已实现。

## 服务入口与权限

- [api_server.py](../api_server.py) 装配前端使用的 `/api/auth`、`/api/agent`、知识库、图谱、DSL、附件和数据库连接接口。
- [app/main.py](../app/main.py) 保留 `/query` 等另一套已有协议，不与完整 API 互相替换。
- [scripts/agent_cli.py](../scripts/agent_cli.py) 直接使用 `AgentService` 提供命令行咨询。

公众咨询使用签名会话凭证，工作人员使用 HttpOnly Cookie；工作人员写请求还需 CSRF token。知识库、图谱、DSL 与数据库管理需要工作人员身份。公众工具执行禁止 Text2SQL 和私有用户档案访问；公众问答仍可检索现有政策语料，当前没有按文档发布审批或内部/公开资料分级授权。[认证与会话契约](AUTHENTICATION.md)

## 普通问答链路

入口为 [AgentService.process_query](../app/agents/service/agent_service.py)，主要顺序如下：

1. 恢复会话和附件上下文，检查请求对私有能力的访问权限。
2. 问候直接回复；原始问题命中已核验 FAQ 时返回对应答案。
3. 对普通、无附件且没有强制 SQL 的请求，按配置优先尝试 AgentChat Team，其次 Router。允许回退且未得到结果时进入知识问答。
4. 附件、强制 SQL 等专项请求经过改写、领域上下文、FastPath 或意图判断，转到知识、图谱、规则、SQL 或工作流路径。
5. 汇总答案、来源、路由及工具元数据，并由接口层保存聊天消息。

[AgentChat Team](../app/agents/service/agentchat_team.py) 使用 `UserProxyAgent + AssistantAgent` 的 `RoundRobinGroupChat(max_turns=2)`；[Router](../app/agents/service/agentchat_router.py) 使用单个助手。两者都提供知识、图谱、规则、Text2SQL、工作流五类工具。提示词要求选择合适工具，不应将该提示写成所有模型都严格只调用一个工具的程序保证。

模板显式开启 `AGENTCHAT_TEAM_ENABLED`、`AGENTCHAT_ENABLED` 和 `AGENTCHAT_REFLECT`，关闭模型流式透传。开关未设置时的行为以代码读取为准，不能把模板选择等同于所有运行方式的隐式默认值。

### FAQ 的命中条件

[FAQResponder](../app/knowledge/faq_responder.py) 使用来源核验条目，检查官方来源 URL、正文文件与哈希、逐字引文、地区及适用日期。问句只忽略首尾空白、大小写和末尾问号/句号，不采用旧文档中的标签包含、0.85 相似度阈值或改写后再次匹配。

### AG-UI、流式输出与模型记忆

问答界面使用 `POST /api/agent/ag-ui`，请求遵循官方 `RunAgentInput`，响应由官方 `EventEncoder` 编码。标准事件包括 `RUN_STARTED / RUN_FINISHED / RUN_ERROR`、`STEP_STARTED / STEP_FINISHED`、`TOOL_CALL_*` 与 `TEXT_MESSAGE_*`；`glyph.session`、`glyph.sources`、`glyph.answer` 三种 `CUSTOM` 事件分别传递客户端会话凭证、来源和最终答复快照。服务端恢复历史与权限，不接受客户端覆盖工具、状态或上下文。

阶段与工具事件来自实际执行边界；没有正文增量时只显示已发生的进度，不模拟打字。前端以最终快照覆盖草稿，保留原始引用编号并按原文合并来源。停止会关闭读取并取消对应服务任务，不自动重发请求。协议接入不改变公众签名会话、工作人员 Cookie / CSRF 或私有工具权限。

原有 `POST /api/agent/chat/stream` 保留兼容，发送 `session`、`message`、`done` 等事件。两种协议都调用同一服务流：`AGENTCHAT_STREAM_ENABLED=false` 时执行普通回答再发送结果；开启且 AgentChat 与模型支持时，无附件、非强制 Text2SQL 请求走所选 Team 或 Router 的模型流式路径，不重放普通请求的问候和 FAQ 前置步骤。附件、强制 Text2SQL 或 AgentChat 未启用时仍通过普通处理返回完整答案。

聊天会话与消息通过 `SessionManager` 和 [ChatHistoryStore](../app/agents/service/chat_history_store.py) 写 MySQL。模型上下文由 [autogen_memory_store.py](../app/agents/framework/common/autogen_memory_store.py) 中的进程内 `ListMemory` 与 `BufferedChatCompletionContext` 提供，重启后的模型记忆连续性不能仅由数据库消息存在来推断。

当前桥接器不支持 Redis 记忆持久化，配置 `AGENTCHAT_REDIS_URL` 也不会启用这一能力。公众历史在浏览器本机读取，工作人员历史接口校验账号命名空间；两种历史恢复方式不同。

## 文档工作区与索引

[知识库路由](../app/api/endpoints/knowledge.py) 处理上传、重新解析、预览、处理配置与显式入库；[DocumentWorkspace](../app/knowledge/document_workspace.py) 管理原文、版本化解析缓存和状态。

资料列表由 [DocumentCatalog](../app/knowledge/document_catalog.py) 保存已校验的元数据快照，启动时预热，并通过文件大小、纳秒时间戳与原件身份检测常规变化；未变化的资料不在每次列表请求中重复读取正文。接口支持服务端分页、名称与状态筛选，前端按完整查询参数缓存元数据页。快照是列表加速缓存，打开工作区、解析、预览与入库仍校验真实内容哈希；列表状态不能替代操作前的版本检查。

- 上传保存原文并生成解析缓存，不自动写入 Milvus。常用解析格式为 PDF、DOCX、TXT 和 Markdown；不能把上传扩展名清单中的 DOC 当作已实现的解析保证。
- PDF / DOCX 由实际选定的解析器处理，PDF 页图使用 PyMuPDF。MinerU 要求匹配当前代码使用的服务协议与密钥；仅设置模板中的本地地址不代表任意本地 MinerU 部署都能直接接入。
- 切块预览按 Unicode 字符计算，支持固定长度或句子边界，不写索引。解析正文与原文逐字一致时才提供精确页号映射。
- 网页当前声明 `ocr=False`、`hierarchical_index=False`，拒绝按文档覆盖 OCR 和网页分级索引选项。
- 网页显式入库核对原文与解析版本，以稳定文档 ID 向 Milvus upsert 后写入状态标记。当前写入对象是完整解析正文，不按预览块逐块向量化。
- [常州专项导入](../scripts/import_changzhou_policies.py) 使用另一条显式分段、来源头、稳定 ID 和读回校验流程，不能与通用网页入库混为同一能力。

[KnowledgeService.search](../app/knowledge/service.py) 查询 Milvus；开启混合检索且已有分级索引时，还读取 LlamaIndex 结果，按文档 ID 保留最高分。部分无法由分级索引承接的向量过滤条件会使其跳过分级检索。

分级索引需通过 [embed_documents.py](../scripts/embed_documents.py) 预先构建。知识流程还包含可选重排与按检索分数选择回答路径的逻辑；检索分数不是答案正确率，不使用没有当前基准的固定加速百分比描述效果。

## 图谱查询与浏览

图谱检索 Agent 支持 LightRAG 的 `naive / local / global / hybrid` 模式；当前 [GraphAgent.answer](../app/agents/pipeline/graph_agent.py) 显式使用 `hybrid`，图谱结果为空时可回到知识问答。

图谱可使用 `scripts.seed_lightrag` 显式构建；配置 `LIGHTRAG_SEED_DATA_DIR` 后，`AgentService.initialize()` 也会按种子清单检查并自动导入或重新导入。启动前应确认该目录及其写入范围。

[图谱 API](../app/api/endpoints/knowledge_graph.py) 直接读取 `LIGHTRAG_WORKDIR` 下的 `graph_chunk_entity_relation.graphml`，提供概览、实体搜索、受限深度和节点数的子图、邻居数量、统计和文件修订信息。[KnowledgeGraph.vue](../web/src/views/KnowledgeGraph.vue) 使用 G6 绘制这些数据。

`LIGHTRAG_WORKDIR` 以当前环境与代码配置为准。当前默认原生图存储与 GraphML 浏览不要求把 Neo4j 作为政策图谱主库；仓库中的 Neo4j 配置和清理代码仍有独立适用范围。

## 规则、草稿与结构化查询

[rules/](../rules/) 保存政策 YAML；[PolicyEngine](../app/agents/dsl_generator/rule_engine.py) 与领域计算函数负责资格、比例、金额及封顶。模型负责选规则和提取明确事实，不直接替代金额计算。

[RuleVerificationRegistry](../app/agents/dsl_generator/rule_verification.py) 将核验记录绑定规则、来源及计算实现指纹；发生版本漂移时转为待复核。对话只放行适当核验状态的金额结果，部分规则返回人工核实。规则编辑器支持生成、保存和草稿试算，试算不自动产生官方核验结论。[当前规则范围](../resources/data/policy_catalog/RULES_2026.md)

[ChatDB](../app/agents/chatdb/) 负责表结构检索、SQL 生成、校验、执行和结果展示。执行路径限制只读查询，拒绝 DML、DDL、多语句等不允许的 SQL。数据库连接配置属于私有能力，只读 SQL 校验也不能代替工作人员身份与实际数据库权限。

## 启动、检查与源码导航

- [快速启动指南](QUICK_START.md)：环境配置、本机运行、显式导入、容器入口与验证命令。
- [项目结构](PROJECT_STRUCTURE.md)：当前目录职责、文件迁移和命令命名。
- [Python 目录约定](PYTHON_STRUCTURE.md)：模型、schema、持久层与内部依赖方向。
- [资料来源目录](../resources/data/policy_catalog/README.md)：政策快照、来源性质、适用范围和已知缺项。

`/api/health` 只检查 API 进程，不验证模型或数据库。前端静态检查、生产构建和 Python 回归的范围不同；依赖版本、安装成功、存储可用与完整业务联调也需要分别验证。
