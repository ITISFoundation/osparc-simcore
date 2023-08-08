"""
    Base model classes for schemas in OpenAPI specs (OAS) for this service

"""

from typing import Any

from pydantic import BaseModel, Extra

from ..utils.change_case import snake_to_camel


class EmptyModel(BaseModel):
    # Used to represent body={}
    class Config:
        extra = Extra.forbid


class InputSchema(BaseModel):
    class Config:  # type: ignore[pydantic-alias]
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

    def data(
        self,
        *,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        **kwargs
    ) -> dict[str, Any]:
        """Helper function to get envelope's data as a dict"""
        return self.dict(
            by_alias=True,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            **kwargs
        )

    def data_json(
        self,
        *,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        **kwargs
    ) -> str:
        """Helper function to get envelope's data as a json str"""
        return self.json(
            by_alias=True,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            **kwargs
        )
