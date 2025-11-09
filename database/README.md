# 政务智能问答数据库系统使用文档

## 目录

1. [系统概述](#系统概述)
2. [数据库架构](#数据库架构)
3. [快速开始](#快速开始)
4. [数据模型](#数据模型)
5. [使用示例](#使用示例)
6. [API集成](#api集成)
7. [维护与更新](#维护与更新)

---

## 系统概述

本系统是基于 ChatDB 架构设计的政务智能问答数据库，专为济南市政策咨询场景优化。

### 核心功能

- **政策文档管理**: 结构化存储政策文档及元数据
- **智能问答**: 高质量 QA 对，支持多种查询类型
- **实体提取**: 自动提取关键信息（补贴金额、申请条件等）
- **语义搜索**: 关键词标签系统支持相关性检索
- **变更追踪**: 完整的政策变更历史记录

### 数据统计

```
初始化数据概览：
- QA 对总数: 10 个
  - 汽车消费补贴: 4 个
  - 家电以旧换新: 3 个
  - 通用政策: 3 个

- 政策文档: 12 个
  - 汽车消费补贴: 5 个
  - 家电以旧换新: 4 个
  - 消费券: 3 个

- Schema 提示: 21 条（LLM友好的表结构说明）
```

---

## 数据库架构

### 核心表结构

#### 1. `policy_documents` - 政策文档表

存储政策文档原文及基本信息。

```sql
CREATE TABLE policy_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id VARCHAR(100) UNIQUE NOT NULL,      -- 文档唯一标识
    title VARCHAR(500) NOT NULL,               -- 文档标题
    category VARCHAR(50) NOT NULL,             -- 政策分类
    sub_category VARCHAR(50),                  -- 子分类
    source_file VARCHAR(500),                  -- 源文件路径
    content TEXT NOT NULL,                     -- 文档内容
    metadata JSON,                             -- 额外元数据
    publish_date DATE,                         -- 发布日期
    effective_date DATE,                       -- 生效日期
    expiry_date DATE,                          -- 失效日期
    status VARCHAR(20) DEFAULT 'active',       -- 状态
    created_at TIMESTAMP,                      -- 创建时间
    updated_at TIMESTAMP                       -- 更新时间
);
```

**分类类型**:
- 汽车消费补贴
- 家电以旧换新
- 消费券
- 数码产品补贴
- 通用政策

#### 2. `policy_qa_pairs` - QA 对表

存储验证过的高质量问答对。

```sql
CREATE TABLE policy_qa_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,                    -- 问题
    answer TEXT NOT NULL,                      -- 答案
    doc_id VARCHAR(100),                       -- 关联文档ID
    category VARCHAR(50) NOT NULL,             -- 分类
    keywords TEXT,                             -- 关键词（逗号分隔）
    difficulty_level INTEGER DEFAULT 3,        -- 难度等级 1-5
    query_type VARCHAR(50),                    -- 查询类型
    verified BOOLEAN DEFAULT FALSE,            -- 是否验证
    use_count INTEGER DEFAULT 0,               -- 使用次数
    feedback_score FLOAT DEFAULT 0.0,          -- 反馈评分
    metadata JSON,                             -- 元数据
    created_at TIMESTAMP,                      -- 创建时间
    updated_at TIMESTAMP                       -- 更新时间
);
```

**查询类型**:
- `informational`: 信息查询（如"补贴金额是多少"）
- `procedural`: 流程查询（如"如何申请补贴"）
- `eligibility`: 资格查询（如"谁可以申请"）

#### 3. `policy_entities` - 政策实体表

结构化提取的关键信息。

```sql
CREATE TABLE policy_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,          -- 实体类型
    entity_name VARCHAR(200) NOT NULL,         -- 实体名称
    entity_value TEXT,                         -- 实体值
    entity_unit VARCHAR(50),                   -- 单位
    confidence FLOAT DEFAULT 1.0,              -- 置信度
    metadata JSON
);
```

**实体类型**:
- 补贴金额
- 申请条件
- 时间期限
- 办理流程
- 申请材料

#### 4. `policy_tags` - 政策标签表

支持语义搜索的标签系统。

```sql
CREATE TABLE policy_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id VARCHAR(100) NOT NULL,
    tag_name VARCHAR(100) NOT NULL,            -- 标签名
    tag_type VARCHAR(50),                      -- 标签类型
    weight FLOAT DEFAULT 1.0                   -- 权重
);
```

**标签类型**:
- 领域（如：汽车、家电）
- 对象（如：补贴、换新）
- 场景（如：新能源、节能）
- 地域（如：济南市）

#### 5. 其他支持表

- `query_history`: 用户查询历史
- `policy_relationships`: 政策间关系
- `policy_change_log`: 变更日志
- `schema_hints`: LLM 表结构提示

---

## 快速开始

### 1. 初始化数据库

```bash
# 进入项目目录
cd F:\pythonproject\Glyph

# 运行初始化脚本
python database/initialize_db.py
```

**预期输出**:
```
============================================================
开始初始化政务智能问答数据库
============================================================

[OK] 已连接到数据库: database\policy_qa.db

[1/6] 创建数据库表结构...
[OK] 数据库表结构创建完成

[2/6] 插入Schema提示...
[OK] 已插入 21 条Schema提示

[3/6] 导入QA对数据...
[OK] 已导入 10 个QA对

[4/6] 导入政策文档...
[INFO] 找到 12 个Markdown文件
[OK] 已导入 12 个政策文档

[5/6] 创建示例标签...
[OK] 已创建 4 个示例标签

[6/6] 生成统计信息...

数据库统计信息
QA对总数: 10
政策文档总数: 12
Schema提示总数: 21

[OK] 数据库初始化完成！
数据库位置: F:\pythonproject\Glyph\database\policy_qa.db
```

### 2. 验证数据库

```bash
# 使用 Python 验证
python -c "import sqlite3; conn = sqlite3.connect('database/policy_qa.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM policy_qa_pairs'); print(f'QA对数量: {cursor.fetchone()[0]}'); conn.close()"
```

---

## 数据模型

### QA 对示例

```json
{
  "question": "2025年济南市汽车消费补贴的活动时间是什么时候？",
  "answer": "购车时间：2025年1月25日0时至2025年3月31日24时（以机动车销售统一发票时间为准）；补贴申报时间：2025年2月12日10时至2025年4月15日24时。补贴额度共计3000万元，先到先得，用完即止。",
  "category": "汽车消费补贴",
  "keywords": "活动时间,购车时间,申报时间,汽车补贴",
  "difficulty_level": 2,
  "query_type": "informational",
  "verified": true
}
```

### 政策文档示例

```json
{
  "doc_id": "doc_0001",
  "title": "2025年政府汽车消费补贴活动公告",
  "category": "汽车消费补贴",
  "status": "active",
  "publish_date": "2025-01-25",
  "content": "# 2025年政府汽车消费补贴活动公告\n\n## 活动时间\n..."
}
```

---

## 使用示例

### Python 基础查询

```python
import sqlite3
import json

# 连接数据库
conn = sqlite3.connect('database/policy_qa.db')
cursor = conn.cursor()

# 1. 查询所有汽车补贴相关的 QA 对
cursor.execute("""
    SELECT question, answer, keywords
    FROM policy_qa_pairs
    WHERE category = '汽车消费补贴'
    ORDER BY difficulty_level
""")

for row in cursor.fetchall():
    print(f"问题: {row[0]}")
    print(f"答案: {row[1]}")
    print(f"关键词: {row[2]}")
    print("-" * 60)

# 2. 关键词搜索
search_keyword = "补贴金额"
cursor.execute("""
    SELECT question, answer
    FROM policy_qa_pairs
    WHERE keywords LIKE ?
""", (f'%{search_keyword}%',))

print(f"\n关键词 '{search_keyword}' 搜索结果:")
for row in cursor.fetchall():
    print(f"Q: {row[0]}")
    print(f"A: {row[1]}\n")

# 3. 获取活跃政策文档
cursor.execute("""
    SELECT title, category, publish_date
    FROM policy_documents
    WHERE status = 'active'
    ORDER BY publish_date DESC
""")

print("\n活跃政策文档:")
for row in cursor.fetchall():
    print(f"- [{row[1]}] {row[0]} ({row[2]})")

conn.close()
```

### 智能问答检索

```python
def search_qa(question_keywords):
    """根据关键词检索相关 QA 对"""
    conn = sqlite3.connect('database/policy_qa.db')
    cursor = conn.cursor()

    # 构建 LIKE 查询
    conditions = ' OR '.join([f"question LIKE '%{kw}%'" for kw in question_keywords])

    cursor.execute(f"""
        SELECT
            question,
            answer,
            category,
            difficulty_level,
            use_count
        FROM policy_qa_pairs
        WHERE {conditions}
        ORDER BY use_count DESC, difficulty_level ASC
        LIMIT 5
    """)

    results = cursor.fetchall()
    conn.close()

    return results

# 使用示例
keywords = ["补贴", "金额", "新能源"]
results = search_qa(keywords)

for i, (q, a, cat, diff, count) in enumerate(results, 1):
    print(f"\n{i}. [{cat}] (难度: {diff}, 使用: {count}次)")
    print(f"   问: {q}")
    print(f"   答: {a[:100]}...")
```

### 统计分析

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('database/policy_qa.db')

# 1. QA 对分类统计
df_qa = pd.read_sql_query("""
    SELECT
        category,
        COUNT(*) as qa_count,
        AVG(difficulty_level) as avg_difficulty,
        SUM(use_count) as total_usage
    FROM policy_qa_pairs
    GROUP BY category
""", conn)

print("QA对分类统计:")
print(df_qa)

# 2. 政策文档分类统计
df_docs = pd.read_sql_query("""
    SELECT
        category,
        COUNT(*) as doc_count,
        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_count
    FROM policy_documents
    GROUP BY category
""", conn)

print("\n政策文档分类统计:")
print(df_docs)

conn.close()
```

---

## API 集成

### FastAPI 端点示例

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
import sqlite3

router = APIRouter(prefix="/api/qa", tags=["问答"])

class QuestionRequest(BaseModel):
    question: str
    category: str = None

class AnswerResponse(BaseModel):
    question: str
    answer: str
    category: str
    confidence: float

@router.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """智能问答端点"""
    conn = sqlite3.connect('database/policy_qa.db')
    cursor = conn.cursor()

    # 简单的关键词匹配
    query = """
        SELECT question, answer, category
        FROM policy_qa_pairs
        WHERE question LIKE ?
    """

    if request.category:
        query += " AND category = ?"
        cursor.execute(query, (f'%{request.question}%', request.category))
    else:
        cursor.execute(query, (f'%{request.question}%',))

    result = cursor.fetchone()
    conn.close()

    if result:
        return AnswerResponse(
            question=result[0],
            answer=result[1],
            category=result[2],
            confidence=0.95
        )
    else:
        return AnswerResponse(
            question=request.question,
            answer="抱歉，暂未找到相关政策信息。",
            category="未知",
            confidence=0.0
        )

@router.get("/categories")
async def get_categories():
    """获取所有政策分类"""
    conn = sqlite3.connect('database/policy_qa.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT category, COUNT(*) as count
        FROM policy_qa_pairs
        GROUP BY category
    """)

    categories = [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]
    conn.close()

    return {"categories": categories}
```

### 向量搜索集成（Milvus）

```python
from pymilvus import connections, Collection
import sqlite3

def sync_qa_to_milvus():
    """将 QA 对同步到 Milvus 向量库"""
    # 连接 SQLite
    conn = sqlite3.connect('database/policy_qa.db')
    cursor = conn.cursor()

    cursor.execute("SELECT id, question, answer, category FROM policy_qa_pairs")
    qa_pairs = cursor.fetchall()
    conn.close()

    # 连接 Milvus
    connections.connect("default", host="localhost", port="19530")
    collection = Collection("policy_qa")

    # 准备数据（需要先用 embedding 模型生成向量）
    # from your_embedding_model import get_embedding

    for qa_id, question, answer, category in qa_pairs:
        # embedding = get_embedding(question)
        # collection.insert([[qa_id], [embedding], [category]])
        pass

    print(f"已同步 {len(qa_pairs)} 个 QA 对到 Milvus")
```

---

## 维护与更新

### 添加新的 QA 对

```python
import sqlite3
import json
from datetime import datetime

def add_qa_pair(question, answer, category, keywords, difficulty=3, query_type="informational"):
    """添加新的 QA 对"""
    conn = sqlite3.connect('database/policy_qa.db')
    cursor = conn.cursor()

    metadata = json.dumps({
        "source": "manual_add",
        "created_by": "admin",
        "created_at": datetime.now().isoformat()
    })

    cursor.execute("""
        INSERT INTO policy_qa_pairs
        (question, answer, category, keywords, difficulty_level, query_type, verified, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (question, answer, category, keywords, difficulty, query_type, True, metadata))

    conn.commit()
    qa_id = cursor.lastrowid
    conn.close()

    print(f"已添加 QA 对，ID: {qa_id}")
    return qa_id

# 使用示例
add_qa_pair(
    question="购买新能源汽车最高可以获得多少补贴？",
    answer="根据2025年济南市政策，购车发票金额30万元（含）以上的新能源汽车，每辆可获得5000元补贴。",
    category="汽车消费补贴",
    keywords="新能源汽车,补贴金额,最高补贴",
    difficulty=2,
    query_type="informational"
)
```

### 更新政策文档状态

```python
def expire_policy(doc_id, reason="政策到期"):
    """标记政策为过期"""
    conn = sqlite3.connect('database/policy_qa.db')
    cursor = conn.cursor()

    # 更新文档状态
    cursor.execute("""
        UPDATE policy_documents
        SET status = 'expired', updated_at = CURRENT_TIMESTAMP
        WHERE doc_id = ?
    """, (doc_id,))

    # 记录变更日志
    cursor.execute("""
        INSERT INTO policy_change_log
        (doc_id, change_type, change_description, old_value, new_value)
        VALUES (?, ?, ?, ?, ?)
    """, (doc_id, "expired", reason, "active", "expired"))

    conn.commit()
    conn.close()

    print(f"政策 {doc_id} 已标记为过期")

# 使用示例
expire_policy("doc_0001", "2025年政策已结束")
```

### 数据库备份

```bash
# 备份数据库
cp database/policy_qa.db database/backup/policy_qa_$(date +%Y%m%d_%H%M%S).db

# 或使用 SQLite 导出
sqlite3 database/policy_qa.db ".backup 'database/backup/policy_qa_backup.db'"
```

### 重新初始化

```bash
# 删除旧数据库
rm database/policy_qa.db

# 重新运行初始化
python database/initialize_db.py
```

---

## 常见问题

### Q1: 如何添加新的政策分类？

A: 直接在插入数据时使用新的 category 值即可。建议保持分类名称的一致性。

### Q2: 如何提高搜索准确度？

A:
1. 完善 `keywords` 字段，添加更多同义词
2. 使用 `policy_tags` 表添加语义标签
3. 集成向量搜索（Milvus）实现语义匹配
4. 利用 `schema_hints` 表帮助 LLM 理解表结构

### Q3: 如何处理多轮对话？

A: 结合 `query_history` 表记录用户查询历史，使用 session_id 关联同一会话的多次查询。

### Q4: 数据库性能优化建议？

A:
- 使用索引（已创建常用字段索引）
- 定期使用 `VACUUM` 清理数据库
- 对大文本字段考虑分表存储
- 高频查询考虑使用缓存（Redis）

---

## 文件结构

```
database/
├── policy_qa.db                    # 主数据库文件
├── initialize_db.py                # 初始化脚本
├── README.md                       # 本文档
├── schema/
│   └── policy_qa_schema.sql        # 数据库 Schema
└── seed_data/
    ├── generate_qa_data.py         # QA 对生成脚本
    └── policy_qa_初始数据.json      # 初始 QA 数据
```

---

## 相关资源

- [ChatDB 项目文档](https://github.com/your-org/chatdb)
- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [SQLite 官方文档](https://www.sqlite.org/docs.html)
- [Milvus 向量数据库](https://milvus.io/)

---

## 版本历史

- **v1.0.0** (2025-11-09)
  - 初始版本发布
  - 支持汽车补贴、家电换新、消费券、数码补贴4大类政策
  - 包含10个验证QA对、12个政策文档
  - 完整的表结构和索引优化

---

## 许可证

本项目仅供内部使用，政策数据版权归济南市政府所有。
