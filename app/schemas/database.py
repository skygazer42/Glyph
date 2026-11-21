"""Connection configuration and Text2SQL schema metadata contracts."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DBConnectionBase(BaseModel):
    """数据库连接的非密码基础配置，不负责建立连接。"""

    name: str = Field(..., description="连接名称")
    db_type: str = Field(..., description="数据库类型")
    host: str = Field(..., description="数据库主机")
    port: int = Field(..., description="端口")
    username: str = Field(..., description="用户名")
    database_name: str = Field(..., description="数据库名称")


class DBConnectionCreate(DBConnectionBase):
    """创建连接配置的输入，包含待保存的原始密码。"""

    password: str = Field(..., description="数据库密码")


class DBConnectionUpdate(BaseModel):
    """连接配置的部分更新输入；不在模型层执行凭据加密。"""

    name: Optional[str] = None
    db_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: Optional[str] = None


class SchemaTableBase(BaseModel):
    """描述指定连接下的表元数据及展示信息。"""

    connection_id: int
    table_name: str = Field(..., description="表名称")
    description: Optional[str] = None
    ui_metadata: Optional[Dict[str, Any]] = None


class SchemaTableCreate(SchemaTableBase):
    """新增表元数据的输入，不负责创建数据库实体表。"""

    pass


class SchemaTableUpdate(BaseModel):
    """更新已登记表元数据的可选字段。"""

    table_name: Optional[str] = None
    description: Optional[str] = None
    ui_metadata: Optional[Dict[str, Any]] = None


class SchemaColumnBase(BaseModel):
    """描述指定表下的列及其约束标记。"""

    table_id: int
    column_name: str
    data_type: str
    description: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_unique: bool = False


class SchemaColumnCreate(SchemaColumnBase):
    """新增列元数据的输入，不执行数据库 DDL。"""

    pass


class SchemaColumnUpdate(BaseModel):
    """表达列元数据的部分更新。"""

    column_name: Optional[str] = None
    data_type: Optional[str] = None
    description: Optional[str] = None
    is_primary_key: Optional[bool] = None
    is_foreign_key: Optional[bool] = None
    is_unique: Optional[bool] = None


class SchemaRelationshipBase(BaseModel):
    """描述连接内源表列与目标表列之间的元数据关系。"""

    connection_id: int
    source_table_id: int
    source_column_id: int
    target_table_id: int
    target_column_id: int
    relationship_type: Optional[str] = None
    description: Optional[str] = None


class SchemaRelationshipCreate(SchemaRelationshipBase):
    """登记表列关系的创建输入，不创建实际外键。"""

    pass


class SchemaRelationshipUpdate(BaseModel):
    """表达已登记关系的部分更新。"""

    source_table_id: Optional[int] = None
    source_column_id: Optional[int] = None
    target_table_id: Optional[int] = None
    target_column_id: Optional[int] = None
    relationship_type: Optional[str] = None
    description: Optional[str] = None


class ValueMappingBase(BaseModel):
    """将指定列的自然语言词语映射到数据库取值。"""

    column_id: int
    nl_term: str
    db_value: str


class ValueMappingCreate(ValueMappingBase):
    """创建列取值映射的输入。"""

    pass


class ValueMappingUpdate(BaseModel):
    """表达自然语言词语与数据库取值映射的部分更新。"""

    nl_term: Optional[str] = None
    db_value: Optional[str] = None
