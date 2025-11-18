# 政务问答数据库快速入门（MySQL 版）

> 说明：当前项目统一使用 **MySQL 的 `policy_db` 库** 作为 Text2SQL / 政策问答的数据源。  
> 早期的 `policy_qa.db`（SQLite）示例库已废弃，不再建议使用。

## 5 分钟快速开始

### 1. 准备环境

1. 启动本地或容器里的 MySQL 8：
   - 确保可以连通：`mysql -h <host> -u <user> -p`
2. 配置 `.env`（或环境变量）中的数据库参数，和主仓库一致：

```env
DATABASE__MYSQL_HOST=localhost
DATABASE__MYSQL_PORT=3306
DATABASE__MYSQL_USER=glyph
DATABASE__MYSQL_PASSWORD=glyph
DATABASE__MYSQL_DB=policy_db
```

### 2. 初始化表结构 + 演示数据

在项目根目录执行：

```bash
cd /path/to/Glyph

# 仅初始化 MySQL 政策问答 / Text2SQL 数据
python scripts/2_seed_mysql_text2sql.py

# 或执行完整数据链路（建表 + MySQL + Milvus + 索引）
bash scripts/init_data.sh
```

`scripts/2_seed_mysql_text2sql.py` 会做两件事：

- 读取 `resources/database/schema/policy_qa_schema.sql`，转换成 MySQL 语法并建表；
- 自动生成一小批政务政策文档、实体、QA 对和标签，插入到 `policy_db` 中。

### 3. 验证初始化结果

使用 MySQL 客户端快速检查：

```bash
mysql -h $DATABASE__MYSQL_HOST \
      -u $DATABASE__MYSQL_USER \
      -p$DATABASE__MYSQL_PASSWORD \
      -D $DATABASE__MYSQL_DB \
      -e "SHOW TABLES"
```

你应该能看到类似表名：

- `policy_documents`
- `policy_qa_pairs`
- `policy_entities`
- `policy_tags`
- `query_history`
- `policy_relationships`
- `policy_change_log`
- `schema_hints`

## Python 查询示例（直接连 MySQL）

```python
import pymysql

conn = pymysql.connect(
    host="localhost",
    port=3306,
    user="glyph",
    password="glyph",
    database="policy_db",
    charset="utf8mb4",
)
cursor = conn.cursor()

# 查询部分 QA 对
cursor.execute(
    """
    SELECT question, answer, category
    FROM policy_qa_pairs
    ORDER BY id
    LIMIT 3
    """
)
for q, a, cat in cursor.fetchall():
    print(f"[{cat}] 问: {q}\n答: {a}\n")

conn.close()
```

## 常用 SQL 模板

按分类统计 QA 对数量：

```sql
SELECT category, COUNT(*) AS qa_count
FROM policy_qa_pairs
GROUP BY category;
```

获取最近发布的有效政策：

```sql
SELECT title, category, publish_date
FROM policy_documents
WHERE status = 'active'
ORDER BY publish_date DESC
LIMIT 10;
```

## 下一步

- 查看完整表结构：`resources/database/schema/policy_qa_schema.sql`
- 查看数据生成逻辑：`scripts/2_seed_mysql_text2sql.py`
- 查看整体链路说明：项目根目录 `README.md` 中的 “导入示例数据” 章节

