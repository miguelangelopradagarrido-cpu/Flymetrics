"""
Domain Exceptions Module
Contiene las excepciones puras del negocio y del dominio de Flymetrics.
"""

class DomainException(Exception):
    """Excepcion base del dominio."""
    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class EntityNotFoundException(DomainException):
    """Lanzada cuando una entidad de negocio requerida no existe."""
    def __init__(self, entity_name: str, identifier: object):
        super().__init__(
            message=f"{entity_name} con identificador '{identifier}' no fue encontrado.",
            code="ENTITY_NOT_FOUND"
        )


class BusinessRuleValidationException(DomainException):
    """Lanzada cuando se infringe una regla estricta de negocio."""
    def __init__(self, rule_message: str):
        super().__init__(
            message=rule_message,
            code="BUSINESS_RULE_VIOLATION"
        )


class UnauthorizedOperationException(DomainException):
    """Lanzada cuando una accion de dominio no esta permitida para el actor."""
    def __init__(self, message: str = "Operacion no autorizada en el dominio."):
        super().__init__(
            message=message,
            code="UNAUTHORIZED_DOMAIN_OPERATION"
        )

