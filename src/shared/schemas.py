from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base schema: camelCase en el contrato del API, snake_case internamente."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # acepta también snake_case en input
        from_attributes=True,  # permite construir responses desde modelos ORM
    )
