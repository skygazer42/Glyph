"""Pydantic schemas for column metadata."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class SchemaColumnBase(BaseModel):
    table_id: int
    column_name: str
    data_type: str
    description: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_unique: bool = False


class SchemaColumnCreate(SchemaColumnBase):
    pass


class SchemaColumnUpdate(BaseModel):
    column_name: Optional[str] = None
    data_type: Optional[str] = None
    description: Optional[str] = None
    is_primary_key: Optional[bool] = None
    is_foreign_key: Optional[bool] = None
    is_unique: Optional[bool] = None


__all__ = ["SchemaColumnCreate", "SchemaColumnUpdate"]
