from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.db_connection import DBConnection
    from app.models.schema_column import SchemaColumn
    from app.models.schema_relationship import SchemaRelationship


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
