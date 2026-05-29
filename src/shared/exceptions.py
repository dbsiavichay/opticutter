class AppError(Exception):
    """Error de aplicación traducible a una respuesta HTTP.

    Las capas de aplicación/dominio lanzan estas excepciones; el handler
    registrado en ``shared.errors`` las traduce a JSON con su ``status_code``.
    """

    status_code = 400

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class EntityNotFoundError(AppError):
    """No se encontró la entidad solicitada."""

    status_code = 404

    def __init__(self, entity: str, entity_id):
        super().__init__(f"{entity} {entity_id} no encontrado")


class ConflictError(AppError):
    """Violación de una restricción de unicidad/integridad."""

    status_code = 409


class BusinessRuleError(AppError):
    """Se violó una regla de negocio."""

    status_code = 422


class ValidationError(AppError):
    """Error de validación de dominio."""

    status_code = 422
