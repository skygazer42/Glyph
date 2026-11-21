#!/usr/bin/env python3
"""Initialize database tables with python -m scripts.create_tables."""

from __future__ import annotations

from app.persistence.db.registry import Base
from app.persistence.db.session import engine


def main() -> None:
    """创建已登记 ORM 模型中尚不存在的表；不执行现有表结构迁移。"""
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created.")


if __name__ == "__main__":
    main()
