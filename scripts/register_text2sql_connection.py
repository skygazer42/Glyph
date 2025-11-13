#!/usr/bin/env python3
"""Register a demo DB connection for the Text2SQL agent.

Steps performed:
1. Ensure ORM metadata tables exist.
2. Insert (or reuse) a sqlite connection pointing to resources/sql/policy_demo.db.
"""

from app.persistence.db.session import SessionLocal
from app.persistence.db.base import Base
from app.persistence.db.session import engine
from app.persistence import crud
from app.schemas.db_connection import DBConnectionCreate

CONNECTION_NAME = "Policy Demo SQLite"
SQLITE_PATH = "resources/sql/policy_demo.db"


def main() -> None:
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        existing = crud.db_connection.get_by_name(db, name=CONNECTION_NAME)
        if existing:
            print(f"✅ DB connection already exists (id={existing.id}).")
            return
        conn = crud.db_connection.create(
            db=db,
            obj_in=DBConnectionCreate(
                name=CONNECTION_NAME,
                db_type="sqlite",
                host="localhost",
                port=0,
                username="sqlite",
                password="sqlite",
                database_name=SQLITE_PATH,
            ),
        )
        print(f"✅ Created sqlite connection with id={conn.id} -> {SQLITE_PATH}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
