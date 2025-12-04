class DomainException(Exception):
    """Excepción base para errores de dominio"""


class EntityNotFoundError(DomainException):
    """Excepción cuando no se encuentra una entidad"""

    def __init__(self, entity_name: str, entity_id: any):
        self.entity_name = entity_name
        self.entity_id = entity_id
        super().__init__(f"{entity_name} with id {entity_id} not found")


class ValidationError(DomainException):
    """Excepción para errores de validación de dominio"""


class BusinessRuleViolationError(DomainException):
    """Excepción cuando se viola una regla de negocio"""
