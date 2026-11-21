# 第三轮 API / 配置 / 持久化 / ChatDB 清理计划

授权范围沿用 `round2/api/source-manifest.json` 的 81 文件，排除主代理共享的 `app/utils/lifecycle.py`：本轮负责 80 文件。不修改其它分区、旧 round2 证据或前端，不安装依赖、提交、部署或迁移。

已重新阅读 python-coding-guidelines 的 naming-imports、classes-functions、data-control、errors-resources、minimal-design。此次按主流程、实际调用和数据来源评审，不以静态检查通过替代可读性结论。

1. 在任何源码清理之前运行 API 和 persistence/ChatDB 现有行为回归，将输出保存至 `round3/api/baseline-pytest.txt`。
2. 逐文件核对依赖与实际调用。本分区扫描未发现 try-import 后置 None 的假可选依赖；已声明必需依赖保持直接导入。DBAccess 的 PostgreSQL/Oracle/BigQuery/DuckDB/Hive/Presto 驱动未列为所有运行环境必装且只在选择相应数据库时使用，保留局部直接导入，不增加可选装配框架。
3. 先删全仓无调用、无当前文档契约的内容，再清理剩余主流程：核实并删除 text2sql_utils 的遗留扩展表过滤及 Session 兼容入口；不删除仍有实际调用的 FastAPI 依赖、模型兼容导出、配置入口或框架回调。
4. 清理已成立契约上的重复探测：AgentService 确定属性直接读取，AutoGen 事件使用实际 kwargs 协议，ChatDB schema 必需字段直接读取；真实可选配置、ORM 未命中和资源生命周期判空保留并记录依据。
5. 简化错误边界：移除手工格式化 traceback 后再 logger.exception 的重复操作；Formatter 只捕获实际 JSON 解析失败；SQL 格式校验只转换解析器明确的格式错误，意外错误继续传播。对行为边界补必要回归，先确认原实现失败，不写锁定源码形状的测试。
6. 按业务含义改进 ChatDB 提示、表/列/关系处理的局部命名与顺序，删除无用中间变量或转发；不把 `or` 机械换成三元，不为减少行数隐藏有效的业务分支。
7. 每个文件完成审阅后记录具体结果及保留判断的来源。最终执行相关行为回归、Ruff、mypy、Python 3.10 AST/compile 和分区 diff 检查，将新的源码清单与本轮证据保存在 `round3/api/`，结论写入 `round3/api-review.md`。

初始候选需经当前调用方复核；若删除会影响实际使用，保留并说明具体使用对象。全局模型注册和领域配置属于现有公开包 API，先核实外部契约及当前用途，再决定是否改动，不为凑改动数量机械删除。
