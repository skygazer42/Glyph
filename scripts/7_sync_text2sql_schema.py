#!/usr/bin/env python3
"""Sync Text2SQL schema metadata from the primary MySQL database.

This script will:
1. Ensure there is a DBConnection record pointing to the configured MySQL policy DB.
2. Introspect the MySQL schema and populate SchemaTable/SchemaColumn/SchemaRelationship
   so that the Text2SQL agent can discover tables/columns/relationships without Neo4j.

It is safe to run multiple times; existing metadata for the connection will be replaced.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    # Ensure project root on sys.path
    root_dir = Path(__file__).resolve().parents[1]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from app.core.config import settings
    from app.persistence.db.session import SessionLocal
    from app.persistence import crud
    from app.schemas.db_connection import DBConnectionCreate
    from app.persistence.db.schema_introspector import refresh_mysql_schema_metadata

    db = SessionLocal()
    try:
        db_settings = settings.database

        # 1. Ensure a DBConnection pointing to the main MySQL policy DB exists
        default_name = "Policy Demo MySQL"
        connection = crud.db_connection.get_by_name(db, name=default_name)
        if not connection:
            conn_in = DBConnectionCreate(
                name=default_name,
                db_type="mysql",
                host=db_settings.mysql_host,
                port=db_settings.mysql_port,
                username=db_settings.mysql_user,
                password=db_settings.mysql_password,
                database_name=db_settings.mysql_db,
            )
            connection = crud.db_connection.create(db=db, obj_in=conn_in)
            print(f"[OK] Created DBConnection '{connection.name}' (id={connection.id})")
        else:
            print(f"[INFO] Reusing existing DBConnection '{connection.name}' (id={connection.id})")

        # 2. Refresh schema metadata for this connection
        print(f"[INFO] Introspecting MySQL schema for database '{connection.database_name}' ...")
        refresh_mysql_schema_metadata(db, connection)
        print("[OK] Text2SQL schema metadata synchronized successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    main()

