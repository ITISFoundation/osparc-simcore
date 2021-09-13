from datetime import datetime
from typing import Any, Callable, Optional, Union
from uuid import UUID, uuid3

from pydantic import (
    AnyUrl,
    BaseModel,
    Field,
    PositiveInt,
    StrictBool,
    StrictFloat,
    StrictInt,
)
from pydantic.main import BaseConfig
from yarl import URL

BuiltinTypes = Union[StrictBool, StrictInt, StrictFloat, str]


## Domain models --------


class BaseSnapshot(BaseModel):
    class Config(BaseConfig):
        orm_mode = True
        # parses with alias and/or field name -> can parse from API or db data models
        allow_population_by_field_name = True

    @classmethod
    def as_field(cls, name) -> Any:
        return cls.__fields__[name].field_info


class Snapshot(BaseSnapshot):
    id: PositiveInt = Field(None, description="Unique snapshot identifier")
    label: Optional[str] = Field(
        None, description="Unique human readable display name", alias="name"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of the time snapshot was taken from parent."
        "Notice that parent might change with time",
    )

    parent_uuid: UUID = Field(..., description="Parent's project uuid")
    project_uuid: UUID = Field(..., description="Current project's uuid")

    # TODO: can project_uuid be cached_property??
    # SEE BaseCustomSettings.Config and do not forget keep_untouched option!

    @staticmethod
    def compose_project_uuid(
        parent_uuid: Union[UUID, str], snapshot_timestamp: datetime
    ) -> UUID:
        if isinstance(parent_uuid, str):
            parent_uuid = UUID(parent_uuid)
        return uuid3(parent_uuid, f"snapshot.{snapshot_timestamp}")


## API models ----------


class SnapshotPatch(BaseSnapshot):
    label: Optional[str] = Snapshot.as_field("label")


class SnapshotItem(Snapshot):
    """API model for an array item of snapshots"""

    url: AnyUrl
    url_parent: AnyUrl
    url_project: AnyUrl
    url_parameters: Optional[AnyUrl] = None

    @classmethod
    def from_snapshot(
        cls, snapshot: Snapshot, url_for: Callable[..., URL]
    ) -> "SnapshotItem":
        # TODO: is this the right place?  requires pre-defined routes
        # how to guarantee routes names
        return cls(
            url=url_for(
                "get_project_snapshot_handler",
                project_id=snapshot.parent_uuid,
                snapshot_id=snapshot.id,
            ),
            url_parent=url_for("get_project", project_id=snapshot.parent_uuid),
            url_project=url_for("get_project", project_id=snapshot.project_uuid),
            url_parameters=url_for(
                "get_snapshot_parameters_handler",
                project_id=snapshot.parent_uuid,
                snapshot_id=snapshot.id,
            ),
            **snapshot.dict(by_alias=True),
        )
