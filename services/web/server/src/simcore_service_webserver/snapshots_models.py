from datetime import datetime
from typing import Optional, Union
from uuid import UUID

from aiohttp import web
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
    id: PositiveInt = Field(None, description="Unique snapshot identifier")
    label: Optional[str] = Field(
        None, description="Unique human readable display name", alias="name"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of the time snapshot was taken from parent. Notice that parent might change with time",
    )

    parent_uuid: UUID = Field(..., description="Parent's project uuid")
    project_uuid: UUID = Field(..., description="Current project's uuid")

    class Config:
        orm_mode = True


## API models ----------


class ParameterApiModel(Parameter):
    url: AnyUrl
    # url_output: AnyUrl


class SnapshotItem(Snapshot):
    """API model for an array item of snapshots"""

    url: AnyUrl
    url_parent: AnyUrl
    url_project: AnyUrl
    url_parameters: Optional[AnyUrl] = None

    @classmethod
    def from_snapshot(cls, snapshot: Snapshot, app: web.Application) -> "SnapshotItem":
        def url_for(router_name: str, **params):
            return app.router[router_name].url_for(
                **{k: str(v) for k, v in params.items()}
            )

        return cls(
            url=url_for(
                "get_project_snapshot_handler",
                project_id=snapshot.project_uuid,
                snapshot_id=snapshot.id,
            ),
            url_parent=url_for("get_project", project_id=snapshot.parent_uuid),
            url_project=url_for("get_project", project_id=snapshot.project_uuid),
            url_parameters=url_for(
                "get_project_snapshot_parameters_handler",
                project_id=snapshot.parent_uuid,
                snapshot_id=snapshot.id,
            ),
            **snapshot.dict(),
        )
