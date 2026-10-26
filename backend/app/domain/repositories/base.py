from typing import Generic, TypeVar, List, Optional, Any
from app.domain.ports.ports import RepositoryPort

T = TypeVar("T")

class BaseRepository(RepositoryPort[T], Generic[T]):
    """Clase base de repositorio de dominio que implementa el contrato del puerto."""
    def get_by_id(self, id: Any) -> Optional[T]:
        raise NotImplementedError
        
    def list(self, skip: int = 0, limit: int = 100, filters: dict = None, sort_by: str = None) -> List[T]:
        raise NotImplementedError
        
    def create(self, entity: T) -> T:
        raise NotImplementedError
        
    def update(self, id: Any, data: dict) -> Optional[T]:
        raise NotImplementedError
        
    def delete(self, id: Any) -> bool:
        raise NotImplementedError

