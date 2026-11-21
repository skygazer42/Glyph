import logging
from sqlalchemy.orm import Session

from app.persistence.crud.db_connection import db_connection as db_connection_crud
from app.schemas.database import DBConnectionCreate
from app.persistence.db.registry import Base
from app.persistence.db.session import engine

logger = logging.getLogger(__name__)


def init_db() -> None:
    # Create tables
    """依据已注册模型创建缺失表；不执行已有表结构的数据迁移。"""
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created")


def create_initial_data(db: Session) -> None:
    # Check if we already have connections
    """仅在示例连接名称不存在时创建示例配置；创建操作通过 CRUD 自行提交。"""
    connection = db_connection_crud.get_by_name(db, name="Sample Database")
    if connection is None:
        connection_in = DBConnectionCreate(
            name="Sample Database",
            db_type="mysql",
            host="localhost",
            port=3306,
            username="root",
            password="mysql",
            database_name="chat_db"
        )
        connection = db_connection_crud.create(db=db, obj_in=connection_in)
        logger.info(f"Created sample connection: {connection.name}")


if __name__ == "__main__":
    from app.persistence.db.session import SessionLocal

    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        init_db()
        create_initial_data(db)
    finally:
        db.close()
