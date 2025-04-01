from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobNameData,
)
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from models_library.projects_nodes_io import StorageFileID
from servicelib.rabbitmq import RPCRouter

from ...modules.celery import get_celery_client
from .._worker_tasks._simcore_s3 import data_export, deep_copy_files_from_project

router = RPCRouter()


@router.expose(reraise_if_error_type=None)
async def copy_folders_from_project(
    app: FastAPI,
    job_id_data: AsyncJobNameData,
    body: FoldersBody,
) -> AsyncJobGet:
    task_uuid = await get_celery_client(app).send_task(
        deep_copy_files_from_project.__name__,
        task_context=job_id_data.model_dump(),
        user_id=job_id_data.user_id,
        body=body,
    )

    return AsyncJobGet(job_id=task_uuid)


@router.expose()
async def start_data_export(
    app: FastAPI, job_id_data: AsyncJobNameData, paths_to_export: list[StorageFileID]
) -> AsyncJobGet:
    task_uuid = await get_celery_client(app).send_task(
        data_export.__name__,
        task_context=job_id_data.model_dump(),
        user_id=job_id_data.user_id,
        paths_to_export=paths_to_export,
    )
    return AsyncJobGet(
        job_id=task_uuid,
    )
