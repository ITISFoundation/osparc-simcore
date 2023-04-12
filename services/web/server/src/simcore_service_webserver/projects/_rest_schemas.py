""" rest API schema models for projects


SEE rationale in https://fastapi.tiangolo.com/tutorial/extra-models/#multiple-models

"""

import uuid
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
# ProjectCreate = copy_model(
#     Project,
#     name="ProjectCreate",
#     include={
#         "uuid",  # TODO: review with OM
#         "name",
#         "description",
#         "creation_date",
#         "last_change_date",
#         "workbench",
#         "prj_owner",
#         "access_rights",  # TODO: review with OM
#     },
#     __base__=BaseOutputSchemaModel,
# )


class ProjectCreate(OutputSchema):
    uuid: ProjectID
    name: str
    description: str
    creation_date: DateTimeStr
    last_change_date: DateTimeStr
    workbench: NodesDict
    prj_owner: LowerCaseEmailStr
    access_rights: dict[GroupIDStr, AccessRights]


# ProjectGet: type[BaseModel] = copy_model(
#     Project,
#     name="ProjectGet",
#     include={
#         "uuid",
#         "name",
#         "description",
#         "thumbnail",
#         "creation_date",
#         "last_change_date",
#         "workbench",
#         "prj_owner",
#         "access_rights",
#         "tags",
#         "classifiers",
#         "state",
#         "ui",
#         "quality",
#         "dev",
#     },
#     __base__=BaseOutputSchemaModel,
# )


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
    classifiers: list[ClassifierID] | None = Field(
        default_factory=list,
    )
    state: ProjectState | None = None
    ui: StudyUI | None = None
    quality: dict[str, Any] = Field(
        default_factory=dict,
    )
    dev: dict | None = None


# TODO: TaskGet[Envelope[TaskProjectGet]] i.e. should include future?
TaskProjectGet: TypeAlias = TaskGet


# TODO: review with OM. with option to get it lighter??
class ProjectListItem(ProjectGet):
    ...


# ProjectReplace = copy_model(
#     Project,
#     name="ProjectReplace",
#     include={
#         "name",
#         "description",
#         "thumbnail",
#         "creation_date",
#         "last_change_date",
#         "workbench",
#         "access_rights",
#         "tags",
#         "classifiers",
#         "ui",
#         "quality",
#         "dev",
#     },
#     __base__=BaseInputSchemaModel,
# )


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


# ProjectUpdate = copy_model(
#     Project,
#     name="ProjectUpdate",
#     include={
#         "name",
#         "description",
#         "thumbnail",
#         "creation_date",
#         "last_change_date",
#         "workbench",
#         "access_rights",
#         "tags",
#         "classifiers",
#         "ui",
#         "quality",
#         "dev",
#     },
#     as_update_model=True,
#     __base__=BaseInputSchemaModel,
# )


class ProjectUpdate(InputSchema):
    name: str = None  # type: ignore
    description: str = None  # type: ignore
    thumbnail: HttpUrlWithCustomMinLength | None = None
    workbench: NodesDict = None  # type: ignore
    access_rights: dict[GroupIDStr, AccessRights] = None  # type: ignore
    tags: list[int] | None = []
    classifiers: list[ClassifierID] | None = Field(
        default_factory=list,
    )
    ui: StudyUI | None = None
    quality: dict[str, Any] = Field(
        default_factory=dict,
    )
    dev: dict | None = None


__all__: tuple[str, ...] = (
    "ProjectCreate",
    "ProjectGet",
    "ProjectListItem",
    "ProjectReplace",
    "ProjectUpdate",
    "TaskProjectGet",
)
