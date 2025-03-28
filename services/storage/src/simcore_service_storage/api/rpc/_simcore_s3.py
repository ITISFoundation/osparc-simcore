from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobNameData,
)
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from servicelib.rabbitmq._rpc_router import RPCRouter

from ...modules.celery import get_celery_client
from .._worker_tasks._simcore_s3 import deep_copy_files_from_project

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
