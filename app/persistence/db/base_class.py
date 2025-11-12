"""
Re-export the shared SQLAlchemy declarative Base used by all ORM models.

Historically this project defined a second Base class here, which caused
`Base.metadata.create_all()` to operate on an empty metadata set (hence the
missing ChatSession/ChatMessage tables in MySQL). Now we directly reuse the
Base from `app.models.base` so every ORM model shares the same metadata tree.
"""

from app.models.base import Base  # noqa: F401

__all__ = ["Base"]
