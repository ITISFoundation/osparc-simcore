from enum import StrEnum
from typing import Final, Literal

from models_library.api_schemas_async_jobs.async_jobs import AsyncJobGet
from models_library.api_schemas_webserver.storage import PathToExport
from models_library.celery import (
    TaskExecutionMetadata,
)
from models_library.products import ProductName
from models_library.users import UserID

from ...task_manager import TaskManager

EXPORT_DATA_TASK_NAME: Final[str] = "export_data"
EXPORT_DATA_AS_DOWNLOAD_LINK_TASK_NAME: Final[str] = "export_data_as_download_link"


class TaskQueueNames(StrEnum):
    CPU_BOUND = "cpu_bound"


async def submit_export_data(
    task_manager: TaskManager,
    owner: str,
    user_id: UserID,
    product_name: ProductName,
    paths_to_export: list[PathToExport],
    export_as: Literal["path", "download_link"],
) -> AsyncJobGet:
    match export_as:
        case "path":
            task_name = EXPORT_DATA_TASK_NAME
        case "download_link":
            task_name = EXPORT_DATA_AS_DOWNLOAD_LINK_TASK_NAME
        case _:
            msg = f"Invalid export_as value: {export_as}"
            raise ValueError(msg)
    task_id = await task_manager.submit_task(
        TaskExecutionMetadata(
            name=task_name,
            ephemeral=False,
            queue=TaskQueueNames.CPU_BOUND,
        ),
        owner=owner,
        user_id=user_id,
        product_name=product_name,
        paths_to_export=paths_to_export,
    )
    return AsyncJobGet(job_id=task_id, job_name=task_name)
