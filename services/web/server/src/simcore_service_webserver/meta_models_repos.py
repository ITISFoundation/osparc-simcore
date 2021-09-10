from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from aiopg.sa.result import RowProxy
from models_library.basic_types import SHA1Str
from models_library.projects_nodes import Node
from pydantic import BaseModel, PositiveInt, StrictBool, StrictFloat, StrictInt
from pydantic.networks import HttpUrl

BuiltinTypes = Union[StrictBool, StrictInt, StrictFloat, str]

# alias for readability
# SEE https://pydantic-docs.helpmanual.io/usage/models/#orm-mode-aka-arbitrary-class-instances

CommitProxy = RowProxy
TagProxy = RowProxy
CommitLog = Tuple[CommitProxy, List[TagProxy]]

ProjectProxy = RowProxy
ProjectDict = Dict


class Checkpoint(BaseModel):
    id: PositiveInt
    checksum: SHA1Str
    created_at: datetime
    tags: Tuple[str, ...]

    message: Optional[str] = None
    parents_ids: Tuple[PositiveInt, ...] = None  # type: ignore

    @classmethod
    def from_commit_log(cls, commit: RowProxy, tags: List[RowProxy]) -> "Checkpoint":
        return cls(
            id=commit.id,
            checksum=commit.snapshot_checksum,
            tags=tuple(tag.name for tag in tags),
            message=tags[0].message if tags else commit.message,
            parents_ids=(commit.parent_commit_id,) if commit.parent_commit_id else None,
            created_at=commit.created,
        )


class WorkbenchView(BaseModel):
    """A view (i.e. read-only and visual) of the project's workbench"""

    workbench: Dict[UUID, Node] = {}
    ui: Dict[UUID, Any] = {}


# API models ---------------


class RepoApiModel(BaseModel):
    project_uuid: UUID
    url: HttpUrl


class CheckpointApiModel(Checkpoint):
    url: HttpUrl


class CheckpointNew(BaseModel):
    tag: str
    message: Optional[str] = None
    new_branch: Optional[str] = None


class CheckpointAnnotations(BaseModel):
    tag: Optional[str] = None
    message: Optional[str] = None


class WorkbenchViewApiModel(WorkbenchView):
    url: HttpUrl
