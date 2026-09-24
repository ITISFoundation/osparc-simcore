from pydantic import Field, StrictBool, StrictFloat, StrictInt

from ..projects import ProjectID
from ._base import InputSchema, OutputSchema

# Limits metadata values
type MetaValueType = StrictBool | StrictInt | StrictFloat | str
type MetadataDict = dict[str, MetaValueType]


class ProjectMetadataGet(OutputSchema):
    project_uuid: ProjectID
    custom: MetadataDict = Field(default_factory=dict, description="Custom key-value map")


class ProjectMetadataUpdate(InputSchema):
    custom: MetadataDict
