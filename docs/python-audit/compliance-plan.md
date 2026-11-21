# Python 规约收尾整改计划

2026-11-15。继续上一轮全文件审核，使用原有两个子智能体；本轮目标是落实适用的强制要求，处理有实际收益的推荐项，逐项说明框架协议和业务约束。

1. 复核全部现有审核记录及剩余项，同时重读当前代码。将规则适用性、未修问题和仅缺外部环境的验证边界分开记录，清理已经过期的保留理由。
2. 在现有 SQLAlchemy 2.0 中补齐真实 ORM 类型契约，保留表名、字段、nullable、默认值、外键、索引及公共导入；先用离线映射/DDL 快照和事务回归锁定行为，再修改。不得通过 type ignore、cast、关闭检查或新增依赖消除诊断。
3. 全文复核请求/响应模型、必需字段、无依据兜底、异步阻塞、取消、客户端及数据库资源所有权、日志、稳定返回值和真实 SDK 协议。修正已证实问题，保留业务功能及调用契约。
4. 两个子智能体分别负责 API/持久化及知识/DSL/工具分区；主代理负责运行时、跨分区接口及统一验证。每个文件都有本轮结论，新增测试也纳入清单。共享文件冲突由主代理协调。
5. 执行全量离线 pytest、207 个以上文件编译/Python 3.10 语法检查、Ruff、mypy（另检查未注解函数体）、Bandit、入口与 OpenAPI 检查、范围内 diff 检查。失败继续修正，记录准确的环境限制，不调用真实外部服务。
6. 更新逐文件报告、覆盖清单、源码/报告哈希和人类可读报告。只有每个适用强制规则的未解决问题归零，且离线验证通过，才报告本轮合规结论；有理由保留的推荐项和专项集成限制明确说明。

## 所有权

- 子智能体一：`app/api/`、`app/config/`、`app/core/`、`app/domains/`、`app/utils/`、`app/models/`、`app/schemas/`、`app/persistence/`、`app/agents/chatdb/`、`api_server.py`、`app/main.py`；对应 API 与持久化测试和报告。
- 子智能体二：`app/knowledge/`、`app/agents/pipeline/`、`app/agents/packs/`、`app/agents/dsl_generator/`、`scripts/`、`examples/`、`resources/database/`、`tests/data_import.py`、`tests/docker_rebuild_test.py`；对应知识、DSL、工具测试和报告。
- 主代理：其余 Python 文件，尤其 `app/agents/framework/`、`app/agents/service/`；集成与监控测试；全局报告及验证配置。两个子智能体不得递归启动其它代理。

保持现有前端改动、已有 stash、服务运行副本不变；不自动提交、推送、部署或迁移数据库。
