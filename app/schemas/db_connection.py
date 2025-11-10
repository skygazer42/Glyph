"""Schemas for managing DB connection metadata."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DBConnectionBase(BaseModel):
    name: str = Field(..., description="连接名称")
    db_type: str = Field(..., description="数据库类型")
    host: str = Field(..., description="数据库主机")
    port: int = Field(..., description="端口")
    username: str = Field(..., description="用户名")
    database_name: str = Field(..., description="数据库名称")


class DBConnectionCreate(DBConnectionBase):
    password: str = Field(..., description="数据库密码")


class DBConnectionUpdate(BaseModel):
    name: Optional[str] = None
    db_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: Optional[str] = None


__all__ = ["DBConnectionCreate", "DBConnectionUpdate"]
