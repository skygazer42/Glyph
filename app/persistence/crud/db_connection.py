"""Connection metadata persistence and related-data cleanup."""

import logging
from typing import Any, Dict, Optional, Union

from neo4j import GraphDatabase
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config.app_config import settings
from app.models.database import DBConnection, SchemaColumn, SchemaRelationship, SchemaTable, ValueMapping
from app.persistence.crud.base import CRUDBase
from app.schemas.database import DBConnectionCreate, DBConnectionUpdate

logger = logging.getLogger(__name__)


class CRUDDBConnection(CRUDBase[DBConnection, DBConnectionCreate, DBConnectionUpdate]):
    """维护数据库连接配置及关联元数据；凭据字段名称不代表实际加密。"""

    def create(self, db: Session, *, obj_in: DBConnectionCreate) -> DBConnection:
        # shortcut: 凭据沿用明文存储契约；引入受管密钥与数据迁移时改为可逆加密。
        """保存连接配置并提交、刷新；当前将输入密码原样写入 password_encrypted 字段。"""
        db_obj = DBConnection(
            name=obj_in.name,
            db_type=obj_in.db_type,
            host=obj_in.host,
            port=obj_in.port,
            username=obj_in.username,
            password_encrypted=obj_in.password,
            database_name=obj_in.database_name,
        )
        db.add(db_obj)
        self._commit(db)
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, *, db_obj: DBConnection, obj_in: Union[DBConnectionUpdate, Dict[str, Any]]
    ) -> DBConnection:
        """将非 None 的 password 映射到现有凭据字段，再按基础更新流程提交。"""
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
        """返回首个同名连接配置；未命中返回 None。"""
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
