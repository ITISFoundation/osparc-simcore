from models_library.utils.change_case import camel_to_snake
from pydantic import BaseModel, ConfigDict


class ApiServerOutputSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=camel_to_snake,
        populate_by_name=True,
        extra="ignore",  # Used to prune extra fields from internal data
        frozen=True,
    )


class ApiServerInputSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=camel_to_snake,
        populate_by_name=True,
        extra="ignore",  # Used to prune extra fields from internal data
        frozen=True,
    )
