# Text2SQL Agent Overview

## 1. 架构分层

```
User Query
   ↓
AgentService.process_query
   ↓ (route = "text2sql")
Text2SQLAgent
   ↓
ChatDB Text2SQL Service
   ↓
Database (MySQL / PostgreSQL / …)
```

- **AgentService**：在意图为 `text2sql` 且传入 `connection_id` 时，调用 `Text2SQLAgent.answer()`。
- **Text2SQLAgent**：从 `db_connection` 表获取连接配置，封装调用 `process_text2sql_query()`，并把结果包装成 `FinalAnswer`。
- **ChatDB Text2SQL Service**（`app/agents/chatdb/text2sql_service.py`）：
  1. `retrieve_relevant_schema()`：基于自然语言查询选择最相关的表/列；
  2. `get_value_mappings()`：提供“自然语言词 ↔ 数据库值”的映射（如“新能源” → `vehicle_type='NEV'`）；
  3. `construct_prompt()`：把 schema + 值映射注入提示，强调“你是一名专业 SQL 开发专家”；
  4. `call_llm_api()`：通过 `model_client` 生成 SQL；
  5. `extract_sql_from_llm_response()`：从回答中截出 SQL，配合 `process_sql_with_value_mappings()` 做二次替换；
  6. `validate_sql()`：确保是合法的 `SELECT`；
  7. `execute_query()`：使用 PyMySQL/SQLAlchemy 在目标数据库执行 SQL，返回结果行。

## 2. 支持任意业务表的条件

只要满足以下条件，理论上任何结构化表都能接入 Text2SQL：

1. **数据库可访问**：在 `db_connection` 表登记一条连接（库类型、host、port、user、password、db_name）。`connection_id` 由用户在查询时指定。
2. **Schema 可描述**：`retrieve_relevant_schema()` 会依赖 `schema_hints`、系统元数据等信息生成 DDL 片段，供 LLM 参考。建议为每张表、字段提供中文描述或示例值，尤其是枚举型字段。
3. **值映射可选**：如果自然语言用词与数据库取值不同，可在 `value_mappings` 添加映射，或者扩展 `text2sql_utils` 里的逻辑。
4. **安全约束**：当前实现只允许生成 `SELECT`，且只能引用提示里公布的表/列，避免误删/误写。

## 3. 样例数据与脚本

- Schema 文件：`resources/database/schema/policy_qa_schema.sql`
- 示例数据脚本：`scripts/seed_mysql_text2sql.py`
  - 自动读取 `.env` 的 `DATABASE__MYSQL_*` 配置；
  - 执行 Schema（自动将 SQLite 语法转换成 MySQL 兼容版本）；
  - 生成随机政策文档、实体、QA 对、标签以及 `schema_hints`；
  - 通过 `--documents N` 控制数据量，`--skip-schema`/`--no-truncate` 控制建表与清空行为。
  - 示例：`python scripts/seed_mysql_text2sql.py --documents 20`

## 4. 常见问题

| 问题 | 说明 |
| --- | --- |
| `connection_id` 缺失 | `Text2SQLAgent` 会直接返回“执行数据库查询需要提供 connection_id”。 |
| MySQL 连接失败 | 检查 `.env` 中 `DATABASE__MYSQL_*`，确保端口对齐 docker-compose 暴露的端口；必要时创建相应用户/权限。 |
| SQL 验证失败 | `validate_sql()` 只允许 `SELECT`；如果 LLM 生成了 `UPDATE/DELETE` 或语法错误，会回显错误并附带 prompt/响应，便于排查。 |
| 查询结果为空 | agent 仍会返回 SQL 和空结果数组，供开发者验证 SQL 是否准确。可以调整 schema 提示/值映射提高命中率。 |

## 5. 接入其他业务库的步骤

1. 在目标库中创建表结构，并填充业务数据；
2. 在 `schema_hints`（或自定义的 schema 提示源）中补充表/字段说明；
3. 通过管理接口或直接写库的方式，在 `db_connection` 表登记该连接；
4. 询问时附上对应 `connection_id`，Text2SQL Agent 会自动在该库上执行生成的 SQL。
