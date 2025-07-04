import logging
from pathlib import Path

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobNameData,
)
from models_library.projects_nodes_io import LocationID
from servicelib.celery.task_manager import TaskManager
from servicelib.rabbitmq import RPCRouter

from .._worker_tasks._paths import compute_path_size as remote_compute_path_size
from .._worker_tasks._paths import delete_paths as remote_delete_paths

_logger = logging.getLogger(__name__)
router = RPCRouter()


@router.expose(reraise_if_error_type=None)
async def compute_path_size(
    task_manager: TaskManager,
    job_id_data: AsyncJobNameData,
    location_id: LocationID,
    path: Path,
) -> AsyncJobGet:
    task_name = remote_compute_path_size.__name__
    task_uuid = await task_manager.send_task(
        name=task_name,
        context=job_id_data.model_dump(),
        user_id=job_id_data.user_id,
        location_id=location_id,
        path=path,
    )

    return AsyncJobGet(job_id=task_uuid, job_name=task_name)


@router.expose(reraise_if_error_type=None)
async def delete_paths(
    task_manager: TaskManager,
    job_id_data: AsyncJobNameData,
    location_id: LocationID,
    paths: set[Path],
) -> AsyncJobGet:
    task_name = remote_delete_paths.__name__
    task_uuid = await task_manager.send_task(
        name=task_name,
        context=job_id_data.model_dump(),
        user_id=job_id_data.user_id,
        location_id=location_id,
        paths=paths,
    )
    return AsyncJobGet(job_id=task_uuid, job_name=task_name)
