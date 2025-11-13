# Text2SQL 演示数据集

为方便在本地演示 Text2SQL 路由，仓库新增了 `resources/sql/policy_demo.sql`，包含济南/青岛消费券、汽车补贴、首保补贴、家电以旧换新等结构化数据。按照下面的步骤即可完成环境准备。

## 1. 生成 SQLite 数据库

```bash
# 进入仓库根目录
sqlite3 resources/sql/policy_demo.db < resources/sql/policy_demo.sql
```

该命令会创建 `resources/sql/policy_demo.db` 并写入 5 张业务表：`coupon_rules`、`auto_subsidy_windows`、`auto_subsidy_tiers`、`insurance_subsidy_rules`、`appliance_subsidy_rules`（另含若干辅助表）。

## 2. 注册 Text2SQL 数据连接

Text2SQL Agent 依赖 `dbconnection` 元数据。使用仓库脚本可自动建表并插入一条 SQLite 连接：

```bash
python scripts/register_text2sql_connection.py
```

输出 `Created sqlite connection with id=...` 后，记下该 `id`，后续在 `/api/agent/chat` 请求体中通过 `"connection_id": <id>` 即可触发 Text2SQL 路由。

> 若脚本提示“connection already exists”，说明已注册，无需重复执行。

## 3. 测试示例

```bash
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
        "message": "写一条SQL统计济南零售券各档位的折扣金额",
        "connection_id": 1,
        "session_id": "text2sql_demo"
      }'
```

| 常用问法 | 说明 |
| --- | --- |
| “编写SQL：查询济南新能源车价段对应的补贴金额” | 命中 `auto_subsidy_tiers` |
| “给我SQL筛选商业险补贴大于1500元的档位” | 命中 `insurance_subsidy_rules` |
| “统计各类家电一级能效补贴率” | 命中 `appliance_subsidy_rules` |

确保同一个 `session_id` 下的问题包含 SQL 关键词（select/统计/查询/SQL 等），且携带有效 `connection_id`，即可看到 Text2SQLAgent 参与回答。

## 4. 新增政策流程 & Agent 数据集

为解决“问题设计与示例数据脱节”导致 Text2SQL 难以验证的痛点，`resources/sql/policy_demo.sql` 现已追加以下表格，并全部来源于 `resources/data/process` 与 `app/agents` 目录的真实资料：

| 表名 | 说明 | 典型字段 |
| --- | --- | --- |
| `policy_documents` | 汇总济南家电/数码/汽车/消费券等政策文件的元数据 | `doc_id`, `category`, `summary`, `source_path` |
| `policy_benefit_rules` | 将补贴档位拆成可检索的区间/金额/限购信息 | `benefit_item`, `subsidy_rate`, `flat_amount` |
| `policy_timelines` | 记录公告中的起止时间段 | `phase`, `start_time`, `notes` |
| `policy_execution_roles` | 抽取执行主体（泉城购、抖音APP、齐鲁银行等）及职责 | `role_name`, `responsibilities` |
| `agent_capabilities` | 来自 `app/agents` 的核心 Agent 编排信息 | `route`, `primary_tools`, `entry_point` |
| `agent_question_templates` | 针对各 Agent 的典型场景/提问模版 | `scenario`, `expected_route` |
| `text2sql_reference_questions` | 15 条参考 NL → SQL 题目，可直接驱动测试脚本 | `question`, `recommended_table`, `filter_hint` |

执行如下命令即可重新生成数据库并查看参考题库：

```bash
sqlite3 resources/sql/policy_demo.db < resources/sql/policy_demo.sql
sqlite3 resources/sql/policy_demo.db \
  "SELECT id, question, recommended_table, filter_hint FROM text2sql_reference_questions LIMIT 5;"
```

随后在调用 `/api/agent/chat` 时，将 `question` 字段替换为参考题目、并传入 `connection_id`：

```bash
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
        "message": "写一条SQL列出济南家电以旧换新细则中所有空调补贴档位及补贴比例。",
        "connection_id": 1,
        "session_id": "text2sql_process_cases"
      }'
```

如需批量演练，可让 `run_50_tests.sh` 或自定义脚本动态读取 `text2sql_reference_questions`（按 `difficulty` 过滤）后逐条发起请求，便可覆盖政策流程、Agent 画像与旧有 demo 表的多样 SQL。
