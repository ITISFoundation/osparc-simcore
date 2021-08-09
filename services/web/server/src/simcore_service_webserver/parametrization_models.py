from datetime import datetime
from typing import Callable, Optional, Union
from uuid import UUID

from models_library.projects_nodes import OutputID
from pydantic import (
    AnyUrl,
    BaseModel,
    Field,
    PositiveInt,
    StrictBool,
    StrictFloat,
    StrictInt,
)

BuiltinTypes = Union[StrictBool, StrictInt, StrictFloat, str]

## Domain models --------
class Parameter(BaseModel):
    name: str
    value: BuiltinTypes

    # TODO: same parameter in different nodes?
    node_id: UUID = Field(..., description="Id of parametrized node")
    output_id: OutputID = Field(..., description="Output where parameter is exposed")


class Snapshot(BaseModel):
    id: PositiveInt = Field(..., description="Unique snapshot identifier")
    label: Optional[str] = Field(None, description="Unique human readable display name")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of the time snapshot was taken from parent. Notice that parent might change with time",
    )

    parent_id: UUID = Field(..., description="Parent's project uuid")
    project_id: UUID = Field(..., description="Current project's uuid")


## API models ----------


class ParameterApiModel(Parameter):
    url: AnyUrl
    # url_output: AnyUrl


class SnapshotApiModel(Snapshot):
    url: AnyUrl
    url_parent: AnyUrl
    url_project: AnyUrl
    url_parameters: Optional[AnyUrl] = None

    @classmethod
    def from_snapshot(cls, snapshot: Snapshot, url_for: Callable) -> "SnapshotApiModel":
        return cls(
            url=url_for(
                "get_snapshot",
                project_id=snapshot.project_id,
                snapshot_id=snapshot.id,
            ),
            url_parent=url_for("get_project", project_id=snapshot.parent_id),
            url_project=url_for("get_project", project_id=snapshot.project_id),
            url_parameters=url_for(
                "get_snapshot_parameters",
                project_id=snapshot.parent_id,
                snapshot_id=snapshot.id,
            ),
            **snapshot.dict(),
        )
