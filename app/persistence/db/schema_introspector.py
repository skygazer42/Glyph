"""
Schema introspection helpers for Text2SQL.

These utilities read the physical database schema (currently MySQL only)
and populate the ORM-managed metadata tables:
- DBConnection
- SchemaTable
- SchemaColumn
- SchemaRelationship

They are intended to be invoked from initialization scripts so that the
Text2SQL pipeline can reliably discover tables/columns/relationships
without requiring Neo4j or manual metadata management.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import pymysql
from sqlalchemy.orm import Session

from app.models.database import DBConnection, SchemaColumn, SchemaRelationship, SchemaTable, ValueMapping


@dataclass
class ColumnInfo:
    """保存结构内省得到的列名称、类型和键约束标记。"""

    name: str
    data_type: str
    is_pk: bool
    is_unique: bool
    is_fk: bool


def _open_mysql_connection(connection: DBConnection) -> pymysql.connections.Connection:
    """Open a raw PyMySQL connection based on a DBConnection row."""
    return pymysql.connect(
        host=connection.host,
        port=connection.port,
        user=connection.username,
        password=connection.password_encrypted,
        database=connection.database_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def _load_mysql_tables(
    mysql_connection: pymysql.connections.Connection,
    database_name: str,
) -> List[Dict[str, str]]:
    """Return basic table info from information_schema.tables."""
    with mysql_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT TABLE_NAME AS table_name, TABLE_TYPE AS table_type
            FROM information_schema.tables
            WHERE TABLE_SCHEMA = %s
              AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
            """,
            (database_name,),
        )
        return list(cursor.fetchall())


def _load_mysql_columns(
    mysql_connection: pymysql.connections.Connection,
    database_name: str,
) -> Dict[str, List[ColumnInfo]]:
    """
    Load column-level metadata keyed by table_name.

    Includes primary/unique/foreign-key flags so we can populate SchemaColumn.
    """
    # Column basics
    with mysql_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                TABLE_NAME,
                COLUMN_NAME,
                DATA_TYPE,
                COLUMN_KEY
            FROM information_schema.columns
            WHERE TABLE_SCHEMA = %s
            """,
            (database_name,),
        )
        rows = list(cursor.fetchall())

    # Foreign key detection
    with mysql_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                TABLE_NAME,
                COLUMN_NAME
            FROM information_schema.key_column_usage
            WHERE TABLE_SCHEMA = %s
              AND REFERENCED_TABLE_NAME IS NOT NULL
            """,
            (database_name,),
        )
        foreign_key_columns = {(row["TABLE_NAME"], row["COLUMN_NAME"]) for row in cursor.fetchall()}

    table_columns: Dict[str, List[ColumnInfo]] = {}
    for row in rows:
        table_name = row["TABLE_NAME"]
        column_name = row["COLUMN_NAME"]
        column_key = row["COLUMN_KEY"].upper()
        is_pk = column_key == "PRI"
        is_unique = column_key in ("PRI", "UNI")
        is_fk = (table_name, column_name) in foreign_key_columns

        column_info = ColumnInfo(
            name=column_name,
            data_type=row["DATA_TYPE"],
            is_pk=is_pk,
            is_unique=is_unique,
            is_fk=is_fk,
        )
        table_columns.setdefault(table_name, []).append(column_info)

    return table_columns


def _load_mysql_relationships(
    mysql_connection: pymysql.connections.Connection,
    database_name: str,
) -> List[Tuple[str, str, str, str]]:
    """
    Load foreign-key relationships as tuples:
    (source_table, source_column, target_table, target_column)
    """
    with mysql_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                TABLE_NAME        AS source_table,
                COLUMN_NAME       AS source_column,
                REFERENCED_TABLE_NAME  AS target_table,
                REFERENCED_COLUMN_NAME AS target_column
            FROM information_schema.key_column_usage
            WHERE TABLE_SCHEMA = %s
              AND REFERENCED_TABLE_NAME IS NOT NULL
            """,
            (database_name,),
        )
        rows = list(cursor.fetchall())

    relationships: List[Tuple[str, str, str, str]] = []
    for row in rows:
        relationships.append(
            (
                row["source_table"],
                row["source_column"],
                row["target_table"],
                row["target_column"],
            )
        )
    return relationships


def refresh_mysql_schema_metadata(db: Session, connection: DBConnection) -> None:
    """
    Introspect the MySQL schema for ``connection`` and refresh SchemaTable / SchemaColumn /
    SchemaRelationship records accordingly.

    This function is idempotent for a given connection_id: it wipes existing metadata for
    that connection and re-creates it from information_schema.
    """
    # 1. Open raw MySQL connection to the target database
    mysql_connection = _open_mysql_connection(connection)
    try:
        tables = _load_mysql_tables(mysql_connection, connection.database_name)
        table_columns = _load_mysql_columns(mysql_connection, connection.database_name)
        relationships = _load_mysql_relationships(mysql_connection, connection.database_name)
    finally:
        mysql_connection.close()

    try:
        # Bulk deletes do not trigger ORM cascades; remove dependent mappings first.
        column_ids = db.query(SchemaColumn.id).join(SchemaTable).filter(
            SchemaTable.connection_id == connection.id
        )
        db.query(ValueMapping).filter(ValueMapping.column_id.in_(column_ids)).delete(
            synchronize_session=False
        )
        # 2. Clear previous metadata for this connection
        db.query(SchemaRelationship).filter(
            SchemaRelationship.connection_id == connection.id
        ).delete(synchronize_session=False)

        # Delete columns via cascade by first deleting tables, or delete columns explicitly
        # then tables to be explicit.
        db.query(SchemaColumn).filter(
            SchemaColumn.table_id.in_(
                db.query(SchemaTable.id).filter(SchemaTable.connection_id == connection.id)
            )
        ).delete(synchronize_session=False)

        db.query(SchemaTable).filter(
            SchemaTable.connection_id == connection.id
        ).delete(synchronize_session=False)

        db.flush()

        # 3. Insert new tables
        table_name_to_id: Dict[str, int] = {}
        for table_info in tables:
            name = table_info["table_name"]
            schema_table = SchemaTable(
                connection_id=connection.id,
                table_name=name,
                description=None,
                ui_metadata=None,
            )
            db.add(schema_table)
            db.flush()  # obtain id
            table_name_to_id[name] = schema_table.id

            # 4. Insert columns for this table
            for column_info in table_columns.get(name, []):
                column = SchemaColumn(
                    table_id=schema_table.id,
                    column_name=column_info.name,
                    data_type=column_info.data_type,
                    description=None,
                    is_primary_key=column_info.is_pk,
                    is_foreign_key=column_info.is_fk,
                    is_unique=column_info.is_unique,
                )
                db.add(column)

        db.flush()

        # Build a lookup from (table_name, column_name) -> SchemaColumn.id
        column_lookup: Dict[Tuple[str, str], int] = {}
        all_columns = (
            db.query(SchemaTable.table_name, SchemaColumn.id, SchemaColumn.column_name)
            .join(SchemaColumn, SchemaColumn.table_id == SchemaTable.id)
            .filter(SchemaTable.connection_id == connection.id)
            .all()
        )
        for table_name, column_id, column_name in all_columns:
            column_lookup[(table_name, column_name)] = column_id

        # 5. Insert relationships
        for source_table, source_column, target_table, target_column in relationships:
            source_table_id = table_name_to_id.get(source_table)
            target_table_id = table_name_to_id.get(target_table)
            source_column_id = column_lookup.get((source_table, source_column))
            target_column_id = column_lookup.get((target_table, target_column))
            if any(value is None for value in (source_table_id, target_table_id, source_column_id, target_column_id)):
                continue

            relationship = SchemaRelationship(
                connection_id=connection.id,
                source_table_id=source_table_id,
                source_column_id=source_column_id,
                target_table_id=target_table_id,
                target_column_id=target_column_id,
                relationship_type="foreign_key",
                description=None,
            )
            db.add(relationship)

        db.commit()

    except Exception:
        db.rollback()
        raise
