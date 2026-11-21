"""Snapshot live stores before the explicitly authorized regional replacement."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from pymilvus import Collection, connections

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "resources/archive/pre_changzhou_20261121"


def write_json(path: Path, value: object) -> None:
    """Create a frozen snapshot once; never overwrite its original contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")


def main() -> None:
    """Read vectors, policy SQL tables and active file hashes without mutations."""
    os.chdir(ROOT)
    load_dotenv(ROOT / ".env.siliconflow.local", override=True)
    load_dotenv(ROOT / ".env", override=False)
    from app.config.app_config import settings
    from scripts.seed_mysql_text2sql import connect_mysql, load_mysql_config

    vector_path = ARCHIVE / "milvus_before.json"
    if not vector_path.exists():
        alias = "changzhou-migration-snapshot"
        connections.connect(
            alias=alias,
            host=settings.database.milvus_host,
            port=str(settings.database.milvus_port),
        )
        try:
            collection = Collection(
                settings.database.milvus_collection_name, using=alias
            )
            collection.load()
            rows = collection.query(
                expr="", output_fields=["*"], limit=16384, consistency_level="Strong"
            )
            # Convert numpy vectors while retaining every coordinate for restoration.
            for row in rows:
                row["embedding"] = [float(value) for value in row["embedding"]]
            write_json(vector_path, {"collection": collection.name, "records": rows})
        finally:
            connections.disconnect(alias)
    snapshot = json.loads(vector_path.read_text(encoding="utf-8"))
    print("Vector snapshot:", len(snapshot["records"]), "records")
    print(
        "Original vector titles:",
        [
            row["title"]
            for row in snapshot["records"]
            if not row["source"].startswith("http")
        ],
    )

    sql_path = ARCHIVE / "mysql_before.json"
    if not sql_path.exists():
        connection = connect_mysql(load_mysql_config())
        try:
            tables = {}
            with connection.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                existing = {next(iter(row.values())) for row in cursor.fetchall()}
                for table in [
                    "policy_documents",
                    "policy_entities",
                    "policy_qa_pairs",
                    "policy_tags",
                    "policy_relationships",
                    "policy_change_log",
                    "schema_hints",
                    "query_history",
                ]:
                    if table in existing:
                        cursor.execute(f"SELECT * FROM `{table}`")
                        tables[table] = cursor.fetchall()
            write_json(
                sql_path,
                {
                    "database": load_mysql_config()["database"],
                    "available_tables": sorted(existing),
                    "policy_tables": tables,
                },
            )
        finally:
            connection.close()
    sql = json.loads(sql_path.read_text(encoding="utf-8"))
    print(
        "SQL database:", sql["database"], "available tables:", sql["available_tables"]
    )
    sql = sql["policy_tables"]
    print("SQL counts:", {table: len(rows) for table, rows in sql.items()})
    print(
        "SQL document identity:",
        [
            {key: row[key] for key in ["doc_id", "title", "source_file", "metadata"]}
            for row in sql.get("policy_documents", [])
        ],
    )

    files_path = ARCHIVE / "files_before.json"
    if not files_path.exists():
        files = []
        for directory in [
            "rules",
            "resources/faq",
            "resources/data/process",
            "resources/data/raw",
            "resources/data/lightrag",
            "resources/data/policy_catalog",
            "resources/database/seed_data",
            "uploads",
        ]:
            for path in (ROOT / directory).rglob("*"):
                if path.is_file():
                    files.append(
                        {
                            "path": path.relative_to(ROOT).as_posix(),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "bytes": path.stat().st_size,
                        }
                    )
        write_json(files_path, files)
    files = json.loads(files_path.read_text(encoding="utf-8"))
    print(
        "Snapshot file groups:",
        dict(Counter(row["path"].split("/")[0] for row in files)),
    )
    print(
        "Legacy process roots:",
        [p.name for p in (ROOT / "resources/data/process").glob("*.md")],
    )
    print("Rules:", [p.name for p in (ROOT / "rules").glob("*.yaml")])


if __name__ == "__main__":
    main()
