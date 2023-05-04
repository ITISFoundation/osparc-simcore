""" rest API schema models for projects


SEE rationale in https://fastapi.tiangolo.com/tutorial/extra-models/#multiple-models

"""

from typing import Any, Literal, TypeAlias

from models_library.emails import LowerCaseEmailStr
from models_library.projects import ClassifierID, DateTimeStr, NodesDict, ProjectID
from models_library.projects_access import AccessRights, GroupIDStr
from models_library.projects_nodes import HttpUrlWithCustomMinLength
from models_library.projects_state import ProjectState
from models_library.projects_ui import StudyUI
from models_library.utils.common_validators import empty_str_to_none, none_to_empty_str
from pydantic import BaseModel, Extra, Field, validator
from servicelib.aiohttp.long_running_tasks.server import TaskGet

from ..rest_schemas_base import InputSchema, OutputSchema
from ._permalink import ProjectPermalink

NOT_REQUIRED = Field(default=None)


class EmptyModel(BaseModel):
    # Used to represent body={}
    class Config:
        extra = Extra.forbid


class ProjectCreateNew(InputSchema):
    uuid: ProjectID | None = None  # NOTE: suggested uuid! but could be different!
    name: str
    description: str | None
    thumbnail: HttpUrlWithCustomMinLength | None
    workbench: NodesDict
    access_rights: dict[GroupIDStr, AccessRights]
    tags: list[int] = Field(default_factory=list)
    classifiers: list[ClassifierID] = Field(default_factory=list)
    ui: StudyUI | None = None

    _empty_is_none = validator(
        "uuid", "thumbnail", "description", allow_reuse=True, pre=True
    )(empty_str_to_none)


# NOTE: based on OVERRIDABLE_DOCUMENT_KEYS
class ProjectCopyOverride(InputSchema):
    name: str
    description: str | None
    thumbnail: HttpUrlWithCustomMinLength | None
    prj_owner: LowerCaseEmailStr

    _empty_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
        empty_str_to_none
    )


class ProjectGet(OutputSchema):
    uuid: ProjectID
    name: str
    description: str
    thumbnail: HttpUrlWithCustomMinLength | Literal[""]
    creation_date: DateTimeStr
    last_change_date: DateTimeStr
    workbench: NodesDict
    prj_owner: LowerCaseEmailStr
    access_rights: dict[GroupIDStr, AccessRights]
    tags: list[int]
    classifiers: list[ClassifierID] = []
    state: ProjectState | None
    ui: EmptyModel | StudyUI | None
    quality: dict[str, Any] = {}
    dev: dict | None
    permalink: ProjectPermalink | None = None  # Optional and nullable

    _empty_description = validator("description", allow_reuse=True, pre=True)(
        none_to_empty_str
    )


TaskProjectGet: TypeAlias = TaskGet


class ProjectListItem(ProjectGet):
    ...


class ProjectReplace(InputSchema):
    uuid: ProjectID
    name: str
    description: str
    thumbnail: HttpUrlWithCustomMinLength | None
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

    _empty_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
        empty_str_to_none
    )


class ProjectUpdate(InputSchema):
    name: str = NOT_REQUIRED
    description: str = NOT_REQUIRED
    name: str = NOT_REQUIRED
    description: str = NOT_REQUIRED
    thumbnail: HttpUrlWithCustomMinLength = NOT_REQUIRED
    workbench: NodesDict = NOT_REQUIRED
    access_rights: dict[GroupIDStr, AccessRights] = NOT_REQUIRED
    tags: list[int] = NOT_REQUIRED
    classifiers: list[ClassifierID] = NOT_REQUIRED
    ui: StudyUI | None = None
    quality: dict[str, Any] = NOT_REQUIRED


__all__: tuple[str, ...] = (
    "ProjectCreateNew",
    "ProjectCopyOverride",
    "ProjectGet",
    "ProjectListItem",
    "ProjectReplace",
    "ProjectUpdate",
    "TaskProjectGet",
)
