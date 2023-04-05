""" projects's rest API schema models

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


class ProjectListItem(BaseOutputSchemaModel):
    pass


class ProjectReplace(BaseInputSchemaModel):
    pass


class ProjectUpdate(BaseInputSchemaModel):
    pass


assert TaskGet  # nosec


__all__: tuple[str, ...] = "TaskGet"
