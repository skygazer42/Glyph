"""Connection configuration and Text2SQL schema metadata contracts."""

from __future__ import annotations

from typing import Any, Dict, Optional

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


class ValueMappingBase(BaseModel):
    column_id: int
    nl_term: str
    db_value: str


class ValueMappingCreate(ValueMappingBase):
    pass


class ValueMappingUpdate(BaseModel):
    nl_term: Optional[str] = None
    db_value: Optional[str] = None
