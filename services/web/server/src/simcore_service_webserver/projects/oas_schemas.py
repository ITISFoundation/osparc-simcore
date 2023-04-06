""" rest API schema models for projects


SEE rationale in https://fastapi.tiangolo.com/tutorial/extra-models/#multiple-models

"""

from models_library.base_oas_schemas import BaseInputSchemaModel, BaseOutputSchemaModel
from models_library.projects import Project
from models_library.utils.pydantic_models_factory import copy_model
from pydantic import BaseModel
from servicelib.aiohttp.long_running_tasks.server import TaskGet

# TODO: review creation  policies with OM (e.g. NO uuid!)
ProjectCreate = copy_model(
    Project,
    name="ProjectCreate",
    include={
        "uuid",  # TODO: review with OM
        "name",
        "description",
        "creation_date",
        "last_change_date",
        "workbench",
        "prj_owner",
        "access_rights",  # TODO: review with OM
    },
    __base__=BaseOutputSchemaModel,
)


ProjectGet: type[BaseModel] = copy_model(
    Project,
    name="ProjectGet",
    include={
        "uuid",
        "name",
        "description",
        "thumbnail",
        "creation_date",
        "last_change_date",
        "workbench",
        "prj_owner",
        "access_rights",
        "tags",
        "classifiers",
        "state",
        "ui",
        "quality",
        "dev",
    },
    __base__=BaseOutputSchemaModel,
)


# TODO: TaskGet[Envelope[TaskProjectGet]] i.e. should include future?
TaskProjectGet = TaskGet


# TODO: review with OM. with option to get it lighter??
ProjectListItem = ProjectGet


ProjectReplace = copy_model(
    Project,
    name="ProjectReplace",
    include={
        "name",
        "description",
        "thumbnail",
        "creation_date",
        "last_change_date",
        "workbench",
        "access_rights",
        "tags",
        "classifiers",
        "ui",
        "quality",
        "dev",
    },
    __base__=BaseInputSchemaModel,
)


ProjectUpdate = copy_model(
    Project,
    name="ProjectUpdate",
    include={
        "name",
        "description",
        "thumbnail",
        "creation_date",
        "last_change_date",
        "workbench",
        "access_rights",
        "tags",
        "classifiers",
        "ui",
        "quality",
        "dev",
    },
    as_update_model=True,
    __base__=BaseInputSchemaModel,
)


__all__: tuple[str, ...] = (
    "ProjectCreate",
    "ProjectGet",
    "ProjectListItem",
    "ProjectReplace",
    "ProjectUpdate",
    "TaskProjectGet",
)
