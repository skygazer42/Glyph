"""CRUD operations for a connection's Text2SQL schema metadata."""

from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.database import SchemaColumn, SchemaRelationship, SchemaTable, ValueMapping
from app.persistence.crud.base import CRUDBase
from app.schemas.database import (
    SchemaColumnCreate,
    SchemaColumnUpdate,
    SchemaRelationshipCreate,
    SchemaRelationshipUpdate,
    SchemaTableCreate,
    SchemaTableUpdate,
    ValueMappingCreate,
    ValueMappingUpdate,
)


class CRUDSchemaTable(CRUDBase[SchemaTable, SchemaTableCreate, SchemaTableUpdate]):
    def get_by_connection(
        self, db: Session, *, connection_id: int, skip: int = 0, limit: int = 100
    ) -> List[SchemaTable]:
        return (
            db.query(SchemaTable)
            .filter(SchemaTable.connection_id == connection_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_name_and_connection(
        self, db: Session, *, table_name: str, connection_id: int
    ) -> Optional[SchemaTable]:
        return (
            db.query(SchemaTable)
            .filter(
                SchemaTable.table_name == table_name,
                SchemaTable.connection_id == connection_id
            )
            .first()
        )


schema_table = CRUDSchemaTable(SchemaTable)


class CRUDSchemaColumn(CRUDBase[SchemaColumn, SchemaColumnCreate, SchemaColumnUpdate]):
    def get_by_table(
        self, db: Session, *, table_id: int, skip: int = 0, limit: int = 100
    ) -> List[SchemaColumn]:
        return (
            db.query(SchemaColumn)
            .filter(SchemaColumn.table_id == table_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_name_and_table(
        self, db: Session, *, column_name: str, table_id: int
    ) -> Optional[SchemaColumn]:
        return (
            db.query(SchemaColumn)
            .filter(
                SchemaColumn.column_name == column_name,
                SchemaColumn.table_id == table_id
            )
            .first()
        )

    def get_by_table_ids(self, db: Session, *, table_ids: List[int]) -> List[SchemaColumn]:
        if not table_ids:
            return []
        return (
            db.query(SchemaColumn)
            .filter(SchemaColumn.table_id.in_(table_ids))
            .all()
        )


schema_column = CRUDSchemaColumn(SchemaColumn)


class CRUDSchemaRelationship(CRUDBase[SchemaRelationship, SchemaRelationshipCreate, SchemaRelationshipUpdate]):
    def get_by_connection(
        self, db: Session, *, connection_id: int, skip: int = 0, limit: int = 100
    ) -> List[SchemaRelationship]:
        return (
            db.query(SchemaRelationship)
            .filter(SchemaRelationship.connection_id == connection_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_source_table(
        self, db: Session, *, source_table_id: int
    ) -> List[SchemaRelationship]:
        return (
            db.query(SchemaRelationship)
            .filter(SchemaRelationship.source_table_id == source_table_id)
            .all()
        )

    def get_by_target_table(
        self, db: Session, *, target_table_id: int
    ) -> List[SchemaRelationship]:
        return (
            db.query(SchemaRelationship)
            .filter(SchemaRelationship.target_table_id == target_table_id)
            .all()
        )

    def get_by_columns(
        self, db: Session, *, source_column_id: int, target_column_id: int
    ) -> Optional[SchemaRelationship]:
        return (
            db.query(SchemaRelationship)
            .filter(
                SchemaRelationship.source_column_id == source_column_id,
                SchemaRelationship.target_column_id == target_column_id
            )
            .first()
        )

    def get_by_table_ids(self, db: Session, *, table_ids: List[int]) -> List[SchemaRelationship]:
        if not table_ids:
            return []
        return (
            db.query(SchemaRelationship)
            .filter(
                or_(
                    SchemaRelationship.source_table_id.in_(table_ids),
                    SchemaRelationship.target_table_id.in_(table_ids),
                )
            )
            .all()
        )


schema_relationship = CRUDSchemaRelationship(SchemaRelationship)


class CRUDValueMapping(CRUDBase[ValueMapping, ValueMappingCreate, ValueMappingUpdate]):
    def get_by_column(
        self, db: Session, *, column_id: int, skip: int = 0, limit: int = 100
    ) -> List[ValueMapping]:
        return (
            db.query(ValueMapping)
            .filter(ValueMapping.column_id == column_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_column_and_term(
        self, db: Session, *, column_id: int, nl_term: str
    ) -> Optional[ValueMapping]:
        return (
            db.query(ValueMapping)
            .filter(
                ValueMapping.column_id == column_id,
                ValueMapping.nl_term == nl_term
            )
            .first()
        )


value_mapping = CRUDValueMapping(ValueMapping)
