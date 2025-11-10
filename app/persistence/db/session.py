from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

db_cfg = settings.database
SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{db_cfg.mysql_user}:{db_cfg.mysql_password}@"
    f"{db_cfg.mysql_host}:{db_cfg.mysql_port}/{db_cfg.mysql_db}"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
