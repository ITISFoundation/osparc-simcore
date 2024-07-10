from typing import Any

from pydantic import BaseModel, Field

from ..projects_nodes_io import NodeID
from ._base import InputSchemaWithoutCamelCase, OutputSchema


class _ProjectIOBase(BaseModel):
    key: NodeID = Field(
        ...,
        description="Project port's unique identifer. Same as the UUID of the associated port node",
    )
    value: Any = Field(..., description="Value assigned to this i/o port")


class ProjectInputUpdate(_ProjectIOBase):
    class Config(InputSchemaWithoutCamelCase):
        ...


class ProjectInputGet(OutputSchema, _ProjectIOBase):
    label: str

    class Config(InputSchemaWithoutCamelCase):
        ...


class ProjectOutputGet(_ProjectIOBase):
    label: str

    class Config(OutputSchema):
        ...
