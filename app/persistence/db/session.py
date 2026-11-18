"""Database engine, session factory, and request-owned sessions."""

from collections.abc import Generator

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.app_config import settings
from app.persistence.db import registry  # noqa: F401 - register both sides of ORM relationships

database_settings = settings.database
SQLALCHEMY_DATABASE_URL = URL.create(
    "mysql+pymysql",
    username=database_settings.mysql_user,
    password=database_settings.mysql_password,
    host=database_settings.mysql_host,
    port=database_settings.mysql_port,
    database=database_settings.mysql_db,
    query={"charset": "utf8mb4"},
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
