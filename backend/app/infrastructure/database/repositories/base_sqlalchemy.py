from sqlalchemy.orm import Session
from typing import TypeVar, Generic, Type, List, Optional, Any
from app.domain.repositories.base import BaseRepository

T = TypeVar("T")

class SQLAlchemyRepository(BaseRepository[T], Generic[T]):
    def __init__(self, model: Type[T], db: Session):
        self.model = model
        self.db = db
        
    def get_by_id(self, id: Any) -> Optional[T]:
        return self.db.get(self.model, id)
        
    def list(self, skip: int = 0, limit: int = 100, filters: dict = None, sort_by: str = None) -> List[T]:
        query = self.db.query(self.model)
        if filters:
            for attr, value in filters.items():
                if value is not None:
                    if hasattr(self.model, attr):
                        query = query.filter(getattr(self.model, attr) == value)
        if sort_by:
            parts = sort_by.strip().split()
            field = parts[0]
            if hasattr(self.model, field):
                column = getattr(self.model, field)
                if len(parts) > 1 and parts[1].lower() == "desc":
                    query = query.order_by(column.desc())
                else:
                    query = query.order_by(column.asc())
        return query.offset(skip).limit(limit).all()
        
    def create(self, entity: T) -> T:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity
        
    def update(self, id: Any, data: dict) -> Optional[T]:
        db_obj = self.get_by_id(id)
        if not db_obj:
            return None
        for key, value in data.items():
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
        
    def delete(self, id: Any) -> bool:
        db_obj = self.get_by_id(id)
        if not db_obj:
            return False
        self.db.delete(db_obj)
        self.db.commit()
        return True
