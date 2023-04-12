"""
    Base model classes for schemas in OpenAPI specs (OAS) for this service

"""

from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, Extra


class InputSchema(BaseModel):
    class Config:
        allow_population_by_field_name = False
        extra = Extra.ignore  # Non-strict inputs policy: Used to prune extra field
        allow_mutations = False
        alias_generator = snake_to_camel


class OutputSchema(BaseModel):
    class Config:
        allow_population_by_field_name = True
        extra = Extra.ignore  # Used to prune extra fields from internal data
        allow_mutations = False
        alias_generator = snake_to_camel
