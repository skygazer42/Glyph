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

from app.models.db_connection import DBConnection
from app.models.schema_table import SchemaTable
from app.models.schema_column import SchemaColumn
from app.models.schema_relationship import SchemaRelationship


@dataclass
class ColumnInfo:
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
    conn: pymysql.connections.Connection,
    database_name: str,
) -> List[Dict[str, str]]:
    """Return basic table info from information_schema.tables."""
    with conn.cursor() as cursor:
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
    conn: pymysql.connections.Connection,
    database_name: str,
) -> Dict[str, List[ColumnInfo]]:
    """
    Load column-level metadata keyed by table_name.

    Includes primary/unique/foreign-key flags so we can populate SchemaColumn.
    """
    # Column basics
    with conn.cursor() as cursor:
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
    with conn.cursor() as cursor:
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
        fk_rows = {(r["TABLE_NAME"], r["COLUMN_NAME"]) for r in cursor.fetchall()}

    table_columns: Dict[str, List[ColumnInfo]] = {}
    for row in rows:
        tbl = row["TABLE_NAME"]
        col = row["COLUMN_NAME"]
        col_key = (row.get("COLUMN_KEY") or "").upper()
        is_pk = col_key == "PRI"
        is_unique = col_key in ("PRI", "UNI")
        is_fk = (tbl, col) in fk_rows

        info = ColumnInfo(
            name=col,
            data_type=row.get("DATA_TYPE") or "",
            is_pk=bool(is_pk),
            is_unique=bool(is_unique),
            is_fk=bool(is_fk),
        )
        table_columns.setdefault(tbl, []).append(info)

    return table_columns


def _load_mysql_relationships(
    conn: pymysql.connections.Connection,
    database_name: str,
) -> List[Tuple[str, str, str, str]]:
    """
    Load foreign-key relationships as tuples:
    (source_table, source_column, target_table, target_column)
    """
    with conn.cursor() as cursor:
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

    rels: List[Tuple[str, str, str, str]] = []
    for r in rows:
        rels.append(
            (
                r["source_table"],
                r["source_column"],
                r["target_table"],
                r["target_column"],
            )
        )
    return rels


def refresh_mysql_schema_metadata(db: Session, connection: DBConnection) -> None:
    """
    Introspect the MySQL schema for ``connection`` and refresh SchemaTable / SchemaColumn /
    SchemaRelationship records accordingly.

    This function is idempotent for a given connection_id: it wipes existing metadata for
    that connection and re-creates it from information_schema.
    """
    # 1. Open raw MySQL connection to the target database
    conn = _open_mysql_connection(connection)
    try:
        tables = _load_mysql_tables(conn, connection.database_name)
        table_columns = _load_mysql_columns(conn, connection.database_name)
        relationships = _load_mysql_relationships(conn, connection.database_name)
    finally:
        conn.close()

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
    for t in tables:
        name = t["table_name"]
        tbl = SchemaTable(
            connection_id=connection.id,
            table_name=name,
            description=None,
            ui_metadata=None,
        )
        db.add(tbl)
        db.flush()  # obtain id
        table_name_to_id[name] = tbl.id

        # 4. Insert columns for this table
        for col in table_columns.get(name, []):
            column = SchemaColumn(
                table_id=tbl.id,
                column_name=col.name,
                data_type=col.data_type,
                description=None,
                is_primary_key=col.is_pk,
                is_foreign_key=col.is_fk,
                is_unique=col.is_unique,
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
    for tbl_name, col_id, col_name in all_columns:
        column_lookup[(tbl_name, col_name)] = col_id

    # 5. Insert relationships
    for src_table, src_col, tgt_table, tgt_col in relationships:
        src_table_id = table_name_to_id.get(src_table)
        tgt_table_id = table_name_to_id.get(tgt_table)
        src_col_id = column_lookup.get((src_table, src_col))
        tgt_col_id = column_lookup.get((tgt_table, tgt_col))
        if not all((src_table_id, tgt_table_id, src_col_id, tgt_col_id)):
            continue

        rel = SchemaRelationship(
            connection_id=connection.id,
            source_table_id=src_table_id,
            source_column_id=src_col_id,
            target_table_id=tgt_table_id,
            target_column_id=tgt_col_id,
            relationship_type="foreign_key",
            description=None,
        )
        db.add(rel)

    db.commit()

