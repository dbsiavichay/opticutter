from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base schema: camelCase in the API contract, snake_case internally."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # also accepts snake_case input
        from_attributes=True,  # allows building responses from ORM models
    )
