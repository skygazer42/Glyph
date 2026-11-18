#!/usr/bin/env python3
"""Sync Text2SQL metadata with python -m scripts.sync_text2sql_schema.

This script will:
1. Ensure there is a DBConnection record pointing to the configured MySQL policy DB.
2. Introspect the MySQL schema and populate SchemaTable/SchemaColumn/SchemaRelationship
   so that the Text2SQL agent can discover tables/columns/relationships without Neo4j.

It is safe to run multiple times; existing metadata for the connection will be replaced.
"""

from __future__ import annotations

from app.config.app_config import settings
from app.persistence.crud.db_connection import db_connection
from app.persistence.db.schema_introspector import refresh_mysql_schema_metadata
from app.persistence.db.session import SessionLocal
from app.schemas.database import DBConnectionCreate, DBConnectionUpdate


def main() -> None:
    db = SessionLocal()
    try:
        db_settings = settings.database

        # 1. Ensure a DBConnection pointing to the main MySQL policy DB exists
        default_name = "Policy Demo MySQL"
        connection = db_connection.get_by_name(db, name=default_name)
        conn_in = DBConnectionCreate(
            name=default_name,
            db_type="mysql",
            host=db_settings.mysql_host,
            port=db_settings.mysql_port,
            username=db_settings.mysql_user,
            password=db_settings.mysql_password,
            database_name=db_settings.mysql_db,
        )
        if connection is None:
            connection = db_connection.create(db=db, obj_in=conn_in)
            print(f"[OK] Created DBConnection '{connection.name}' (id={connection.id})")
        else:
            connection = db_connection.update(
                db=db, db_obj=connection,
                obj_in=DBConnectionUpdate(**conn_in.model_dump()),
            )
            print(f"[INFO] Updated DBConnection '{connection.name}' from current configuration (id={connection.id})")

        # 2. Refresh schema metadata for this connection
        print(f"[INFO] Introspecting MySQL schema for database '{connection.database_name}' ...")
        refresh_mysql_schema_metadata(db, connection)
        print("[OK] Text2SQL schema metadata synchronized successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
