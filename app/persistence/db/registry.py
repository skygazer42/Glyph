"""Register every ORM mapping before creating sessions or database tables."""

from app.models.base import Base as Base
from app.models import chat_history, database

__all__ = ["Base", "chat_history", "database"]
