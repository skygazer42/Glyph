"""Utility helpers for executing SQL queries via DBAccess."""

from __future__ import annotations

from typing import List, Dict, Any

from app.models.db_connection import DBConnection
from app.persistence.db.dbaccess import DBAccess


def _build_db_access(connection: DBConnection) -> DBAccess:
    db_access = DBAccess()
    db_type = (connection.db_type or "").lower()

    if db_type == "mysql":
        db_access.connect_to_mysql(
            host=connection.host,
            dbname=connection.database_name,
            user=connection.username,
            password=connection.password_encrypted,
            port=connection.port,
        )
    elif db_type in {"postgres", "postgresql"}:
        db_access.connect_to_postgres(
            host=connection.host,
            dbname=connection.database_name,
            user=connection.username,
            password=connection.password_encrypted,
            port=connection.port,
        )
    elif db_type == "sqlite":
        db_access.connect_to_sqlite(connection.database_name)
    elif db_type == "clickhouse":
        db_access.connect_to_clickhouse(
            host=connection.host,
            dbname=connection.database_name,
            user=connection.username,
            password=connection.password_encrypted,
            port=connection.port,
        )
    elif db_type == "snowflake":
        db_access.connect_to_snowflake(
            account=connection.host,
            username=connection.username,
            password=connection.password_encrypted,
            database=connection.database_name,
        )
    else:  # pragma: no cover
        raise ValueError(f"Unsupported database type: {connection.db_type}")

    return db_access


def execute_query(connection: DBConnection, sql: str) -> List[Dict[str, Any]]:
    """Execute ``sql`` against the provided ``connection`` and return dictionaries."""
    db_access = _build_db_access(connection)
    result = db_access.run_sql(sql)
    if result is None:
        return []
    if hasattr(result, "to_dict"):
        return result.to_dict("records")
    return list(result)


__all__ = ["execute_query"]
