from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobNameData,
)
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from models_library.api_schemas_webserver.storage import PathToExport
from servicelib.queued_tasks.models import TaskMetadata, TasksQueue
from servicelib.rabbitmq import RPCRouter

from ...modules.celery import get_task_manager_from_app
from .._worker_tasks._simcore_s3 import deep_copy_files_from_project, export_data

router = RPCRouter()


@router.expose(reraise_if_error_type=None)
async def copy_folders_from_project(
    app: FastAPI,
    job_id_data: AsyncJobNameData,
    body: FoldersBody,
) -> AsyncJobGet:
    task_name = deep_copy_files_from_project.__name__
    task_uuid = await get_task_manager_from_app(app).submit_task(
        task_metadata=TaskMetadata(
            name=task_name,
        ),
        task_context=job_id_data.model_dump(),
        user_id=job_id_data.user_id,
        body=body.model_dump(mode="json"),
    )

    return AsyncJobGet(job_id=task_uuid, job_name=task_name)


@router.expose()
async def start_export_data(
    app: FastAPI, job_id_data: AsyncJobNameData, paths_to_export: list[PathToExport]
) -> AsyncJobGet:
    task_name = export_data.__name__
    task_uuid = await get_task_manager_from_app(app).submit_task(
        task_metadata=TaskMetadata(
            name=task_name,
            ephemeral=False,
            queue=TasksQueue.CPU_BOUND,
        ),
        task_context=job_id_data.model_dump(),
        user_id=job_id_data.user_id,
        paths_to_export=paths_to_export,
    )
    return AsyncJobGet(job_id=task_uuid, job_name=task_name)
