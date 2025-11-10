"""Pydantic schemas for table relationships."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SchemaRelationshipBase(BaseModel):
    connection_id: int
    source_table_id: int
    source_column_id: int
    target_table_id: int
    target_column_id: int
    relationship_type: Optional[str] = None
    description: Optional[str] = None


class SchemaRelationshipCreate(SchemaRelationshipBase):
    pass


class SchemaRelationshipUpdate(BaseModel):
    source_table_id: Optional[int] = None
    source_column_id: Optional[int] = None
    target_table_id: Optional[int] = None
    target_column_id: Optional[int] = None
    relationship_type: Optional[str] = None
    description: Optional[str] = None


__all__ = ["SchemaRelationshipCreate", "SchemaRelationshipUpdate"]
