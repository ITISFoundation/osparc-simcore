import logging
from pathlib import Path
from typing import Final

from celery import Task  # type: ignore[import-untyped]
from celery_library.worker.app_server import get_app_server
from models_library.celery import TaskKey
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID, NodeID, StorageFileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from servicelib.logging_utils import log_context
from servicelib.utils import limited_gather

from ...constants import MAX_CONCURRENT_S3_TASKS
from ...dsm import get_dsm_provider
from ...dsm_factory import BaseDataManager
from ...simcore_s3_dsm import SimcoreS3DataManager

_logger = logging.getLogger(__name__)

_PROJECT_FOLDER_MAX_PARTS: Final[int] = 2


async def compute_path_size(
    task: Task,
    task_key: TaskKey,
    user_id: UserID,
    product_name: ProductName,
    location_id: LocationID,
    path: Path,
) -> ByteSize:
    assert task_key  # nosec
    with log_context(_logger, logging.INFO, msg=f"computing path size {user_id=}, {location_id=}, {path=}"):
        dsm = get_dsm_provider(get_app_server(task.app).app).get(location_id)
        return await dsm.compute_path_size(user_id, product_name, path=Path(path))


async def _delete_path(dsm: BaseDataManager, user_id: UserID, path: Path) -> None:
    # NOTE: a project or project/node folder is not a file identifier, it is authorized at project level
    if isinstance(dsm, SimcoreS3DataManager) and 0 < len(path.parts) <= _PROJECT_FOLDER_MAX_PARTS:
        node_id = NodeID(path.parts[1]) if len(path.parts) == _PROJECT_FOLDER_MAX_PARTS else None
        await dsm.delete_project_simcore_s3(user_id, ProjectID(path.parts[0]), node_id)
        return

    await dsm.delete_file(user_id, TypeAdapter(StorageFileID).validate_python(f"{path}"))


async def delete_paths(
    task: Task,
    task_key: TaskKey,
    user_id: UserID,
    product_name: ProductName,
    location_id: LocationID,
    paths: set[Path],
) -> None:
    assert task_key  # nosec
    with log_context(_logger, logging.INFO, msg=f"delete {paths=} in {location_id=} for {user_id=}, {product_name=}"):
        dsm = get_dsm_provider(get_app_server(task.app).app).get(location_id)
        await limited_gather(*[_delete_path(dsm, user_id, path) for path in paths], limit=MAX_CONCURRENT_S3_TASKS)
