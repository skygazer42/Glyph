"""Database connection metadata endpoints.

These endpoints expose DBConnection records so that frontends can:
- List available connections
- Let users pick a connection for Text2SQL scenarios
"""

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.persistence.db.session import SessionLocal
from app.persistence import crud


class DBConnectionInfo(BaseModel):
    id: int
    name: str
    db_type: str
    host: str
    port: int
    database_name: str


router = APIRouter()


@router.get("/connections", response_model=List[DBConnectionInfo])
def list_connections() -> List[DBConnectionInfo]:
    """List all registered DB connections (for Text2SQL etc.)."""
    db = SessionLocal()
    try:
        conns = db.query(crud.db_connection.model).all()
        return [
            DBConnectionInfo(
                id=c.id,
                name=c.name,
                db_type=c.db_type,
                host=c.host,
                port=c.port,
                database_name=c.database_name,
            )
            for c in conns
        ]
    finally:
        db.close()


@router.get("/connections/{connection_id}", response_model=DBConnectionInfo)
def get_connection(connection_id: int) -> DBConnectionInfo:
    """Get a single DB connection by id."""
    db = SessionLocal()
    try:
        conn = crud.db_connection.get(db, id=connection_id)
        if not conn:
            raise HTTPException(status_code=404, detail="DB connection not found")
        return DBConnectionInfo(
            id=conn.id,
            name=conn.name,
            db_type=conn.db_type,
            host=conn.host,
            port=conn.port,
            database_name=conn.database_name,
        )
    finally:
        db.close()

