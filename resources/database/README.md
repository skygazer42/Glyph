# 政务智能问答数据库 Schema 说明（MySQL）

> 本文档只描述 **表结构和使用约定**。  
> 实际初始化和导数逻辑由 `scripts/2_seed_mysql_text2sql.py` 和 `scripts/init_data.sh` 负责完成，目标库为 **MySQL `policy_db`**。

---

## 1. 系统概述

政务智能问答数据库用于承载：

- 政策原文与元数据（文档层）
- 结构化实体与标签（结构化层）
- 问答对与查询日志（交互层）

Text2SQL 智能体、DSL 生成器等都会围绕这些表做检索和分析。

---

## 2. 初始化与连接方式

### 2.1 初始化 MySQL 表结构 + 演示数据

在项目根目录执行：

```bash
# 仅初始化 MySQL / Text2SQL 演示数据
python scripts/2_seed_mysql_text2sql.py

# 或执行完整链路（建表 + MySQL + Milvus + 索引）
bash scripts/init_data.sh
```

`2_seed_mysql_text2sql.py` 会：

1. 读取 `resources/database/schema/policy_qa_schema.sql`，转换为 MySQL 兼容语法并建表；
2. 生成若干随机政策文档、实体、QA 对、标签，插入到 `policy_db` 中；
3. 填充 `schema_hints`，方便 LLM / Text2SQL 理解表结构。

### 2.2 验证表是否存在

```bash
mysql -h $DATABASE__MYSQL_HOST \
      -u $DATABASE__MYSQL_USER \
      -p$DATABASE__MYSQL_PASSWORD \
      -D $DATABASE__MYSQL_DB \
      -e "SHOW TABLES"
```

通常你会看到：

- `policy_documents`
- `policy_entities`
- `policy_qa_pairs`
- `policy_tags`
- `query_history`
- `policy_relationships`
- `policy_change_log`
- `schema_hints`

---

## 3. 核心表概览

> 完整字段定义请参考：`resources/database/schema/policy_qa_schema.sql`  
> 以下为按业务维度的简要说明。

### 3.1 政策文档表 `policy_documents`

- 存储政策原文和元数据：
  - `doc_id`: 业务主键，供其他表引用
  - `title`: 标题
  - `category` / `sub_category`: 领域与子类（如汽车消费补贴、家电以旧换新）
  - `content`: Markdown/纯文本内容
  - `metadata`: JSON 扩展字段（地域、发布部门等）
  - `publish_date` / `effective_date` / `expiry_date`
  - `status`: `active` / `expired` / `draft`

### 3.2 政策实体表 `policy_entities`

- 对文档中关键信息的结构化抽取：
  - 常见 `entity_type`：补贴金额、申请条件、时间期限、办理流程、申请材料
  - `entity_value` / `entity_unit` 用于结构化计算或过滤

### 3.3 问答对表 `policy_qa_pairs`

- 存储高质量 QA 对，供：
  - Text2SQL 回答直接落库
  - FAQ 检索/候选答案合并
- 关键字段：
  - `question` / `answer`
  - `doc_id`：回链到 `policy_documents`
  - `category` / `keywords`
  - `difficulty_level`：1–5
  - `query_type`：`informational` / `procedural` / `eligibility`
  - `verified`：是否人工校验
  - `use_count` / `feedback_score`

### 3.4 标签表 `policy_tags`

- 负责语义标签与简单主题体系：
  - `tag_name`: 标签名（如 “新能源”、“消费券”、“小微企业”）
  - `tag_type`: 领域 / 对象 / 场景
  - `weight`: 用于相关性加权

### 3.5 查询历史表 `query_history`

- 记录用户查询与系统响应摘要：
  - `session_id` / `user_id`
  - `query`：原始问句
  - `matched_doc_ids`：文档 ID 列表（JSON）
  - `response`：回答摘要
  - `response_time_ms` / `feedback` / `feedback_comment`

> 注意：多轮对话的完整细节建议使用主项目的  
> `ChatSession` / `ChatMessage` ORM 模型（`app/models/chat_history.py`），  
> 这里的 `query_history` 更偏向统计与审计用途。

### 3.6 政策关系表 `policy_relationships`

- 抽象不同政策文档之间的关系：
  - `relationship_type`: `补充` / `替代` / `依赖` / `相关`
  - 供智能体做「政策对比」「新旧政策衔接」等推理。

### 3.7 变更日志表 `policy_change_log`

- 记录政策生命周期变更：
  - `change_type`: `created` / `updated` / `expired` / `superseded`
  - `old_value` / `new_value`: 文本或 JSON 摘要
  - 可用于回溯特定时间点的政策状态。

### 3.8 Schema 提示表 `schema_hints`

- 面向 LLM / Text2SQL 的表结构注释：
  - `table_name` / `column_name`
  - `hint_type`: `description` / `example` / `constraint`
  - `hint_text`: 中文提示文案
- `scripts/2_seed_mysql_text2sql.py` 会自动填充一批中文提示，帮助模型理解字段语义。

---

## 4. 与 Text2SQL / Agent 的关系

- Text2SQL 智能体会：
  - 从 `schema_hints` 和元数据中拼接 DDL 视图；
  - 基于用户问题选择 `policy_documents` / `policy_qa_pairs` 等相关表；
  - 生成并执行 SQL，最终输出自然语言答案。
- 其它 Agent（如政策比较、时间线梳理）会复用同一批表，并通过
  `PolicyDomainContextBuilder` 做地区 / 时间窗口 / 主题的统一规范化。

---

## 5. 推荐的访问方式

项目内部推荐使用已有的 ORM / 工具层，而不是直接拼接连接串：

- ORM 模型：`app/models/*.py`
- SQLAlchemy 会话：`app/persistence/db/session.py` 中的 `SessionLocal`
- 通用查询封装：`app/persistence/crud/*`

示例（同步脚本）：

```python
from app.persistence.db.session import SessionLocal
from app.models.schema_table import SchemaTable

db = SessionLocal()
try:
    tables = db.query(SchemaTable).limit(5).all()
    for t in tables:
        print(t.table_name, t.description)
finally:
    db.close()
```

---

## 6. 目录结构

```text
resources/database/
├── schema/
│   └── policy_qa_schema.sql        # 政策问答相关表的 Schema 定义（以 SQLite 语法书写，脚本中会转换为 MySQL）
└── seed_data/
    ├── generate_qa_data.py         # 生成初始 QA 对数据的脚本（供演示/扩展）
    └── policy_qa_初始数据.json      # 示例 QA 对 JSON（可按需导入到 MySQL）
```

---

## 7. 迁移与扩展建议

- 新增表时：
  - 优先修改 `policy_qa_schema.sql`，并确保 `2_seed_mysql_text2sql.py` 的语法转换仍然生效；
  - 同时补充 `schema_hints`，提高 Text2SQL 的可用性。
- 若引入新领域（城市 / 业务线），推荐：
  - 在 `metadata` / 标签中附加 `region` / `domain` 信息；
  - 通过上层的领域上下文路由（`PolicyDomainContextBuilder`）区分处理。

