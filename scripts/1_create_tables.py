#!/usr/bin/env python3
"""Initialize database tables for the Glyph project."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from app.persistence.db.base import Base
    from app.persistence.db.session import engine

    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created.")


if __name__ == "__main__":
    main()
