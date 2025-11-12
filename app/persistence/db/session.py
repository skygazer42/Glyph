from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote_plus

from app.core.config import settings

db_cfg = settings.database
password = quote_plus(db_cfg.mysql_password)
SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{db_cfg.mysql_user}:{password}@"
    f"{db_cfg.mysql_host}:{db_cfg.mysql_port}/{db_cfg.mysql_db}"
    "?charset=utf8mb4"
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
