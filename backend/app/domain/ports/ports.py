"""
Domain Ports Module
Contratos e interfaces puras de puertos según la Arquitectura Hexagonal.
"""
from typing import Generic, TypeVar, List, Optional, Any
from abc import ABC, abstractmethod

T = TypeVar("T")

class RepositoryPort(Generic[T], ABC):
    """Puerto base para repositorios de acceso a datos."""
    @abstractmethod
    def get_by_id(self, id: Any) -> Optional[T]:
        pass

    @abstractmethod
    def list(self, skip: int = 0, limit: int = 100, filters: dict = None, sort_by: str = None) -> List[T]:
        pass

    @abstractmethod
    def create(self, entity: T) -> T:
        pass

    @abstractmethod
    def update(self, id: Any, data: dict) -> Optional[T]:
        pass

    @abstractmethod
    def delete(self, id: Any) -> bool:
        pass


class NotificationPort(ABC):
    """Puerto para servicios de notificaciones (Email, WhatsApp, Push)."""
    @abstractmethod
    def send_notification(self, recipient: str, message: str, title: Optional[str] = None) -> bool:
        pass


class StoragePort(ABC):
    """Puerto para servicios de almacenamiento de archivos (S3, Drive, Local)."""
    @abstractmethod
    def upload_file(self, file_content: bytes, destination_path: str) -> str:
        pass

