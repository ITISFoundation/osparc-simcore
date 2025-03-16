from pathlib import Path

from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobNameData,
)
from models_library.projects_nodes_io import LocationID
from servicelib.rabbitmq import RPCRouter

from ...modules.celery import get_celery_client
from .._worker_tasks._paths import compute_path_size as remote_compute_path_size

router = RPCRouter()


@router.expose(reraise_if_error_type=None)
async def compute_path_size(
    app: FastAPI,
    job_id_data: AsyncJobNameData,
    # user_id: UserID,
    location_id: LocationID,
    path: Path,
) -> AsyncJobGet:
    assert app  # nosec

    task_uuid = await get_celery_client(app).send_task(
        remote_compute_path_size.__name__,
        task_context=job_id_data.model_dump(),
        user_id=job_id_data.user_id,
        location_id=location_id,
        path=path,
    )

    return AsyncJobGet(job_id=task_uuid)
