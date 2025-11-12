#!/usr/bin/env python3
"""Populate the MySQL Text2SQL dataset with synthetic policy rows."""

from __future__ import annotations

import argparse
import json
import os
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
import re

import pymysql
from pymysql.constants import CLIENT

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = BASE_DIR / "resources/database/schema/policy_qa_schema.sql"


def load_mysql_config() -> Dict[str, str]:
    """Read MySQL connection settings from environment (defaults match docker-compose)."""
    return {
        "host": os.getenv("DATABASE__MYSQL_HOST", "localhost"),
        "port": int(os.getenv("DATABASE__MYSQL_PORT", "3306")),
        "user": os.getenv("DATABASE__MYSQL_USER", "glyph"),
        "password": os.getenv("DATABASE__MYSQL_PASSWORD", "glyph"),
        "database": os.getenv("DATABASE__MYSQL_DB", "policy_db"),
    }


def connect_mysql(cfg: Dict[str, str]) -> pymysql.connections.Connection:
    """Create a PyMySQL connection with multi-statement support."""
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        autocommit=True,
        client_flag=CLIENT.MULTI_STATEMENTS,
        cursorclass=pymysql.cursors.DictCursor,
    )


def apply_schema(conn: pymysql.connections.Connection) -> None:
    """Execute the full schema SQL to ensure tables exist."""
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    import re
    schema_sql = re.sub(
        r"-- ==================== 索引优化[\s\S]*?-- ==================== 视图定义 ====================",
        "-- ==================== 视图定义 ====================",
        schema_sql,
        flags=re.MULTILINE,
    )
    schema_sql = re.sub(
        r"-- ==================== 视图定义 ====================\s*(?s:.*)",
        "",
        schema_sql,
        flags=re.MULTILINE,
    )
    schema_sql = (
        schema_sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "INT AUTO_INCREMENT PRIMARY KEY")
        .replace("AUTOINCREMENT", "AUTO_INCREMENT")
        .replace("JSON", "JSON")
        .replace("date('now')", "CURRENT_DATE")
    )
    statements = []
    for raw in schema_sql.split(";"):
        stmt = raw.strip()
        if not stmt:
            continue
        upper_stmt = stmt.upper()
        if upper_stmt.startswith("CREATE INDEX") or upper_stmt.startswith("DROP INDEX"):
            continue  # 索引对示例数据不是必需
        if upper_stmt.startswith("CREATE VIEW") or upper_stmt.startswith("DROP VIEW"):
            continue  # 视图语法与SQLite差异较大，跳过
        statements.append(stmt)
    with conn.cursor() as cursor:
        for stmt in statements:
            cursor.execute(stmt)


def truncate_tables(conn: pymysql.connections.Connection, tables: List[str]) -> None:
    with conn.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
        for tbl in tables:
            cursor.execute(f"TRUNCATE TABLE {tbl};")
        cursor.execute("SET FOREIGN_KEY_CHECKS=1;")


def random_date_between(year: int = 2024) -> Tuple[str, str, str]:
    """Generate publish/effective/expiry dates."""
    start = date(year, 1, 1)
    publish = start + timedelta(days=random.randint(0, 180))
    effective = publish + timedelta(days=random.randint(0, 15))
    expiry = effective + timedelta(days=random.randint(120, 400))
    return publish.isoformat(), effective.isoformat(), expiry.isoformat()


def generate_documents(count: int) -> List[Dict[str, str]]:
    categories = [
        ("汽车消费补贴", "新能源"),
        ("家电以旧换新", "节能家电"),
        ("消费券", "泉城购"),
        ("数码产品补贴", "数码购新"),
        ("通用政策", "综合服务"),
    ]
    doc_template = (
        "为落实济南市{category}政策，本细则围绕{theme}，重点说明申请条件、补贴金额、办理流程"
        "以及监督机制。政策适用于符合条件的个人或企业，并与财政、商务等部门联动执行。"
    )
    docs: List[Dict[str, str]] = []
    for idx in range(1, count + 1):
        category, theme = random.choice(categories)
        publish, effective, expiry = random_date_between()
        docs.append(
            {
                "doc_id": f"doc_{idx:04d}",
                "title": f"{publish[:4]}年{theme}{category}实施细则",
                "category": category,
                "sub_category": theme,
                "source_file": f"auto_generated_{idx}.md",
                "content": doc_template.format(category=category, theme=theme),
                "metadata": json.dumps(
                    {
                        "region": "济南市",
                        "issuing_agency": random.choice(
                            ["商务局", "发改委", "财政局", "工信局"]
                        ),
                    },
                    ensure_ascii=False,
                ),
                "publish_date": publish,
                "effective_date": effective,
                "expiry_date": expiry,
            }
        )
    return docs


def generate_entities(docs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    entity_types = ["补贴金额", "申请条件", "办理流程", "申请材料", "时间期限"]
    entities: List[Dict[str, str]] = []
    for doc in docs:
        for _ in range(random.randint(2, 4)):
            entity_type = random.choice(entity_types)
            value = ""
            if entity_type == "补贴金额":
                value = f"{random.randint(1000, 8000)} 元"
            elif entity_type == "申请条件":
                value = "需持济南市户籍或在济缴纳社保满6个月"
            elif entity_type == "办理流程":
                value = "网上申报→街道审核→部门复核→资金拨付"
            elif entity_type == "申请材料":
                value = "身份证、购置发票、旧设备回收凭证"
            else:
                value = "政策发布之日起180天内有效"
            entities.append(
                {
                    "doc_id": doc["doc_id"],
                    "entity_type": entity_type,
                    "entity_name": f"{entity_type}-{random.randint(1,99)}",
                    "entity_value": value,
                    "entity_unit": "元" if entity_type == "补贴金额" else "",
                }
            )
    return entities


def generate_qa_pairs(docs: List[Dict[str, str]], per_doc: int = 2) -> List[Dict[str, str]]:
    qa_templates = [
        ("补贴额度是多少？", "个人最高可享受{amount}元补贴，按发票金额分档核定。"),
        ("办理流程是怎样的？", "需要完成网上申报、街道审核、部门复核并公示后发放补贴。"),
        ("申请条件有哪些限制？", "须在济南购置符合标准的新产品，并提供回收或报废证明。"),
    ]
    qa_pairs: List[Dict[str, str]] = []
    for doc in docs:
        for _ in range(per_doc):
            question_template, answer_template = random.choice(qa_templates)
            amount = random.randint(2000, 6000)
            qa_pairs.append(
                {
                    "question": f"{doc['title']} {question_template}",
                    "answer": answer_template.format(amount=amount),
                    "doc_id": doc["doc_id"],
                    "category": doc["category"],
                    "keywords": "补贴,政策",
                    "difficulty_level": random.randint(1, 3),
                    "query_type": random.choice(
                        ["informational", "procedural", "eligibility"]
                    ),
                    "verified": True,
                }
            )
    return qa_pairs


def generate_tags(docs: List[Dict[str, str]]) -> List[Dict[str, str]]:
    tags: List[Dict[str, str]] = []
    tag_pool = ["新能源", "节能", "消费券", "数字经济", "小微企业", "以旧换新"]
    for doc in docs:
        selected = random.sample(tag_pool, k=2)
        for tag in selected:
            tags.append(
                {
                    "doc_id": doc["doc_id"],
                    "tag_name": tag,
                    "tag_type": "主题",
                    "weight": round(random.uniform(0.5, 1.0), 2),
                }
            )
    return tags


def generate_schema_hints() -> List[Tuple[str, str, str, str]]:
    return [
        ("policy_documents", "doc_id", "description", "文档唯一标识符，例如 doc_0001"),
        ("policy_documents", "category", "description", "政策分类：汽车消费补贴/家电以旧换新/消费券等"),
        ("policy_entities", "entity_type", "description", "实体类型：补贴金额/申请条件/办理流程等"),
        ("policy_qa_pairs", "query_type", "description", "查询类型：informational/procedural/eligibility"),
    ]


def bulk_insert(conn: pymysql.connections.Connection, sql: str, rows: List[Tuple]) -> None:
    if not rows:
        return
    with conn.cursor() as cursor:
        cursor.executemany(sql, rows)


def seed_mysql(conn: pymysql.connections.Connection, doc_count: int) -> None:
    docs = generate_documents(doc_count)
    entities = generate_entities(docs)
    qa_pairs = generate_qa_pairs(docs)
    tags = generate_tags(docs)
    schema_hints = generate_schema_hints()

    bulk_insert(
        conn,
        """
        INSERT INTO policy_documents
        (doc_id, title, category, sub_category, source_file, content, metadata, publish_date, effective_date, expiry_date, status)
        VALUES (%(doc_id)s, %(title)s, %(category)s, %(sub_category)s, %(source_file)s, %(content)s, %(metadata)s,
                %(publish_date)s, %(effective_date)s, %(expiry_date)s, 'active')
        """,
        docs,
    )
    bulk_insert(
        conn,
        """
        INSERT INTO policy_entities
        (doc_id, entity_type, entity_name, entity_value, entity_unit)
        VALUES (%(doc_id)s, %(entity_type)s, %(entity_name)s, %(entity_value)s, %(entity_unit)s)
        """,
        entities,
    )
    bulk_insert(
        conn,
        """
        INSERT INTO policy_qa_pairs
        (question, answer, doc_id, category, keywords, difficulty_level, query_type, verified)
        VALUES (%(question)s, %(answer)s, %(doc_id)s, %(category)s, %(keywords)s, %(difficulty_level)s, %(query_type)s, %(verified)s)
        """,
        qa_pairs,
    )
    bulk_insert(
        conn,
        """
        INSERT INTO policy_tags
        (doc_id, tag_name, tag_type, weight)
        VALUES (%(doc_id)s, %(tag_name)s, %(tag_type)s, %(weight)s)
        """,
        tags,
    )
    bulk_insert(
        conn,
        """
        INSERT INTO schema_hints
        (table_name, column_name, hint_type, hint_text, language)
        VALUES (%s, %s, %s, %s, 'zh')
        """,
        schema_hints,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed MySQL data for Text2SQL demos.")
    parser.add_argument(
        "--documents",
        type=int,
        default=12,
        help="How many synthetic policy documents to generate (default: 12)",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Skip executing the schema SQL (use existing tables).",
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Do not truncate existing data before inserting.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if load_dotenv:
        load_dotenv(BASE_DIR / ".env")
    cfg = load_mysql_config()
    conn = connect_mysql(cfg)
    try:
        if not args.skip_schema:
            print("→ Applying schema ...")
            apply_schema(conn)
        if not args.no_truncate:
            print("→ Truncating existing data ...")
            truncate_tables(
                conn,
                [
                    "policy_entities",
                    "policy_qa_pairs",
                    "policy_tags",
                    "query_history",
                    "policy_relationships",
                    "policy_change_log",
                    "schema_hints",
                    "policy_documents",
                ],
            )
        print(f"→ Generating {args.documents} policy documents + related rows ...")
        seed_mysql(conn, args.documents)
        print("✓ MySQL seed data ready. Text2SQL agent can now query policy_db.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
