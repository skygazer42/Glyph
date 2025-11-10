# 政务问答数据库快速入门

## 5分钟快速开始

### 1. 初始化数据库

```bash
cd F:\pythonproject\Glyph
python database/initialize_db.py
```

### 2. 验证安装

```bash
python -c "import sqlite3; conn = sqlite3.connect('database/policy_qa.db'); print('数据库连接成功！'); conn.close()"
```

### 3. 第一个查询

```python
import sqlite3

# 连接数据库
conn = sqlite3.connect('database/policy_qa.db')
cursor = conn.cursor()

# 查询所有QA对
cursor.execute("SELECT question, answer FROM policy_qa_pairs LIMIT 3")
for q, a in cursor.fetchall():
    print(f"问: {q}")
    print(f"答: {a}\n")

conn.close()
```

## 常用查询模板

### 关键词搜索

```python
keyword = "补贴金额"
cursor.execute("""
    SELECT question, answer, category
    FROM policy_qa_pairs
    WHERE keywords LIKE ?
""", (f'%{keyword}%',))
```

### 分类查询

```python
category = "汽车消费补贴"
cursor.execute("""
    SELECT question, answer
    FROM policy_qa_pairs
    WHERE category = ?
    ORDER BY difficulty_level
""", (category,))
```

### 获取活跃政策

```python
cursor.execute("""
    SELECT title, category, publish_date
    FROM policy_documents
    WHERE status = 'active'
    ORDER BY publish_date DESC
""")
```

## 数据统计

```python
# QA对统计
cursor.execute("""
    SELECT category, COUNT(*) as count
    FROM policy_qa_pairs
    GROUP BY category
""")
print("分类统计:", cursor.fetchall())

# 文档统计
cursor.execute("SELECT COUNT(*) FROM policy_documents")
print("文档总数:", cursor.fetchone()[0])
```

## API 集成示例

```python
from fastapi import FastAPI
import sqlite3

app = FastAPI()

@app.get("/api/qa/search")
async def search_qa(q: str):
    conn = sqlite3.connect('database/policy_qa.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT question, answer, category
        FROM policy_qa_pairs
        WHERE question LIKE ?
        LIMIT 5
    """, (f'%{q}%',))

    results = [
        {"question": row[0], "answer": row[1], "category": row[2]}
        for row in cursor.fetchall()
    ]

    conn.close()
    return {"results": results}
```

## 数据库位置

```
F:\pythonproject\Glyph\database\policy_qa.db
```

## 数据概览

- **QA 对**: 10 个
  - 汽车消费补贴: 4 个
  - 家电以旧换新: 3 个
  - 通用政策: 3 个

- **政策文档**: 12 个
  - 汽车消费补贴: 5 个
  - 家电以旧换新: 4 个
  - 消费券: 3 个

## 核心表

1. `policy_qa_pairs` - 问答对
2. `policy_documents` - 政策文档
3. `policy_entities` - 实体信息
4. `policy_tags` - 语义标签
5. `schema_hints` - LLM提示

## 下一步

- 查看完整文档: `database/README.md`
- 了解表结构: `database/schema/policy_qa_schema.sql`
- 查看数据: `database/seed_data/policy_qa_初始数据.json`

## 常见问题

**Q: 如何添加新数据？**

```python
cursor.execute("""
    INSERT INTO policy_qa_pairs (question, answer, category, keywords)
    VALUES (?, ?, ?, ?)
""", ("新问题", "新答案", "分类", "关键词1,关键词2"))
conn.commit()
```

**Q: 如何备份数据库？**

```bash
cp database/policy_qa.db database/backup/policy_qa_backup.db
```

**Q: 如何重置数据库？**

```bash
rm database/policy_qa.db
python database/initialize_db.py
```

---

更多信息请参考: `database/README.md`
