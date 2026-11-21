#!/usr/bin/env python3
"""Seed source-backed official policy rows with python -m scripts.seed_mysql_text2sql."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple, TypedDict, Union

import pymysql
from dotenv import load_dotenv
from uuid import NAMESPACE_URL, uuid5

from scripts.official_policy_data import load_curated_faq, load_official_policies


BASE_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = BASE_DIR / "resources/database/schema/policy_qa_schema.sql"


class MySQLConfig(TypedDict):
    """官方资料导入使用的 MySQL 连接参数。"""

    host: str
    port: int
    user: str
    password: str
    database: str


SeedValue = Union[str, int, bool, float, None]


def load_mysql_config() -> MySQLConfig:
    """Read MySQL connection settings from environment (defaults match docker-compose)."""
    return {
        "host": os.getenv("DATABASE__MYSQL_HOST", "localhost"),
        "port": int(os.getenv("DATABASE__MYSQL_PORT", "3306")),
        "user": os.getenv("DATABASE__MYSQL_USER", "glyph"),
        "password": os.getenv("DATABASE__MYSQL_PASSWORD", "glyph"),
        "database": os.getenv("DATABASE__MYSQL_DB", "policy_db"),
    }


def connect_mysql(cfg: MySQLConfig) -> pymysql.connections.Connection:
    """Create the owned connection for one transaction of official rows."""
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def mysql_schema_statements(schema_path: Path = SCHEMA_PATH) -> list[str]:
    """Convert this repository's SQLite-oriented table schema for MySQL."""
    schema_sql = schema_path.read_text(encoding="utf-8")
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
        schema_sql.replace(
            "INTEGER PRIMARY KEY AUTOINCREMENT", "INT AUTO_INCREMENT PRIMARY KEY"
        )
        .replace("AUTOINCREMENT", "AUTO_INCREMENT")
        .replace("date('now')", "CURRENT_DATE")
    )
    schema_sql = re.sub(r"(?m)^\s*--.*$", "", schema_sql)
    statements = []
    # shortcut: this repository schema has no semicolons in literals; use a SQL parser if that changes.
    for raw in schema_sql.split(";"):
        stmt = raw.strip()
        if not stmt:
            continue
        upper_stmt = stmt.upper()
        if upper_stmt.startswith("CREATE INDEX") or upper_stmt.startswith("DROP INDEX"):
            continue  # 索引对示例数据不是必需
        if upper_stmt.startswith("CREATE VIEW") or upper_stmt.startswith("DROP VIEW"):
            continue  # 视图语法与SQLite差异较大，跳过
        if upper_stmt.startswith("CREATE TABLE"):
            if "CHARSET" not in upper_stmt:
                stmt = f"{stmt} DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
        statements.append(stmt)
    return statements


def apply_schema(conn: pymysql.connections.Connection) -> None:
    """Execute the converted table schema; MySQL DDL commits independently."""
    with conn.cursor() as cursor:
        for stmt in mysql_schema_statements():
            cursor.execute(stmt)


def truncate_tables(conn: pymysql.connections.Connection, tables: List[str]) -> None:
    """清空列出的合法表名并恢复外键检查；MySQL TRUNCATE 不能由后续回滚恢复。"""
    if any(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table) is None for table in tables):
        raise ValueError("Expected unqualified MySQL table names")
    with conn.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
        try:
            for tbl in tables:
                cursor.execute(f"TRUNCATE TABLE `{tbl}`;")
        finally:
            cursor.execute("SET FOREIGN_KEY_CHECKS=1;")


def generate_documents(count: int) -> List[Dict[str, SeedValue]]:
    """从已核验官方正文生成 SQL 记录，常州地方资料优先，不合成政策事实。"""
    policies = sorted(
        load_official_policies(BASE_DIR), key=lambda item: item["scope"] == "全国"
    )
    return [
        {
            "doc_id": str(uuid5(NAMESPACE_URL, "glyph:official-policy:" + item["url"])),
            "title": item["title"],
            "category": item["topic"],
            "sub_category": item["document_kind"],
            "source_file": item["markdown_path"],
            "content": item["body"],
            "metadata": json.dumps(
                {
                    key: value
                    for key, value in item.items()
                    if key not in {"body", "markdown"}
                },
                ensure_ascii=False,
            ),
            "publish_date": item.get("published_date"),
            "effective_date": item.get("effective_date"),
            "expiry_date": item.get("expires_date"),
        }
        for item in policies[:count]
    ]


def generate_entities(docs: List[Dict[str, SeedValue]]) -> List[Dict[str, SeedValue]]:
    """仅保存原始目录中明确的发布机关和地区，不推断补贴金额或资格。"""
    entities = []
    for doc in docs:
        metadata = json.loads(str(doc["metadata"]))
        for name, field in [("发布机关", "issuer"), ("适用地区", "scope")]:
            entities.append(
                {
                    "doc_id": doc["doc_id"],
                    "entity_type": name,
                    "entity_name": name,
                    "entity_value": metadata[field],
                    "entity_unit": "",
                }
            )
    return entities


def generate_qa_pairs(docs: List[Dict[str, SeedValue]]) -> List[Dict[str, SeedValue]]:
    """仅关联经过原文摘录核验的问答；无官方来源的样例不会生成答案。"""
    by_url = {
        json.loads(str(doc["metadata"]))["url"]: doc
        for doc in docs
        if "metadata" in doc
    }
    if not by_url:
        return []
    pairs = load_curated_faq(BASE_DIR, load_official_policies(BASE_DIR))
    return [
        {
            "question": entry["question"],
            "answer": entry["answer"],
            "doc_id": by_url[entry["source"]]["doc_id"],
            "category": entry["topic"],
            "keywords": ",".join(entry["tags"]),
            "difficulty_level": 3,
            "query_type": "informational",
            "verified": True,
            "metadata": json.dumps(entry, ensure_ascii=False),
        }
        for entry in pairs
        if entry["source"] in by_url
    ]


def generate_tags(docs: List[Dict[str, SeedValue]]) -> List[Dict[str, SeedValue]]:
    """使用资料已有的主题和地区标签，不生成随机属性。"""
    return [
        {
            "doc_id": doc["doc_id"],
            "tag_name": doc["category"],
            "tag_type": "主题",
            "weight": 1.0,
        }
        for doc in docs
    ]


def generate_schema_hints() -> List[Tuple[str, str, str, str]]:
    """返回 Text2SQL 演示表及字段的中文说明记录。"""
    return [
        ("policy_documents", "doc_id", "description", "文档唯一标识符，例如 doc_0001"),
        (
            "policy_documents",
            "category",
            "description",
            "政策分类：汽车消费补贴/家电以旧换新/消费券等",
        ),
        (
            "policy_entities",
            "entity_type",
            "description",
            "实体类型：补贴金额/申请条件/办理流程等",
        ),
        (
            "policy_qa_pairs",
            "query_type",
            "description",
            "查询类型：informational/procedural/eligibility",
        ),
    ]


def bulk_insert(
    conn: pymysql.connections.Connection,
    sql: str,
    rows: Sequence[Union[Mapping[str, SeedValue], tuple]],
) -> None:
    """在调用方连接上参数化批量插入；空批次跳过，提交和回滚由调用方负责。"""
    if not rows:
        return
    with conn.cursor() as cursor:
        cursor.executemany(sql, rows)


def seed_mysql(conn: pymysql.connections.Connection, doc_count: int) -> None:
    """向调用方事务插入尚未收录的官方资料及证据问答，不提交事务。"""
    docs = generate_documents(doc_count)
    all_docs = docs
    if docs:
        with conn.cursor() as cursor:
            placeholders = ",".join(["%s"] * len(docs))
            cursor.execute(
                f"SELECT doc_id FROM policy_documents WHERE doc_id IN ({placeholders})",
                [doc["doc_id"] for doc in docs],
            )
            existing = {row["doc_id"] for row in cursor.fetchall()}
        docs = [doc for doc in docs if doc["doc_id"] not in existing]
    entities = generate_entities(docs)
    qa_pairs = generate_qa_pairs(all_docs)
    tags = generate_tags(docs)
    schema_hints = generate_schema_hints()
    with conn.cursor() as cursor:
        if all_docs:
            placeholders = ",".join(["%s"] * len(all_docs))
            cursor.execute(
                f"SELECT doc_id, question FROM policy_qa_pairs WHERE doc_id IN ({placeholders})",
                [doc["doc_id"] for doc in all_docs],
            )
            existing_pairs = {
                (row["doc_id"], row["question"]) for row in cursor.fetchall()
            }
            qa_pairs = [
                row
                for row in qa_pairs
                if (row["doc_id"], row["question"]) not in existing_pairs
            ]
        cursor.execute(
            "SELECT table_name, column_name, hint_type, hint_text FROM schema_hints WHERE language = 'zh'"
        )
        existing_hints = {
            (row["table_name"], row["column_name"], row["hint_type"], row["hint_text"])
            for row in cursor.fetchall()
        }
        schema_hints = [hint for hint in schema_hints if hint not in existing_hints]

    bulk_insert(
        conn,
        """
        INSERT INTO policy_documents
        (doc_id, title, category, sub_category, source_file, content, metadata, publish_date, effective_date, expiry_date, status)
        VALUES (%(doc_id)s, %(title)s, %(category)s, %(sub_category)s, %(source_file)s, %(content)s, %(metadata)s,
                %(publish_date)s, %(effective_date)s, %(expiry_date)s, 'collected')
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
        (question, answer, doc_id, category, keywords, difficulty_level, query_type, verified, metadata)
        VALUES (%(question)s, %(answer)s, %(doc_id)s, %(category)s, %(keywords)s, %(difficulty_level)s, %(query_type)s, %(verified)s, %(metadata)s)
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
    parser = argparse.ArgumentParser(
        description="Seed verified official sources for Text2SQL."
    )
    parser.add_argument(
        "--documents",
        type=int,
        default=200,
        help="Maximum official source documents to import (default: 200)",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Skip executing the schema SQL (use existing tables).",
    )
    reset = parser.add_mutually_exclusive_group()
    reset.add_argument(
        "--truncate",
        action="store_true",
        help="Explicitly discard existing demo rows before seeding (MySQL TRUNCATE cannot be rolled back).",
    )
    reset.add_argument(
        "--no-truncate",
        dest="truncate",
        action="store_false",
        help="Keep existing data (default; retained compatibility flag).",
    )
    parser.set_defaults(truncate=False)
    return parser.parse_args()


def main() -> None:
    """装配连接并提交种子数据，失败时回滚未提交插入并关闭连接。

    建表与显式 --truncate 各自具有 MySQL DDL 提交语义，不属于插入回滚范围。
    """
    args = parse_args()
    if args.documents < 0:
        raise ValueError("documents must not be negative")
    load_dotenv(BASE_DIR / ".env")
    cfg = load_mysql_config()
    conn = connect_mysql(cfg)
    try:
        if not args.skip_schema:
            print("[*] Applying schema ...")
            apply_schema(conn)
        if args.truncate:
            print("[*] Truncating existing data ...")
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
        print(f"[*] Generating {args.documents} policy documents + related rows ...")
        seed_mysql(conn, args.documents)
        conn.commit()
        print("[OK] MySQL seed data ready. Text2SQL agent can now query policy_db.")
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
