from typing import Literal

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobOwnerMetadata,
)
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from models_library.api_schemas_webserver.storage import PathToExport
from servicelib.celery.models import (
    ExecutionMetadata,
    OwnerMetadata,
    TasksQueue,
)
from servicelib.celery.task_manager import TaskManager
from servicelib.rabbitmq import RPCRouter

from .._worker_tasks._simcore_s3 import (
    deep_copy_files_from_project,
    export_data,
    export_data_as_download_link,
)

router = RPCRouter()


@router.expose(reraise_if_error_type=None)
async def copy_folders_from_project(
    task_manager: TaskManager,
    job_filter: AsyncJobOwnerMetadata,
    body: FoldersBody,
) -> AsyncJobGet:
    task_name = deep_copy_files_from_project.__name__
    task_filter = OwnerMetadata.model_validate(job_filter.model_dump())
    task_uuid = await task_manager.submit_task(
        execution_metadata=ExecutionMetadata(
            name=task_name,
        ),
        task_filter=task_filter,
        user_id=job_filter.user_id,
        body=body,
    )

    return AsyncJobGet(job_id=task_uuid, job_name=task_name)


@router.expose()
async def start_export_data(
    task_manager: TaskManager,
    job_filter: AsyncJobOwnerMetadata,
    paths_to_export: list[PathToExport],
    export_as: Literal["path", "download_link"],
) -> AsyncJobGet:
    if export_as == "path":
        task_name = export_data.__name__
    elif export_as == "download_link":
        task_name = export_data_as_download_link.__name__
    else:
        raise ValueError(f"Invalid export_as value: {export_as}")
    task_filter = OwnerMetadata.model_validate(job_filter.model_dump())
    task_uuid = await task_manager.submit_task(
        execution_metadata=ExecutionMetadata(
            name=task_name,
            ephemeral=False,
            queue=TasksQueue.CPU_BOUND,
        ),
        task_filter=task_filter,
        user_id=job_filter.user_id,
        paths_to_export=paths_to_export,
    )
    return AsyncJobGet(job_id=task_uuid, job_name=task_name)
