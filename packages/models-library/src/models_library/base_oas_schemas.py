"""
    Base model classes for schemas in OpenAPI specs (OAS)

"""

from pydantic import BaseModel, Extra


class BaseInputSchemaModel(BaseModel):
    class Config:
        allow_population_by_field_name = False
        extra = Extra.forbid
        allow_mutations = False


class BaseOutputSchemaModel(BaseModel):
    class Config:
        allow_population_by_field_name = True
        extra = Extra.ignore  # Used to prune extra fields from internal data
        allow_mutations = False
