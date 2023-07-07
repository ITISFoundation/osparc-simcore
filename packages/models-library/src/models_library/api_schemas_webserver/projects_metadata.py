from typing import TypeAlias

from pydantic import Field, StrictBool, StrictFloat, StrictInt

from ..projects import ProjectID
from ._base import InputSchema, OutputSchema

# Limits metadata values
MetaValueType: TypeAlias = StrictBool | StrictInt | StrictFloat | str
MetadataDict: TypeAlias = dict[str, MetaValueType]


class ProjectCustomMetadataGet(OutputSchema):
    project_uuid: ProjectID
    metadata: MetadataDict = Field(
        default_factory=dict, description="Custom key-value map"
    )


class ProjectCustomMetadataUpdate(InputSchema):
    metadata: MetadataDict
