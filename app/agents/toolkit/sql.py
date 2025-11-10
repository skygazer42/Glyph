"""Simple wrapper around the Text2SQL service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.db_connection import DBConnection
from app.schemas.query import QueryResponse
from app.services.text2sql_service import Text2SQLService


class Text2SQLTool:
    def __init__(self, service: Text2SQLService | None = None) -> None:
        self.service = service or Text2SQLService()

    def run(self, db: Session, connection: DBConnection, query: str) -> QueryResponse:
        return self.service.run(db, connection, query)


__all__ = ["Text2SQLTool"]
