#!/usr/bin/env python3
"""Initialize database tables with python -m scripts.create_tables."""

from __future__ import annotations

from app.persistence.db.registry import Base
from app.persistence.db.session import engine


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created.")


if __name__ == "__main__":
    main()
