from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.db_connection import DBConnection
    from app.models.schema_column import SchemaColumn
    from app.models.schema_table import SchemaTable


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
