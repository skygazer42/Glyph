# 第三轮 API / 配置 / 持久化 / ChatDB 审核结果

本轮按 python-coding-guidelines 重新复核 naming-imports、classes-functions、data-control、errors-resources、minimal-design，主流程、实际调用方和字段生产者是可读性判断依据。清理计划先写在 [api-plan.md](api-plan.md)，旧 round2 报告未改写为本轮证据。

所有权沿用 round2 的 81 文件，排除主代理负责的 `app/utils/lifecycle.py`。80 个原有文件逐一复核，其中 2 个无消费者模块删除，现存 78 文件（76 个应用文件、2 个回归测试文件）。相对 round2 文件哈希，32 个文件改正、46 个复核保留、2 个审核后删除。每个文件的具体阅读结论在 [api/file-review.md](api/file-review.md)，当前路径、状态、行数及 LF 归一化 SHA256 在 [api/source-manifest.json](api/source-manifest.json)。

## 具体改正

| 规则与级别 | 实际位置 | 问题、影响和最小改法 |
| --- | --- | --- |
| NAM-001 强制 / NAM-004 推荐 | `text2sql_service.py`、`text2sql_utils.py`、`domain_zh_gov.py`、`schema_introspector.py`、API endpoints、`main.py`、`session.py` | 聚合/时间窗、表/列/关系、事件/附件/会话及配置变量使用业务名字；模型阶段命名 `generate_sql_with_model`；PyMySQL、SQLAlchemy、PyYAML 等已声明必需依赖直接顶层导入。 |
| FUN-003 强制 / DAT 真实可选边界 | `sql_executor.py`、`factory.py`、`utils/config.py` | SQL 执行器需要已连接的 DBAccess，改为必需关键字注入，去掉深层“也许没有连接对象”的兜底。Vision 的 api_key/base_url 和 Tavily key 才是真正可选值，统一 `str \| None` 默认 None，并仅在这三个已知配置项边界把 `.env` 精确空串转 None。 |
| FUN-002 推荐 / DES 最小实现 | `hybrid_sql_generator.py`、`sql_generator.py`、`text2sql_utils.py`、`text2sql_service.py` | Hybrid 引擎全仓没有装配者，状态永远 None/False；删除不可达检索/学习/示例/分类脚手架和误导的“正在混合检索”进度，保留真实配置入口、未配置提示、标准 SQL 生成与 `examples_used=0`。删除无调用提示准备方法、扩展表过滤及 standalone Session 兼容包装。 |
| DES 最小实现 | `app/core/model_clients.py`、`app/config/autogen.py` | 逐项核对全仓导入、调用和文档：模型注册表仅包自导出，旧 AutoGen 常量没有消费者，删除两个模块及无用导出。实际共享模型和 AutoGenSettings 保留。 |
| CLS 方法职责 | ChatDB base/query/sql/visualization agent | 无实例状态的 schema/memory 转换及模板构造使用 staticmethod；AutoGen 消息处理、logging 格式器/过滤器、Pydantic 校验器等真实框架协议保持对应方法类型。 |
| DAT 契约 / ERR 失败可见 | `base.py`、`schema_retriever.py`、`text2sql_utils.py`、`dsl.py`、`logging_manager.py` | 由生产者保证的 schema、metadata 键直接读取；AutoGen 事件直接用 kwargs；JSON 格式器只捕获 JSONDecodeError，SQL 校验只转换 SQLParseError。意外解析器故障不再伪装“不合法SQL”。 |
| DAT 配置边界 | `domains/prompt_catalog.py`、`core/llms.py` | YAML 空文档保留既有无配置语义，false/list 与 domains 非映射明确报错；LLM 直接使用已配置 base URL，移除空值时悄悄切到另一个服务商的备用地址。 |
| ERR / LOG | `api/endpoints/agent.py`、`dsl.py`、`text2sql_service.py`、`sql_executor.py` | 删除手工 format_exc 再 logger.exception 的重复 traceback；模型错误不再额外包一层 RuntimeError；既有 QueryResponse/SqlResultMessage 错误边界保留并记录 traceback。 |
| DAT / FUN 最小改法 | `models/base.py`、`init_db.py`、API/CRUD | 附件 MIME 直接判断，不造空字符串；图片后缀使用 endswith tuple；删除 init_db 未使用的 Session 参数并同步唯一调用；ORM/会话未命中明确使用 None，去掉重复文件探测。 |

## 保留的可选和资源语义

- 本分区未发现 try-import 后把必需依赖替换成 Optional Callable/None 的导入兜底。DBAccess 的 `_run_sql`、`_close_connection` 的 None 表示未连接或已关闭；它们不是假可选依赖。PostgreSQL、Oracle、BigQuery、DuckDB、Hive/Presto 驱动按选择的数据库局部直接导入，项目没有声明所有环境必装这些驱动。
- ORM 的 first/get 未命中、无可识别时间窗、未提供 connection_id、用户反馈 callback 未注册、可选凭据、上传 MIME 和 XML 缺失文本都有具体来源，保留必要判断。Snapshot 自带的表/列/关系字段则直接使用，不以 get/空对象隐藏契约缺失。
- 关键词分析/表匹配是当前明确存在的模型失败降级路径，并记录异常；Neo4j 清理失败后继续 MySQL 删除是已有部分成功策略；可视化解析失败显示真实结果列是既有可用性行为。未机械删除这些分支。
- 模型兼容导出 `app/models/llms.py` 有实际消费者；Text2SQLService 在当前 README 中公开；SQLAlchemy Base 导出和模型导入负责 metadata 注册。保留这些兼容和框架职责。
- 保留 SQL 安全策略、查询表/列/连接范围、密码空字符串、0/False、事务回滚、线程内 Session/文件生命周期、同一 DuckDB 连接以及有界流关闭。

## 验证

清理前同一组现有回归 **68 passed**，见 [api/baseline-pytest.txt](api/baseline-pytest.txt)。本轮新增 7 个参数化用例实例，在改源前分别确认了失败：意外 SQL 解析器故障被吞掉（1）、可选配置默认仍为空串（2）、Hybrid 未检索却宣称检索（1）、非法 YAML 被当空配置（3）。修复后同组 **75 passed**，见 [api/pytest.txt](api/pytest.txt)。

最终验证范围为清单中的 78 个现存文件：

- mypy：`--explicit-package-bases --follow-imports=silent --ignore-missing-imports --disable-error-code import-untyped --check-untyped-defs`，无问题，见 [api/mypy.txt](api/mypy.txt)。
- Ruff：E4/E7/E9/F/B/ASYNC，FastAPI Depends/File 按框架不可变默认调用配置，无问题，见 [api/ruff.txt](api/ruff.txt)。
- Python 3.10 AST 解析、compile、分区 `git diff --check` 通过，见 [api/syntax-diff.txt](api/syntax-diff.txt)。最后仅补 text2sql_utils 两函数之间空行并刷新清单；该文件重新解析/编译、分区 diff 检查通过。

这些检查佐证行为和语法；逐文件业务流程与保留判断写在清单中，未以静态检查绿替代阅读结论。没有运行真实 DB/LLM/Neo4j/Milvus/Redis 集成，没有安装、提交、部署、执行建表/种子数据或迁移，也未修改 web。Hybrid 检索/学习引擎当前仍未装配；此次只清理不可达脚手架，没有新增检索能力。

**源码和测试已最终冻结；交付后仅补写本轮文档证据。**
