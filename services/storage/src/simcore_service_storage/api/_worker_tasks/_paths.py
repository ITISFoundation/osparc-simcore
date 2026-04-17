import logging
from pathlib import Path

from celery import Task  # type: ignore[import-untyped]
from celery_library.worker.app_server import get_app_server
from models_library.celery import TaskKey
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID, NodeID, StorageFileID
from models_library.rabbitmq_messages import FileNotificationEventType
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter, ValidationError
from servicelib.logging_utils import log_context
from servicelib.utils import limited_gather

from ...constants import MAX_CONCURRENT_FILE_DELETE_NOTIFICATIONS, MAX_CONCURRENT_S3_TASKS
from ...dsm import get_dsm_provider
from ...modules.rabbitmq import post_file_notification
from ...simcore_s3_dsm import SimcoreS3DataManager

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

        file_ids: set[StorageFileID] = set()
        directory_paths: list[tuple[ProjectID, NodeID | None]] = []

        for path in paths:
            try:
                file_id = TypeAdapter(StorageFileID).validate_python(f"{path}")
                file_ids.add(file_id)
            except ValidationError:
                parts = Path(path).parts
                if len(parts) > 1:
                    directory_paths.append((ProjectID(parts[0]), NodeID(parts[1])))
                elif len(parts) == 1:
                    directory_paths.append((ProjectID(parts[0]), None))
                else:
                    raise

        await limited_gather(
            *[dsm.delete_file(user_id, file_id) for file_id in file_ids],
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
                for file_id in file_ids
            ],
            limit=MAX_CONCURRENT_FILE_DELETE_NOTIFICATIONS,
        )

        if directory_paths:
            assert isinstance(dsm, SimcoreS3DataManager)  # nosec
            for project_id, node_id in directory_paths:
                await dsm.delete_project_simcore_s3(user_id, project_id, node_id)
