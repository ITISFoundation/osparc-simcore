from typing import Any

from models_library.projects_nodes_io import NodeID
from pydantic import BaseConfig, BaseModel, Extra, Field


class _InputSchemaConfig(BaseConfig):
    class Config:
        allow_population_by_field_name = False
        extra = Extra.forbid
        allow_mutations = False


class _OutputSchemaConfig(BaseConfig):
    class Config:
        allow_population_by_field_name = True
        extra = Extra.ignore  # Used to prune extra fields from internal data
        allow_mutations = False


class _ProjectIOBase(BaseModel):
    key: NodeID = Field(
        ...,
        description="Project port's unique identifer. Same as the UUID of the associated port node",
    )
    value: Any = Field(..., description="Value assigned to this i/o port")


class ProjectInputUpdate(_ProjectIOBase):
    class Config(_InputSchemaConfig):
        ...


class ProjectInputGet(_OutputSchemaConfig, _ProjectIOBase):
    label: str

    class Config(_InputSchemaConfig):
        ...


class ProjectOutputGet(_ProjectIOBase):
    label: str

    class Config(_OutputSchemaConfig):
        ...
