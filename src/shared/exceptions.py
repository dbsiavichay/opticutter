class AppError(Exception):
    """Error de aplicación traducible a una respuesta HTTP.

    Las capas de aplicación/dominio lanzan estas excepciones; el handler
    registrado en ``shared.errors`` las traduce a la envoltura ``{errors, meta}``
    usando ``status_code`` (HTTP) y ``code`` (legible por máquina).
    """

    status_code = 400
    code = "APPLICATION_ERROR"
    field: str | None = None

    def __init__(self, detail: str, *, field: str | None = None):
        self.detail = detail
        if field is not None:
            self.field = field
        super().__init__(detail)


class EntityNotFoundError(AppError):
    """No se encontró la entidad solicitada."""

    status_code = 404
    code = "NOT_FOUND"

    def __init__(self, entity: str, entity_id):
        super().__init__(f"{entity} {entity_id} no encontrado")


class ConflictError(AppError):
    """Violación de una restricción de unicidad/integridad."""

    status_code = 409
    code = "CONFLICT"


class BusinessRuleError(AppError):
    """Se violó una regla de negocio."""

    status_code = 422
    code = "BUSINESS_RULE_ERROR"


class ValidationError(AppError):
    """Error de validación de dominio."""

    status_code = 422
    code = "VALIDATION_ERROR"
