from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker

from app.config.app_config import settings

database_settings = settings.database
SQLALCHEMY_DATABASE_URL = URL.create(
    "mysql+pymysql", username=database_settings.mysql_user, password=database_settings.mysql_password,
    host=database_settings.mysql_host, port=database_settings.mysql_port, database=database_settings.mysql_db,
    query={"charset": "utf8mb4"},
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
