# pylint: disable=too-many-arguments
from pathlib import Path
from typing import Final

from models_library.products import ProductName
from models_library.projects_nodes_io import LocationID
from models_library.users import UserID

from ....celery.models import ExecutionMetadata, OwnerMetadata, TaskName, TaskUUID
from ....celery.task_manager import TaskManager

COMPUTE_PATH_SIZE_TASK_NAME: Final[str] = "compute_path_size"
DELETE_PATHS_TASK_NAME: Final[str] = "delete_paths"


async def submit_compute_path_size_task(  # noqa: PLR0913
    task_manager: TaskManager,
    owner_metadata: OwnerMetadata,
    user_id: UserID,
    product_name: ProductName,
    location_id: LocationID,
    path: Path,
) -> tuple[TaskUUID, TaskName]:
    return await task_manager.submit_task(
        ExecutionMetadata(
            name=COMPUTE_PATH_SIZE_TASK_NAME,
        ),
        owner_metadata=owner_metadata,
        user_id=user_id,
        product_name=product_name,
        location_id=location_id,
        path=path,
    ), COMPUTE_PATH_SIZE_TASK_NAME


async def submit_delete_paths_task(
    task_manager: TaskManager,
    owner_metadata: OwnerMetadata,
    user_id: UserID,
    location_id: LocationID,
    paths: set[Path],
) -> tuple[TaskUUID, TaskName]:
    return await task_manager.submit_task(
        ExecutionMetadata(
            name=DELETE_PATHS_TASK_NAME,
        ),
        owner_metadata=owner_metadata,
        user_id=user_id,
        location_id=location_id,
        paths=paths,
    ), DELETE_PATHS_TASK_NAME
