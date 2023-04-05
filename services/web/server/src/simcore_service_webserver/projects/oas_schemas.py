""" rest API schema models for projects


SEE rationale in https://fastapi.tiangolo.com/tutorial/extra-models/#multiple-models

"""

from models_library.base_oas_schemas import BaseInputSchemaModel, BaseOutputSchemaModel
from servicelib.aiohttp.long_running_tasks.server import TaskGet

#
# API Schema Models
#


class ProjectCreate(BaseInputSchemaModel):
    pass


class ProjectGet(BaseOutputSchemaModel):
    pass


# TODO: TaskGet[Envelope[TaskProjectGet]] i.e. should include future?
TaskProjectGet = TaskGet


class ProjectListItem(BaseOutputSchemaModel):
    pass


class ProjectReplace(BaseInputSchemaModel):
    pass


class ProjectUpdate(BaseInputSchemaModel):
    pass


__all__: tuple[str, ...] = (
    "ProjectCreate",
    "ProjectGet",
    "ProjectListItem",
    "ProjectReplace",
    "ProjectUpdate",
    "TaskProjectGet",
)
