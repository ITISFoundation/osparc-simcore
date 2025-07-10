from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobFilter,
    AsyncJobGet,
)
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from models_library.api_schemas_webserver.storage import PathToExport
from servicelib.celery.models import TaskFilter
from servicelib.celery.task_manager import TaskManager
from servicelib.rabbitmq import RPCRouter

from ...modules.celery.tasks import TaskQueue
from .._worker_tasks._simcore_s3 import deep_copy_files_from_project, export_data

router = RPCRouter()


@router.expose(reraise_if_error_type=None)
async def copy_folders_from_project(
    task_manager: TaskManager,
    job_filter: AsyncJobFilter,
    body: FoldersBody,
) -> AsyncJobGet:
    task_name = deep_copy_files_from_project.__name__
    task_filter = TaskFilter.model_validate(job_filter.model_dump())

    task_uuid = await task_manager.send_task(
        task_name=task_name,
        task_filter=task_filter,
        user_id=job_filter.user_id,
        body=body,
    )

    return AsyncJobGet(job_id=task_uuid, job_name=task_name)


@router.expose()
async def start_export_data(
    task_manager: TaskManager,
    job_filter: AsyncJobFilter,
    paths_to_export: list[PathToExport],
) -> AsyncJobGet:
    task_name = export_data.__name__

    task_filter = TaskFilter.model_validate(job_filter.model_dump())
    task_uuid = await task_manager.send_task(
        task_name=task_name,
        task_filter=task_filter,
        task_ephemeral=False,
        task_queue=TaskQueue.CPU_BOUND,
        user_id=job_filter.user_id,
        paths_to_export=paths_to_export,
    )
    return AsyncJobGet(job_id=task_uuid, job_name=task_name)
