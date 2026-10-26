class AppException(Exception):
    """Base exception for all application errors."""
    def __init__(self, message: str, status_code: int = 400, errors: list = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors or []

class NotFoundException(AppException):
    def __init__(self, message: str = "Recurso no encontrado", errors: list = None):
        super().__init__(message, status_code=404, errors=errors)

class BadRequestException(AppException):
    def __init__(self, message: str = "Petición incorrecta", errors: list = None):
        super().__init__(message, status_code=400, errors=errors)

class UnauthorizedException(AppException):
    def __init__(self, message: str = "No autorizado", errors: list = None):
        super().__init__(message, status_code=401, errors=errors)

class ForbiddenException(AppException):
    def __init__(self, message: str = "Acceso denegado", errors: list = None):
        super().__init__(message, status_code=403, errors=errors)

class ConflictException(AppException):
    def __init__(self, message: str = "Conflicto en la operación", errors: list = None):
        super().__init__(message, status_code=409, errors=errors)

class ExternalServiceException(AppException):
    def __init__(self, message: str = "Servicio externo no disponible", errors: list = None):
        super().__init__(message, status_code=503, errors=errors)
