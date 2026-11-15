from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.schema_relationship import SchemaRelationship
    from app.models.schema_table import SchemaTable
    from app.models.value_mapping import ValueMapping


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
