"""Pydantic schemas for table metadata."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SchemaTableBase(BaseModel):
    connection_id: int
    table_name: str = Field(..., description="表名称")
    description: Optional[str] = None
    ui_metadata: Optional[Dict[str, Any]] = None


class SchemaTableCreate(SchemaTableBase):
    pass


class SchemaTableUpdate(BaseModel):
    table_name: Optional[str] = None
    description: Optional[str] = None
    ui_metadata: Optional[Dict[str, Any]] = None


__all__ = ["SchemaTableCreate", "SchemaTableUpdate"]
