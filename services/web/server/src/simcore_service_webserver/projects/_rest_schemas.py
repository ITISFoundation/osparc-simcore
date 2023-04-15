""" rest API schema models for projects


SEE rationale in https://fastapi.tiangolo.com/tutorial/extra-models/#multiple-models

"""

from typing import Any, TypeAlias

from models_library.emails import LowerCaseEmailStr
from models_library.projects import ClassifierID, DateTimeStr, NodesDict, ProjectID
from models_library.projects_access import AccessRights, GroupIDStr
from models_library.projects_nodes import HttpUrlWithCustomMinLength
from models_library.projects_state import ProjectState
from models_library.projects_ui import StudyUI
from models_library.utils.common_validators import empty_str_to_none
from pydantic import BaseModel, Extra, Field, validator
from servicelib.aiohttp.long_running_tasks.server import TaskGet

from ..rest_schemas_base import InputSchema, OutputSchema


class EmptyModel(BaseModel):
    # Used to represent body={}
    class Config:
        extra = Extra.forbid


class ProjectCreateNew(InputSchema):
    name: str
    description: str
    thumbnail: HttpUrlWithCustomMinLength | None
    workbench: NodesDict
    access_rights: dict[GroupIDStr, AccessRights]
    tags: list[int] = Field(default_factory=list)
    classifiers: list[ClassifierID] = Field(default_factory=list)
    ui: StudyUI | None = None

    _empty_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
        empty_str_to_none
    )


# NOTE: based on OVERRIDABLE_DOCUMENT_KEYS
class ProjectCopyOverride(InputSchema):
    name: str
    description: str
    thumbnail: HttpUrlWithCustomMinLength | None
    prj_owner: LowerCaseEmailStr

    _empty_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
        empty_str_to_none
    )


#
# This is the schema the client will read
# Parses some domain data and has to fit
#
class ProjectGet(OutputSchema):
    uuid: ProjectID
    name: str
    description: str
    thumbnail: HttpUrlWithCustomMinLength | None
    creation_date: DateTimeStr
    last_change_date: DateTimeStr
    workbench: NodesDict
    prj_owner: LowerCaseEmailStr
    access_rights: dict[GroupIDStr, AccessRights]
    tags: list[int]
    classifiers: list[ClassifierID]
    state: ProjectState | None
    ui: StudyUI | None
    quality: dict[str, Any]
    dev: dict | None

    @validator("description", pre=True)
    @classmethod
    def none_is_empty_str(cls, v):
        # NOTE: in db the description can be null
        return v or ""


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


NOT_REQUIRED = Field(default=None)


class ProjectUpdate(InputSchema):
    name: str = NOT_REQUIRED
    description: str = NOT_REQUIRED
    name: str = Field(default=None)
    description: str = Field(default=None)
    thumbnail: HttpUrlWithCustomMinLength | None = None
    workbench: NodesDict = Field(default=None)
    access_rights: dict[GroupIDStr, AccessRights] = Field(default=None)
    tags: list[int] | None = []
    classifiers: list[ClassifierID] | None = Field(default_factory=list)
    ui: StudyUI | None = None
    quality: dict[str, Any] = Field(default_factory=dict)

    _empty_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
        empty_str_to_none
    )


__all__: tuple[str, ...] = (
    "ProjectCreateNew",
    "ProjectCopyOverride",
    "ProjectGet",
    "ProjectListItem",
    "ProjectReplace",
    "ProjectUpdate",
    "TaskProjectGet",
)
