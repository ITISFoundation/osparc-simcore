from datetime import datetime
from typing import Any, TypeAlias, Union

from aiopg.sa.result import RowProxy
from models_library.basic_types import SHA1Str
from models_library.projects import ProjectID
from models_library.projects_nodes import Node
from pydantic import BaseModel, Field, PositiveInt, StrictBool, StrictFloat, StrictInt
from pydantic.networks import HttpUrl

BuiltinTypes: TypeAlias = Union[StrictBool, StrictInt, StrictFloat, str]

# alias for readability
# SEE https://pydantic-docs.helpmanual.io/usage/models/#orm-mode-aka-arbitrary-class-instances

BranchProxy: TypeAlias = RowProxy
CommitProxy: TypeAlias = RowProxy
RepoProxy: TypeAlias = RowProxy
TagProxy: TypeAlias = RowProxy
CommitLog: TypeAlias = tuple[CommitProxy, list[TagProxy]]


HEAD = f"{__file__}/ref/HEAD"

CommitID: TypeAlias = int
BranchID: TypeAlias = int
RefID: TypeAlias = Union[CommitID, str]

CheckpointID: TypeAlias = PositiveInt


class Checkpoint(BaseModel):
    id: CheckpointID
    checksum: SHA1Str
    created_at: datetime
    tags: tuple[str, ...]
    message: str | None = None
    parents_ids: tuple[PositiveInt, ...] = Field(default=None)

    @classmethod
    def from_commit_log(cls, commit: RowProxy, tags: list[RowProxy]) -> "Checkpoint":
        return cls(
            id=commit.id,
            checksum=commit.snapshot_checksum,
            tags=tuple(tag.name for tag in tags),
            message=commit.message,
            parents_ids=(commit.parent_commit_id,) if commit.parent_commit_id else None,  # type: ignore[arg-type]
            created_at=commit.created,
        )


class WorkbenchView(BaseModel):
    """A view (i.e. read-only and visual) of the project's workbench"""

    class Config:
        orm_mode = True

    # NOTE: Tmp replacing UUIDS by str due to a problem serializing to json UUID keys
    # in the response https://github.com/samuelcolvin/pydantic/issues/2096#issuecomment-814860206
    workbench: dict[str, Node]
    ui: dict[str, Any] = {}


# API models ---------------


class RepoApiModel(BaseModel):
    project_uuid: ProjectID
    url: HttpUrl


class CheckpointApiModel(Checkpoint):
    url: HttpUrl


class CheckpointNew(BaseModel):
    tag: str
    message: str | None = None
    # new_branch: Optional[str] = None


class CheckpointAnnotations(BaseModel):
    tag: str | None = None
    message: str | None = None


class WorkbenchViewApiModel(WorkbenchView):
    url: HttpUrl
    checkpoint_url: HttpUrl


__all__: tuple[str, ...] = (
    "BranchID",
    "BranchProxy",
    "CheckpointID",
    "CommitID",
    "CommitLog",
    "CommitProxy",
    "HEAD",
    "RefID",
    "RepoProxy",
    "TagProxy",
)
