# Round 4 API / 配置 / 持久化 / ChatDB 审核

本轮完整阅读了 round3/api/source-manifest.json 指定的 78 个现存 Python 文件。范围包含 API、配置/核心、领域/工具、模型/schema、持久化、ChatDB 和两份回归测试；没有用前轮结论替代本轮阅读。最终为 75 个现存文件及 3 个本轮审核后删除的转发模块，另保留 2 项前轮删除历史。相对 round3，22 个现存文件有改动；其他文件有逐文件具体观察和保留依据。

`api-files.json` 的 75 个现存条目均包含全文阅读范围、最终 LF 归一化 SHA256/行数、适用规则的正式编号/级别/标题、实际行号和源代码片段，以及具体问题、改正或保留原因。删除项保存在 `deleted_history`，不会把删除文件从覆盖事实中抹去。`source_frozen=true`；主代理随后修正 text2sql 外部 JSON 边界，本区已重读该源码及对应测试、刷新两条记录并再次冻结，详见后续复核。

## 具体修正

| 位置 | 规则与问题 | 最小改正及证据 |
| --- | --- | --- |
| `app/api/deps.py:39` | ASY-003【强制】：同步 FastAPI 依赖在框架线程池并发首次构造时，共享单例检查/构造/发布没有同一临界区。 | 七个同步工厂共用 `threading.Lock`；保留各工厂真实构造职责，不新增注册表。七个确定性线程回归在旧实现失败、修正后通过。构造调用关系没有递归调用这些工厂。 |
| `app/api/endpoints/agent.py:218` | RES-005、ASY-008、ASY-009【强制】：SSE 消费方提前结束时，内层自有生成器没有在实际消费作用域确定关闭。 | 将 stream 赋给局部变量，在消费 `finally` 中等待 `close_with_timeout(stream.aclose)`；沿用共享有界 shield 清理，保持同任务 ContextVar 恢复。普通早关和已经取消作用域两项回归红→绿，证明关闭完成前外层不返回，也不误记完成的助手消息。 |
| `app/main.py:188` | LOG-004【强制】：`/query`、`/load-docs` 把原错误转换为 HTTP 500 后，框架只处理 HTTPException，原 traceback 丢失。 | 两个实际转换边界补 `logger.exception`；真实 FastAPI TestClient 的两项行为回归红→绿，检查日志中的原异常。 |
| `app/api/endpoints/agent.py:99`、`:173` | DAT-001【强制】：已成立的内部必需协议仍用缺省值读取。 | 跟随 `AgentService._finalize_answer` 和 stream 生产者确认 `metadata["session_id"]`、`event["type"]` 必定产生后改直接索引。两项缺字段服务输出回归红→绿，损坏协议现在产生 HTTP/SSE 错误。 |
| `app/agents/service/chat_history_store.py`（由主代理负责修改） | DB-003【强制】：消息写入与会话 activity 分别提交，第二步失败会留下半次操作。 | 本区提供真实 SQLite 回归：注入 `UPDATE chatsession` 故障，旧实现 1 failed/1 passed，主代理将两步置于同一个 `db.begin()` 后 2 passed。成功保留消息，失败消息与时间一起回滚。该源码不计入本区 75 项。 |
| 19 个源码文件及两份测试 | NAM-003【强制】、DES-006【推荐】：内部对象依赖经聚合包/旧 shim 多跳。 | AgentService、KnowledgeService、EnhancedDocumentProcessor、settings、model_client、ORM Base 直接导入定义模块；测试替身同步到实际定义路径。具体文件见 `api-import-definition-files.txt`。真实公共包导出和路由子模块装配保留。 |

错误路径的回归在旧实现上单独确认失败，证据分别为 `api-red-lifecycle.txt`（9 failed）、`api-red-error-log.txt`（2 failed）、`api-red-required-contract.txt`（2 failed）和 `api-chat-transaction-red.txt`（1 failed/1 passed）。最终绿测覆盖这些行为；没有为导入格式增加源码字符串或转发形状测试。

## 删除与保留依据

删除前检索了全仓 Python 引用、README 与配置入口，并排除本身的审计历史、依赖目录和日志目录作为消费者。仓库没有发行包配置或文档承诺这些旧模块的公开迁移窗口。按 DES-001/DES-004【强制】及 DES-006【推荐】删除：

- `app/core/config.py`：只转发 settings；剩余消费者为 core 包入口和 `7_sync_text2sql_schema`，分别同步到 `app.config.app_config`，后者由 tooling 所有者修改。保留 `app/core/__init__.py` 的真实公共导出。
- `app/models/llms.py`：只转发 model_client；仅示例及其测试替身使用，tooling 所有者同步到 `app.core.llms`。
- `app/persistence/db/base_class.py`：ORM/CRUD 内部对象改从 `app.models.base` 获取后，仅测试还显式加载该旧 shim；删除这行转发形状加载，真实 SQLAlchemy 映射、DDL、外键、关系、级联及事务测试仍执行。

原有 `app/config/autogen.py`、`app/core/model_clients.py` 删除只记录历史，没有重建。没有把包标记、真实装配入口或短小框架回调按行数当作无用模块删除。

DAT-002/003/006、PYD-009 等规则逐处对照后保留了真实语义：连接 ID 0、布尔 False、零期限/容量及空密码有效；PATCH 的缺字段、显式 None 与 False 不混淆；DDL nullable 的 ORM/JSON/时间字段保留 None；请求中的可选 attachments/user_id、领域未命中及未配置服务状态保留。消息和配置容器使用实例工厂；内部 dataclass/Enum、SQLAlchemy ORM、AutoGen RoutedAgent、logging Filter/Formatter 各保留真实协议。动态 DSL/stats/metadata 字典由实际模板使用，不为统一类型而改变产品契约。

## 初次冻结验证

| 验证 | 实际结果 | 证据 |
| --- | --- | --- |
| 两份分区回归测试 | 90 passed in 5.40s | `api-pytest.txt` |
| mypy，显式包基、跟随静默导入、忽略缺失第三方类型、检查无注解函数 | Success: no issues found in 75 source files | `api-mypy.txt` |
| Ruff E4/E7/E9/F/B/ASYNC；仅对已有 FastAPI Depends/File 扩展不可变默认调用声明 | All checks passed | `api-ruff.txt` |
| 75 文件 `ast.parse(feature_version=(3,10))` 与 `compile` | 全部通过 | `api-syntax-diff.txt` |
| 分区现存/删除路径 `git diff --check` | exit 0 | `api-syntax-diff.txt` |
| 主代理联合运行 API、持久化、运行时、监控回归 | 193 passed in 6.94s | `cross-api-runtime-tests.txt` |

本表静态检查和 90 项测试均在三处 shim 删除及定义模块导入修改后执行，时间早于下述 text2sql 后续修正。每条记录的规则编号/级别来自当前 Skill 的 87 条正式标题，源代码片段和哈希对应冻结文件。

实际运行环境是 Python 3.11.7；3.10 只做语法版本检查，没有宣称在真实 3.10 解释器运行。LLM、Redis、向量库、Neo4j、MySQL/PostgreSQL 等外部服务未做真实端到端调用；数据库行为回归使用真实 SQLite/SQLAlchemy，驱动边界用替身。不安装依赖，不提交、部署、迁移或执行种子数据及外部业务操作。静态检查不能代替可读性和契约审核，逐文件具体判断见账本。

## text2sql 后续复核

主代理修正后，本区重新完整阅读 `app/agents/chatdb/text2sql_utils.py` 的 482 行与 `tests/test_python_guidelines_persistence_chatdb.py` 的 861 行，并只刷新原 75 项账本中的这两条记录。没有将旧哈希或初次冻结检查冒充更新后的文件验证。

PYD-001/002/003【强制】与 PYD-008【推荐】：查询分析的六个稳定必填字段使用同文件 `QueryAnalysis`；排序使用 `RankedTable` 与 `TableRanking`。两处外部 JSON 读取使用 `model_validate_json`，严格验证整数表 ID、0..10 评分和字符串 reasoning，内部按模型属性直读。DB-002【强制】：排序表 ID 必须来自本次可用表快照。ERR-004【强制】：保留原有关键词分析/匹配策略、traceback warning、领域加权与相关性阈值。False、空集合、空排序、表 ID 0 和评分 0 均保留真实语义。

新增 17 项行为测试在旧实现产生 13 failed/4 passed（`text2sql-json-red.txt`），修正后整份持久化回归 57 passed in 2.45s（`text2sql-json-green.txt`）。本区重新执行两文件 Python 3.10 AST/compile 均通过；主代理补充的四文件 mypy 为 Success: no issues found，四文件 Ruff 通过；初次 75 文件检查与本次后续检查分别记录。

最终 LF SHA256：源码 `cafaa3c20a17bea8b1255b601e3856ba6875b483b12a0558ce827902b96f00c5`；测试 `d4d46de393344a100e7e77c49e46a8aba277f33242261cd6cfcea9fe507ad9af`。
