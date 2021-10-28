from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from aiopg.sa.result import RowProxy
from models_library.basic_types import SHA1Str
from models_library.projects import ProjectID
from models_library.projects_nodes import Node
from pydantic import BaseModel, PositiveInt, StrictBool, StrictFloat, StrictInt
from pydantic.networks import HttpUrl

BuiltinTypes = Union[StrictBool, StrictInt, StrictFloat, str]

# alias for readability
# SEE https://pydantic-docs.helpmanual.io/usage/models/#orm-mode-aka-arbitrary-class-instances

BranchProxy = RowProxy
CommitProxy = RowProxy
RepoProxy = RowProxy
TagProxy = RowProxy
CommitLog = Tuple[CommitProxy, List[TagProxy]]

ProjectProxy = RowProxy
ProjectDict = Dict

HEAD = f"{__file__}/ref/HEAD"

CommitID = int
BranchID = int
RefID = Union[CommitID, str]

CheckpointID = PositiveInt


class Checkpoint(BaseModel):
    id: CheckpointID
    checksum: SHA1Str
    created_at: datetime
    tags: Tuple[str, ...]
    # TODO: so front-end can proper break tree branches
    # branches: Tuple[str, ...] = tuple()

    message: Optional[str] = None
    parents_ids: Tuple[PositiveInt, ...] = None  # type: ignore

    @classmethod
    def from_commit_log(cls, commit: RowProxy, tags: List[RowProxy]) -> "Checkpoint":
        return cls(
            id=commit.id,
            checksum=commit.snapshot_checksum,
            tags=tuple(tag.name for tag in tags),
            message=commit.message,
            parents_ids=(commit.parent_commit_id,) if commit.parent_commit_id else None,
            created_at=commit.created,
        )


class WorkbenchView(BaseModel):
    """A view (i.e. read-only and visual) of the project's workbench"""

    class Config:
        orm_mode = True

    # FIXME: Tmp replacing UUIDS by str due to a problem serializing to json UUID keys
    # in the response https://github.com/samuelcolvin/pydantic/issues/2096#issuecomment-814860206
    workbench: Dict[str, Node]
    ui: Dict[str, Any] = {}


# API models ---------------


class RepoApiModel(BaseModel):
    project_uuid: ProjectID
    url: HttpUrl


class CheckpointApiModel(Checkpoint):
    url: HttpUrl


class CheckpointNew(BaseModel):
    tag: str
    message: Optional[str] = None
    # new_branch: Optional[str] = None


class CheckpointAnnotations(BaseModel):
    tag: Optional[str] = None
    message: Optional[str] = None


class WorkbenchViewApiModel(WorkbenchView):
    url: HttpUrl
    checkpoint_url: HttpUrl
