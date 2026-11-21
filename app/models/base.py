"""Declarative base shared by persistence models."""

from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """所有 ORM 模型共用的声明基类，默认以小写类名生成表名。"""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
