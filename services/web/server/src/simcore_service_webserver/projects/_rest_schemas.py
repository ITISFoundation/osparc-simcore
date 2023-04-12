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
from pydantic import Field
from servicelib.aiohttp.long_running_tasks.server import TaskGet

from ..rest_schemas_base import InputSchema, OutputSchema

# TODO: review creation  policies with OM (e.g. NO uuid!)


class ProjectCreate(InputSchema):
    uuid: ProjectID
    name: str
    description: str
    thumbnail: HttpUrlWithCustomMinLength | None
    workbench: NodesDict
    prj_owner: LowerCaseEmailStr
    access_rights: dict[GroupIDStr, AccessRights]
    tags: list[int] | None = []
    classifiers: list[ClassifierID] | None = Field(default_factory=list)
    state: ProjectState | None = None
    ui: StudyUI | None = None
    quality: dict[str, Any] = Field(default_factory=dict)
    dev: dict | None = None


# NOTE: based on OVERRIDABLE_DOCUMENT_KEYS
class ProjectCopyOverride(InputSchema):
    name: str
    description: str
    thumbnail: HttpUrlWithCustomMinLength | None
    prj_owner: LowerCaseEmailStr
    access_rights: dict[GroupIDStr, AccessRights]


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
    tags: list[int] | None = []
    classifiers: list[ClassifierID] | None = Field(default_factory=list)
    state: ProjectState | None = None
    ui: StudyUI | None = None
    quality: dict[str, Any] = Field(default_factory=dict)
    dev: dict | None = None


# TODO: TaskGet[Envelope[TaskProjectGet]] i.e. should include future?
TaskProjectGet: TypeAlias = TaskGet


# TODO: review with OM. with option to get it lighter??
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
    dev: dict | None = None


class ProjectUpdate(InputSchema):
    name: str = Field(default=None)
    description: str = Field(default=None)
    thumbnail: HttpUrlWithCustomMinLength | None = None
    workbench: NodesDict = Field(default=None)
    access_rights: dict[GroupIDStr, AccessRights] = Field(default=None)
    tags: list[int] | None = []
    classifiers: list[ClassifierID] | None = Field(default_factory=list)
    ui: StudyUI | None = None
    quality: dict[str, Any] = Field(default_factory=dict)
    dev: dict | None = None


__all__: tuple[str, ...] = (
    "ProjectCreate",
    "ProjectCopyOverride",
    "ProjectGet",
    "ProjectListItem",
    "ProjectReplace",
    "ProjectUpdate",
    "TaskProjectGet",
)
