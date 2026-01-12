from typing import Final, Literal

from models_library.api_schemas_async_jobs.async_jobs import AsyncJobGet
from models_library.api_schemas_webserver.storage import PathToExport
from models_library.products import ProductName
from models_library.users import UserID

from ....celery.models import (
    ExecutionMetadata,
    OwnerMetadata,
    TasksQueue,
)
from ....celery.task_manager import TaskManager

EXPORT_DATA_TASK_NAME: Final[str] = "export_data"
EXPORT_DATA_AS_DOWNLOAD_LINK_TASK_NAME: Final[str] = "export_data_as_download_link"


async def submit_export_data_task(  # noqa: PLR0913
    task_manager: TaskManager,
    owner_metadata: OwnerMetadata,
    user_id: UserID,
    product_name: ProductName,
    paths_to_export: list[PathToExport],
    export_as: Literal["path", "download_link"],
) -> AsyncJobGet:
    if export_as == "path":
        task_name = EXPORT_DATA_TASK_NAME
    elif export_as == "download_link":
        task_name = EXPORT_DATA_AS_DOWNLOAD_LINK_TASK_NAME
    else:
        msg = f"Invalid export_as value: {export_as}"
        raise ValueError(msg)
    task_uuid = await task_manager.submit_task(
        execution_metadata=ExecutionMetadata(
            name=task_name,
            ephemeral=False,
            queue=TasksQueue.CPU_BOUND,
        ),
        owner_metadata=owner_metadata,
        user_id=user_id,
        product_name=product_name,
        paths_to_export=paths_to_export,
    )
    return AsyncJobGet(job_id=task_uuid, job_name=task_name)
