from typing import TypeAlias

from pydantic import Field, StrictBool, StrictFloat, StrictInt

from ..projects import ProjectID
from ._base import InputSchema, OutputSchema

# Limits metadata values
MetaValueType: TypeAlias = StrictBool | StrictInt | StrictFloat | str  # noqa: UP040
MetadataDict: TypeAlias = dict[str, MetaValueType]  # noqa: UP040


class ProjectMetadataGet(OutputSchema):
    project_uuid: ProjectID
    custom: MetadataDict = Field(default_factory=dict, description="Custom key-value map")


class ProjectMetadataUpdate(InputSchema):
    custom: MetadataDict
