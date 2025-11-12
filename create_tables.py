from app.persistence.db.base import Base
from app.persistence.db.session import engine

# 创建所有表
Base.metadata.create_all(bind=engine)
print("所有表已创建")
