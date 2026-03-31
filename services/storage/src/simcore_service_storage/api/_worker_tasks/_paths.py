import logging
from pathlib import Path

from celery import Task  # type: ignore[import-untyped]
from celery_library.worker.app_server import get_app_server
from models_library.celery import TaskKey
from models_library.products import ProductName
from models_library.projects_nodes_io import LocationID, StorageFileID
from models_library.rabbitmq_messages import FileNotificationEventType
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from servicelib.logging_utils import log_context
from servicelib.utils import limited_gather

from ...constants import MAX_CONCURRENT_S3_TASKS
from ...dsm import get_dsm_provider
from ...modules.rabbitmq import post_file_notification

_logger = logging.getLogger(__name__)


async def compute_path_size(
    task: Task,
    task_key: TaskKey,
    user_id: UserID,
    product_name: ProductName,
    location_id: LocationID,
    path: Path,
) -> ByteSize:
    assert task_key  # nosec
    with log_context(
        _logger,
        logging.INFO,
        msg=f"computing path size {user_id=}, {location_id=}, {path=}",
    ):
        dsm = get_dsm_provider(get_app_server(task.app).app).get(location_id)
        return await dsm.compute_path_size(user_id, product_name, path=Path(path))


async def delete_paths(
    task: Task,
    task_key: TaskKey,
    user_id: UserID,
    location_id: LocationID,
    paths: set[Path],
) -> None:
    assert task_key  # nosec
    with log_context(
        _logger,
        logging.INFO,
        msg=f"delete {paths=} in {location_id=} for {user_id=}",
    ):
        app = get_app_server(task.app).app
        dsm = get_dsm_provider(app).get(location_id)
        files_ids: set[StorageFileID] = {TypeAdapter(StorageFileID).validate_python(f"{path}") for path in paths}
        await limited_gather(
            *[dsm.delete_file(user_id, file_id) for file_id in files_ids],
            limit=MAX_CONCURRENT_S3_TASKS,
        )
        await limited_gather(
            *[
                post_file_notification(
                    app,
                    event_type=FileNotificationEventType.FILE_DELETED,
                    user_id=user_id,
                    file_id=file_id,
                )
                for file_id in files_ids
            ],
            limit=MAX_CONCURRENT_S3_TASKS,
        )
