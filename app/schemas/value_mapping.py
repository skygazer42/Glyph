"""Pydantic schemas for value-mapping records."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ValueMappingBase(BaseModel):
    column_id: int
    nl_term: str
    db_value: str


class ValueMappingCreate(ValueMappingBase):
    pass


class ValueMappingUpdate(BaseModel):
    nl_term: Optional[str] = None
    db_value: Optional[str] = None


__all__ = ["ValueMappingCreate", "ValueMappingUpdate"]
