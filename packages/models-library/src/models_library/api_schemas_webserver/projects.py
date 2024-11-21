""" rest API schema models for projects


SEE rationale in https://fastapi.tiangolo.com/tutorial/extra-models/#multiple-models

"""

from datetime import datetime
from typing import Annotated, Any, Literal, TypeAlias

from models_library.folders import FolderID
from models_library.workspaces import WorkspaceID
from pydantic import BeforeValidator, ConfigDict, Field, HttpUrl, field_validator

from ..api_schemas_long_running_tasks.tasks import TaskGet
from ..basic_types import LongTruncatedStr, ShortTruncatedStr
from ..emails import LowerCaseEmailStr
from ..folders import FolderID
from ..projects import ClassifierID, DateTimeStr, NodesDict, ProjectID
from ..projects_access import AccessRights, GroupIDStr
from ..projects_state import ProjectState
from ..projects_ui import StudyUI
from ..utils.common_validators import (
    empty_str_to_none_pre_validator,
    none_to_empty_str_pre_validator,
    null_or_none_str_to_none_validator,
)
from ..workspaces import WorkspaceID
from ._base import EmptyModel, InputSchema, OutputSchema
from .permalinks import ProjectPermalink


class ProjectCreateNew(InputSchema):
    uuid: ProjectID | None = None  # NOTE: suggested uuid! but could be different!
    name: str
    description: str | None = None
    thumbnail: HttpUrl | None = None
    workbench: NodesDict
    access_rights: dict[GroupIDStr, AccessRights]
    tags: list[int] = Field(default_factory=list)
    classifiers: list[ClassifierID] = Field(default_factory=list)
    ui: StudyUI | None = None
    workspace_id: WorkspaceID | None = None
    folder_id: FolderID | None = None

    _empty_is_none = field_validator("uuid", "thumbnail", "description", mode="before")(
        empty_str_to_none_pre_validator
    )

    _null_or_none_to_none = field_validator("workspace_id", "folder_id", mode="before")(
        null_or_none_str_to_none_validator
    )


# NOTE: based on OVERRIDABLE_DOCUMENT_KEYS
class ProjectCopyOverride(InputSchema):
    name: str
    description: str | None = None
    thumbnail: HttpUrl | None = None
    prj_owner: LowerCaseEmailStr

    _empty_is_none = field_validator("thumbnail", mode="before")(
        empty_str_to_none_pre_validator
    )


class ProjectGet(OutputSchema):
    uuid: ProjectID
    name: str
    description: str
    thumbnail: HttpUrl | Literal[""]
    creation_date: DateTimeStr
    last_change_date: DateTimeStr
    workbench: NodesDict
    prj_owner: LowerCaseEmailStr
    access_rights: dict[GroupIDStr, AccessRights]
    tags: list[int]
    classifiers: list[ClassifierID] = Field(
        default_factory=list, json_schema_extra={"default": []}
    )
    state: ProjectState | None = None
    ui: EmptyModel | StudyUI | None = None
    quality: dict[str, Any] = Field(
        default_factory=dict, json_schema_extra={"default": {}}
    )
    dev: dict | None
    permalink: ProjectPermalink | None = None
    workspace_id: WorkspaceID | None
    folder_id: FolderID | None
    trashed_at: datetime | None

    _empty_description = field_validator("description", mode="before")(
        none_to_empty_str_pre_validator
    )

    model_config = ConfigDict(frozen=False)


TaskProjectGet: TypeAlias = TaskGet


class ProjectListItem(ProjectGet):
    ...


class ProjectReplace(InputSchema):
    uuid: ProjectID
    name: ShortTruncatedStr
    description: LongTruncatedStr
    thumbnail: Annotated[
        HttpUrl | None, BeforeValidator(empty_str_to_none_pre_validator)
    ] = Field(default=None)
    creation_date: DateTimeStr
    last_change_date: DateTimeStr
    workbench: NodesDict
    access_rights: dict[GroupIDStr, AccessRights]
    tags: list[int] | None = Field(
        default_factory=list, json_schema_extra={"default": []}
    )
    classifiers: list[ClassifierID] | None = Field(
        default_factory=list, json_schema_extra={"default": []}
    )
    ui: StudyUI | None = None
    quality: dict[str, Any] = Field(
        default_factory=dict, json_schema_extra={"default": {}}
    )


class ProjectPatch(InputSchema):
    name: ShortTruncatedStr | None = Field(default=None)
    description: LongTruncatedStr | None = Field(default=None)
    thumbnail: Annotated[
        HttpUrl | None, BeforeValidator(empty_str_to_none_pre_validator)
    ] = Field(default=None)
    access_rights: dict[GroupIDStr, AccessRights] | None = Field(default=None)
    classifiers: list[ClassifierID] | None = Field(default=None)
    dev: dict | None = Field(default=None)
    ui: StudyUI | None = Field(default=None)
    quality: dict[str, Any] | None = Field(default=None)


__all__: tuple[str, ...] = (
    "EmptyModel",
    "ProjectCopyOverride",
    "ProjectCreateNew",
    "ProjectGet",
    "ProjectListItem",
    "ProjectReplace",
    "TaskProjectGet",
)
