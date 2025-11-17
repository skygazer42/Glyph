# Glyph 技术栈概览

本文聚焦 Glyph 政策智能问答系统所使用的关键技术、组件位置和核心能力，方便团队在撰写汇报或评估架构时快速定位。

## 后端基础

- **语言/运行时**：Python 3.9+，要求类型提示、4 空格缩进。
- **Web 框架**：FastAPI（`api_server.py`、`app/main.py`），提供 REST API、健康检查和 CLI 接口。
- **配置与依赖**：`requirements.txt` 描述 loguru、rich、LlamaIndex、Milvus SDK 等依赖；`.env` 通过 `app/config/app_config.py` 读取。
- **日志与监控**：loguru + rich 输出，配合 FastAPI 中间件记录请求。

## 智能体与编排

- **Agent 框架**：AutoGen Core，所有智能体注册在 `app/agents/service/agent_service.py`，入口 `AgentService.process_query`。
- **核心 Agent**：
  - `RewriteAgent`：业务化改写、上下文拼接（LRU 缓存）。
  - `IntentRouter`：LLM 分类 + FastPath 规则；根据意图分发。
  - `KnowledgeAgent`：混合检索、早停与答案合成。
  - `GraphAgent`：对接 LightRAG 本地图谱。
  - `RuleEngine`：YAML DSL 计算器，位于 `rules/`。
  - `Text2SQLAgent`：`app/agents/chatdb/`，包含 schema 检索、SQL 生成、执行与可视化。
  - 其他（Dialogue、Clarifier、Workflow、PolicyAnalyzer 等）在路由图中协同。
- **智能路由能力**：FAQ 命中 → Rewrite/Domain → FastPath → IntentRouter → 各链路；`EARLY_STOP_CONF` 控制早停。

## 知识与检索

- **文档处理**：
  - `app/knowledge/document_loader.py` 将 Markdown/PDF 标准化为 `PolicyDocument`。
  - `HierarchicalMarkdownProcessor`（`app/knowledge/hierarchical_index.py`）支持 simple/sentence/keyword_aware 三种分块策略。
- **索引与向量**：
  - **LlamaIndex**：`scripts/4_embed_documents.py` 构建 doc/section/chunk/summary 分级索引；存储在 `LLAMAINDEX_STORAGE_DIR`。
  - **Milvus**：`app/knowledge/milvus.py` 负责集合/索引；`scripts/5_embed_process_documents.py` 写入嵌入。
- **混合召回**：`KnowledgeService.search` 先融合 LlamaIndex 结果，再调用 Milvus；可通过 `.env` 关闭 Hybrid。
- **置信度与早停**：`EARLY_STOP_CONF`（默认 0.8）决定是否直接提取政策要点，减少 LLM 调用。

## 图谱与 LightRAG

- **图谱引擎**：LightRAG，工作目录 `resources/data/lightrag`。`scripts/6_seed_lightrag.py` 负责构建实体/关系。
- **查询模式**：naive/local/global/hybrid，可在 `.env` 中通过 `LIGHTRAG_QUERY_MODE` 切换。
- **使用场景**：Policy 脉络、关系推理、流程追溯；GraphAgent 输出会被 `AnswerComposer` 聚合。
- **示意图**：`docs/assets/knowledge_graph_sample.svg` 提供栈内图谱示例。

## 规则引擎与 DSL

- **数据位置**：`rules/`、`resources/dsl/`、`templates/`；YAML 定义政策 ID、资格、金额计算、封顶等逻辑。
- **执行链路**：RuleEngine 读取 DSL → PolicyEngine 计算 → AnswerComposer 格式化，支撑高确定性场景（补贴测算、资格判断）。
- **脚本支持**：`python scripts/check_config.py`、`scripts/check_mineru_config.py` 在提交前校验配置一致性。

## Text2SQL（ChatDB）

- **模块位置**：`app/agents/chatdb/`，关键组件：
  - `schema_retriever.py`：MySQL 元数据召回。
  - `sql_generator.py` / `hybrid_sql_generator.py`：规则 + LLM 混合生成 SQL。
  - `sql_executor.py`：仅允许 SELECT，拒绝 DML/DDL/UNION，多语句。
  - `visualization_recommender.py`：根据结果推荐表格/图表。
  - `domain_zh_gov.py`：解析时间窗口、地区关键词增强 SQL。
- **依赖**：MySQL 8.0、`scripts/1_create_tables.py` 初始化 `policy_qa` 库；`scripts/2_seed_mysql_text2sql.py` 导入示例数据。

## 前端与可视化

- **框架**：Vite + Vue 3 + Pinia + Vue Router，位于 `web/` 目录。
- **UI 库**：Element Plus，用于表单/表格；D3 负责图谱可视化；CodeMirror + highlight.js 帮助 DSL 编辑。
- **启动命令**：`npm --prefix web install && npm --prefix web run dev`，默认连接本地 FastAPI。
- **静态资产**：截图、SVG、DSL 模板位于 `web/src` 与 `docs/assets`。

## 支撑脚本

- `scripts/init_data.sh`：串行执行建表、导种子数据、初始化 Milvus/LlamaIndex/LightRAG。
- `scripts/unified_cli.py`：在本地语料上启动多 Agent CLI。
- `scripts/gov_domain_build_overrides.py`：扫描 `resources/data/process` 生成地区/关键词 overrides。
- `run_50_tests.sh` & `pytest`：快速验证路由与 API 质量。

## 参考

- 更详细架构图：`README.md`“功能特性”“系统架构”章节。
- 知识库设计：`docs/knowledge_design_logic.md`。
- 技术优化：`docs/TECHNICAL_OPTIMIZATIONS.md`。
