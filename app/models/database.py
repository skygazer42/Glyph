"""Database connections and their Text2SQL schema metadata."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.chat_history import ChatSession


class DBConnection(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    db_type: Mapped[str] = mapped_column(String(50), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(String(255), nullable=False)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    tables: Mapped[list[SchemaTable]] = relationship("SchemaTable", back_populates="connection")
    chat_sessions: Mapped[list[ChatSession]] = relationship("ChatSession", back_populates="connection")


class SchemaTable(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    connection_id: Mapped[int] = mapped_column(Integer, ForeignKey("dbconnection.id"), nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ui_metadata: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    connection: Mapped[DBConnection] = relationship("DBConnection", back_populates="tables")
    columns: Mapped[list[SchemaColumn]] = relationship("SchemaColumn", back_populates="table", cascade="all, delete-orphan")
    source_relationships: Mapped[list[SchemaRelationship]] = relationship("SchemaRelationship",
                                       foreign_keys="[SchemaRelationship.source_table_id]",
                                       back_populates="source_table")
    target_relationships: Mapped[list[SchemaRelationship]] = relationship("SchemaRelationship",
                                       foreign_keys="[SchemaRelationship.target_table_id]",
                                       back_populates="target_table")


class SchemaColumn(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    table_id: Mapped[int] = mapped_column(Integer, ForeignKey("schematable.id"), nullable=False, index=True)
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary_key: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    is_foreign_key: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    is_unique: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)  # 添加唯一标记
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    table: Mapped[SchemaTable] = relationship("SchemaTable", back_populates="columns")
    value_mappings: Mapped[list[ValueMapping]] = relationship("ValueMapping", back_populates="column", cascade="all, delete-orphan")
    source_relationships: Mapped[list[SchemaRelationship]] = relationship("SchemaRelationship",
                                       foreign_keys="[SchemaRelationship.source_column_id]",
                                       back_populates="source_column")
    target_relationships: Mapped[list[SchemaRelationship]] = relationship("SchemaRelationship",
                                       foreign_keys="[SchemaRelationship.target_column_id]",
                                       back_populates="target_column")


class SchemaRelationship(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    connection_id: Mapped[int] = mapped_column(Integer, ForeignKey("dbconnection.id"), nullable=False)
    source_table_id: Mapped[int] = mapped_column(Integer, ForeignKey("schematable.id"), nullable=False)
    source_column_id: Mapped[int] = mapped_column(Integer, ForeignKey("schemacolumn.id"), nullable=False)
    target_table_id: Mapped[int] = mapped_column(Integer, ForeignKey("schematable.id"), nullable=False)
    target_column_id: Mapped[int] = mapped_column(Integer, ForeignKey("schemacolumn.id"), nullable=False)
    relationship_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g., '1-to-1', '1-to-N', 'N-to-M'
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # 关系描述
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    connection: Mapped[DBConnection] = relationship("DBConnection")
    source_table: Mapped[SchemaTable] = relationship("SchemaTable", foreign_keys=[source_table_id], back_populates="source_relationships")
    source_column: Mapped[SchemaColumn] = relationship("SchemaColumn", foreign_keys=[source_column_id], back_populates="source_relationships")
    target_table: Mapped[SchemaTable] = relationship("SchemaTable", foreign_keys=[target_table_id], back_populates="target_relationships")
    target_column: Mapped[SchemaColumn] = relationship("SchemaColumn", foreign_keys=[target_column_id], back_populates="target_relationships")


class ValueMapping(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    column_id: Mapped[int] = mapped_column(Integer, ForeignKey("schemacolumn.id"), nullable=False)
    nl_term: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    db_value: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    column: Mapped[SchemaColumn] = relationship("SchemaColumn", back_populates="value_mappings")
