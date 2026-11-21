"""Utility helpers for executing SQL queries via DBAccess."""

from __future__ import annotations

from typing import List, Dict, Any
from dataclasses import dataclass

from app.models.database import DBConnection
from app.persistence.db.access import DBAccess


@dataclass(frozen=True)
class ConnectionSettings:
    """Plain connection values that can safely leave an ORM Session's thread."""

    db_type: str
    host: str
    database_name: str
    username: str
    password_encrypted: str
    port: int

    @classmethod
    def from_connection(cls, connection: DBConnection) -> "ConnectionSettings":
        """从数据库连接记录复制建立连接所需的配置字段。"""
        return cls(db_type=connection.db_type, host=connection.host,
                   database_name=connection.database_name, username=connection.username,
                   password_encrypted=connection.password_encrypted, port=connection.port)


def _build_db_access(connection: DBConnection | ConnectionSettings) -> DBAccess:
    """依据连接配置建立 MySQL 或 PostgreSQL 访问对象；不支持的数据库类型直接报错。"""
    db_access = DBAccess()
    db_type = connection.db_type.lower()

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
    elif db_type == "snowflake":
        # Snowflake support has been removed; keep explicit error to surface misconfiguration.
        raise ValueError("Snowflake connections are no longer supported. Please use MySQL/PostgreSQL.")
    else:  # pragma: no cover
        raise ValueError(f"Unsupported database type: {connection.db_type}")

    return db_access


def execute_query(connection: DBConnection | ConnectionSettings, sql: str) -> List[Dict[str, Any]]:
    """Execute ``sql`` against the provided ``connection`` and return dictionaries."""
    db_access = _build_db_access(connection)
    try:
        return db_access.run_sql(sql).to_dict("records")
    finally:
        db_access.close()


__all__ = ["ConnectionSettings", "execute_query"]
