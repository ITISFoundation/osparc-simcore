"""
    Base model classes for schemas in OpenAPI specs (OAS) for this service

"""

from typing import Any

from pydantic import BaseModel, ConfigDict

from ..utils.change_case import snake_to_camel


class EmptyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InputSchemaWithoutCamelCase(BaseModel):
    # Added to tmp keep backwards compatibility
    # until all bodies are updated
    #
    model_config = ConfigDict(
        populate_by_name=False, extra="ignore", allow_mutations=False
    )


class InputSchema(BaseModel):
    model_config = InputSchemaWithoutCamelCase.model_config | ConfigDict(
        alias_generator=snake_to_camel
    )


class OutputSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        extra="ignore",
        allow_mutations=False,
    )

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
        return self.model_dump_json(
            by_alias=True,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            **kwargs
        )
