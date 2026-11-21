from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """使用调用方提供的 Session 查询模型；写操作自行提交，Session 的关闭仍由调用方负责。"""

    def __init__(self, model: Type[ModelType]) -> None:
        """绑定待维护的 SQLAlchemy 模型；每次操作所用 Session 由调用方传入。"""
        self.model = model

    @staticmethod
    def _commit(db: Session) -> None:
        """提交当前 Session；失败时尝试回滚并重新抛出，不保证回滚本身不会失败。"""
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        """按主键读取模型；未命中返回 None，不提交事务。"""
        return db.get(self.model, id)

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """按偏移和数量读取模型列表；无结果返回空列表，不指定额外排序。"""
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        """从输入模型创建记录并提交、刷新；提交后的刷新异常不会撤销已提交记录。"""
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        self._commit(db)
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """仅更新输入中出现的映射列并提交、刷新；字典与模型的未设置字段处理不同。"""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        for field in self.model.__mapper__.column_attrs:
            if field.key in update_data:
                setattr(db_obj, field.key, update_data[field.key])
        db.add(db_obj)
        self._commit(db)
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: Any) -> Optional[ModelType]:
        """按主键删除并提交；未命中返回 None，不执行删除提交。"""
        obj = db.get(self.model, id)
        if obj is None:
            return None
        db.delete(obj)
        self._commit(db)
        return obj
