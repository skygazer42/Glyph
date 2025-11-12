#!/usr/bin/env python3
"""
Fix chatsession.connection_id foreign key so Text2SQL can create sessions even without a DB connection.

This script:
1. Drops the existing foreign key constraint (if any).
2. Makes connection_id nullable.
3. Recreates the constraint with ON DELETE SET NULL / ON UPDATE CASCADE.
"""

import os
import sys
from pathlib import Path
from typing import Optional

import pymysql
from pymysql.constants import CLIENT

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parents[1]


def load_mysql_config() -> dict[str, str]:
    return {
        "host": os.getenv("DATABASE__MYSQL_HOST", "localhost"),
        "port": int(os.getenv("DATABASE__MYSQL_PORT", "3306")),
        "user": os.getenv("DATABASE__MYSQL_USER", "glyph"),
        "password": os.getenv("DATABASE__MYSQL_PASSWORD", "glyph"),
        "database": os.getenv("DATABASE__MYSQL_DB", "policy_db"),
    }


def drop_existing_fk(cursor: pymysql.cursors.Cursor, table: str, constraint: Optional[str]) -> None:
    if constraint:
        cursor.execute(f"ALTER TABLE {table} DROP FOREIGN KEY `{constraint}`;")


def find_fk_name(cursor: pymysql.cursors.Cursor, table: str) -> Optional[str]:
    cursor.execute(
        """
        SELECT constraint_name
        FROM information_schema.TABLE_CONSTRAINTS
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND constraint_type = 'FOREIGN KEY'
        """,
        (table,),
    )
    rows = cursor.fetchall()
    for row in rows:
        return row["constraint_name"]
    return None


def main() -> int:
    if load_dotenv:
        load_dotenv(BASE_DIR / ".env")
    cfg = load_mysql_config()
    conn = pymysql.connect(
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
    try:
        with conn.cursor() as cursor:
            fk_name = find_fk_name(cursor, "chatsession")
            if fk_name:
                print(f"Dropping existing foreign key constraint: {fk_name}")
                drop_existing_fk(cursor, "chatsession", fk_name)
            else:
                print("No existing foreign key found on chatsession.connection_id")

            print("Making connection_id nullable...")
            cursor.execute("ALTER TABLE chatsession MODIFY COLUMN connection_id INT NULL;")

            print("Adding ON DELETE SET NULL constraint...")
            cursor.execute(
                """
                ALTER TABLE chatsession
                ADD CONSTRAINT fk_chatsession_connection
                    FOREIGN KEY (connection_id)
                    REFERENCES dbconnection(id)
                    ON DELETE SET NULL
                    ON UPDATE CASCADE;
                """
            )
        print("Chatsession foreign key updated successfully.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
