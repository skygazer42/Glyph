import logging
from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session
from sqlalchemy import delete
from neo4j import GraphDatabase

from app.config.app_config import settings
from app.persistence.crud.base import CRUDBase
from app.models.db_connection import DBConnection
from app.models.schema_table import SchemaTable
from app.models.schema_column import SchemaColumn
from app.models.schema_relationship import SchemaRelationship
from app.models.value_mapping import ValueMapping
from app.schemas.db_connection import DBConnectionCreate, DBConnectionUpdate

logger = logging.getLogger(__name__)


class CRUDDBConnection(CRUDBase[DBConnection, DBConnectionCreate, DBConnectionUpdate]):
    def create(self, db: Session, *, obj_in: DBConnectionCreate) -> DBConnection:
        # 在实际应用中，应该对密码进行加密
        # 但为了解决当前的连接问题，我们暂时存储明文密码
        # password_encrypted=get_password_hash(obj_in.password),
        db_obj = DBConnection(
            name=obj_in.name,
            db_type=obj_in.db_type,
            host=obj_in.host,
            port=obj_in.port,
            username=obj_in.username,
            password_encrypted=obj_in.password,  # 暂时存储明文密码
            database_name=obj_in.database_name,
        )
        db.add(db_obj)
        self._commit(db)
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, *, db_obj: DBConnection, obj_in: Union[DBConnectionUpdate, Dict[str, Any]]
    ) -> DBConnection:
        if isinstance(obj_in, dict):
            update_data = dict(obj_in)
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        if "password" in update_data:
            password = update_data.pop("password")
            if password is not None:
                update_data["password_encrypted"] = password
        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def get_by_name(self, db: Session, *, name: str) -> Optional[DBConnection]:
        return db.query(DBConnection).filter(DBConnection.name == name).first()

    def remove(self, db: Session, *, id: int) -> Optional[DBConnection]:
        """Override the base remove method to handle deletion of related entities"""
        # First, get the connection object
        connection = db.get(self.model, id)
        if connection is None:
            return None

        try:
            # Step 0: 清理Neo4j图数据库中的相关数据
            if settings.database.use_neo4j:
                self._clean_neo4j_data(id)

            # Step 1: Delete all relationships associated with this connection
            # This must be done first because relationships reference both tables and columns
            db.execute(delete(SchemaRelationship).where(SchemaRelationship.connection_id == id))

            # Get all tables associated with this connection
            tables = db.query(SchemaTable).filter(SchemaTable.connection_id == id).all()
            table_ids = [table.id for table in tables]

            if table_ids:
                # Get all columns associated with these tables
                columns = db.query(SchemaColumn).filter(SchemaColumn.table_id.in_(table_ids)).all()
                column_ids = [column.id for column in columns]

                if column_ids:
                    # Step 2: Delete all value mappings associated with these columns
                    db.execute(delete(ValueMapping).where(ValueMapping.column_id.in_(column_ids)))

                # Step 3: Delete all columns associated with these tables
                db.execute(delete(SchemaColumn).where(SchemaColumn.table_id.in_(table_ids)))

            # Step 4: Delete all tables associated with this connection
            db.execute(delete(SchemaTable).where(SchemaTable.connection_id == id))

            # Step 5: Delete the connection itself
            db.delete(connection)
            db.commit()

            return connection
        except Exception:
            db.rollback()
            raise

    def _clean_neo4j_data(self, connection_id: int) -> None:
        """清理Neo4j图数据库中与指定连接相关的所有数据"""
        try:
            print(f"开始清理Neo4j中连接ID为{connection_id}的数据")
            # 连接到Neo4j
            with GraphDatabase.driver(
                settings.database.neo4j_uri,
                auth=(settings.database.neo4j_user, settings.database.neo4j_password),
            ) as driver, driver.session() as session:
                # 删除与此连接相关的所有节点和关系
                print(f"删除Neo4j中连接ID为{connection_id}的所有节点和关系")
                session.run(
                    "MATCH (n {connection_id: $connection_id}) DETACH DELETE n",
                    connection_id=connection_id
                )
                print(f"成功清理Neo4j中连接ID为{connection_id}的数据")

        except Exception:
            logger.warning("Neo4j cleanup failed for connection %s; continuing MySQL deletion", connection_id, exc_info=True)
            # 这里我们只记录错误，但不抛出异常，因为即使Neo4j清理失败，我们仍然希望继续删除MySQL中的数据


db_connection = CRUDDBConnection(DBConnection)
