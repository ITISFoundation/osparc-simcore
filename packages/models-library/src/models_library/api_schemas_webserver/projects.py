""" rest API schema models for projects


SEE rationale in https://fastapi.tiangolo.com/tutorial/extra-models/#multiple-models

"""

from typing import Any, Literal, TypeAlias

from models_library.folders import FolderID
from models_library.workspaces import WorkspaceID
from pydantic import Field, HttpUrl, field_validator

from ..api_schemas_long_running_tasks.tasks import TaskGet
from ..basic_types import LongTruncatedStr, ShortTruncatedStr
from ..emails import LowerCaseEmailStr
from ..projects import ClassifierID, DateTimeStr, NodesDict, ProjectID
from ..projects_access import AccessRights, GroupIDStr
from ..projects_state import ProjectState
from ..projects_ui import StudyUI
from ..utils.common_validators import (
    empty_str_to_none_pre_validator,
    none_to_empty_str_pre_validator,
    null_or_none_str_to_none_validator,
)
from ..utils.pydantic_tools_extension import FieldNotRequired
from ._base import EmptyModel, InputSchema, OutputSchema
from .permalinks import ProjectPermalink


class ProjectCreateNew(InputSchema):
    uuid: ProjectID | None = None  # NOTE: suggested uuid! but could be different!
    name: str
    description: str | None
    thumbnail: HttpUrl | None
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
    description: str | None
    thumbnail: HttpUrl | None
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
    classifiers: list[ClassifierID] = []
    state: ProjectState | None = None
    ui: EmptyModel | StudyUI | None = None
    quality: dict[str, Any] = {}
    dev: dict | None = None
    permalink: ProjectPermalink = FieldNotRequired()
    workspace_id: WorkspaceID | None
    folder_id: FolderID | None

    _empty_description = field_validator("description", mode="before")(
        none_to_empty_str_pre_validator
    )


TaskProjectGet: TypeAlias = TaskGet


class ProjectListItem(ProjectGet):
    ...


class ProjectReplace(InputSchema):
    uuid: ProjectID
    name: ShortTruncatedStr
    description: LongTruncatedStr
    thumbnail: HttpUrl | None
    creation_date: DateTimeStr
    last_change_date: DateTimeStr
    workbench: NodesDict
    access_rights: dict[GroupIDStr, AccessRights]
    tags: list[int] | None = []
    classifiers: list[ClassifierID] | None = Field(
        default_factory=list,
    )
    ui: StudyUI | None = None
    quality: dict[str, Any] = Field(
        default_factory=dict,
    )

    _empty_is_none = field_validator("thumbnail", mode="before")(
        empty_str_to_none_pre_validator
    )


class ProjectUpdate(InputSchema):
    name: ShortTruncatedStr = FieldNotRequired()
    description: LongTruncatedStr = FieldNotRequired()
    thumbnail: HttpUrl = FieldNotRequired()
    workbench: NodesDict = FieldNotRequired()
    access_rights: dict[GroupIDStr, AccessRights] = FieldNotRequired()
    tags: list[int] = FieldNotRequired()
    classifiers: list[ClassifierID] = FieldNotRequired()
    ui: StudyUI | None = None
    quality: dict[str, Any] = FieldNotRequired()


class ProjectPatch(InputSchema):
    name: ShortTruncatedStr = FieldNotRequired()
    description: LongTruncatedStr = FieldNotRequired()
    thumbnail: HttpUrl = FieldNotRequired()
    access_rights: dict[GroupIDStr, AccessRights] = FieldNotRequired()
    classifiers: list[ClassifierID] = FieldNotRequired()
    dev: dict | None = FieldNotRequired()
    ui: StudyUI | None = FieldNotRequired()
    quality: dict[str, Any] = FieldNotRequired()


__all__: tuple[str, ...] = (
    "EmptyModel",
    "ProjectCopyOverride",
    "ProjectCreateNew",
    "ProjectGet",
    "ProjectListItem",
    "ProjectReplace",
    "ProjectUpdate",
    "TaskProjectGet",
)
