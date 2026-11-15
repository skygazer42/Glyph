from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.schema_column import SchemaColumn


class ValueMapping(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    column_id: Mapped[int] = mapped_column(Integer, ForeignKey("schemacolumn.id"), nullable=False)
    nl_term: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    db_value: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    column: Mapped[SchemaColumn] = relationship("SchemaColumn", back_populates="value_mappings")
