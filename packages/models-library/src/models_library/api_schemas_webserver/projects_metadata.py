from typing import Literal, TypeAlias

from models_library.projects_nodes_io import NodeID
from models_library.utils.services_io import JsonSchemaDict
from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt

from ..projects import ProjectID
from ._base import InputSchema, OutputSchema

# Limits metadata values
MetaValueType: TypeAlias = StrictBool | StrictInt | StrictFloat | str
MetadataDict: TypeAlias = dict[str, MetaValueType]


class ProjectMetadataGet(OutputSchema):
    project_uuid: ProjectID
    custom: MetadataDict = Field(
        default_factory=dict, description="Custom key-value map"
    )


class ProjectMetadataUpdate(InputSchema):
    custom: MetadataDict


class ProjectMetadataPortGet(BaseModel):
    key: NodeID = Field(
        ...,
        description="Project port's unique identifer. Same as the UUID of the associated port node",
    )
    kind: Literal["input", "output"]
    content_schema: JsonSchemaDict | None = Field(
        None,
        description="jsonschema for the port's value. SEE https://json-schema.org/understanding-json-schema/",
    )
