import logging
from pathlib import Path

from celery import Task
from models_library.projects_nodes_io import LocationID
from models_library.users import UserID
from pydantic import ByteSize
from servicelib.logging_utils import log_context

from ...dsm import get_dsm_provider
from ...modules.celery.utils import get_fastapi_app

_logger = logging.getLogger(__name__)


async def compute_path_size(
    task: Task, user_id: UserID, location_id: LocationID, path: Path
) -> ByteSize:
    with log_context(
        _logger,
        logging.INFO,
        msg=f"computing path size {user_id=}, {location_id=}, {path=}",
    ):
        dsm = get_dsm_provider(get_fastapi_app(task.app)).get(location_id)
        return await dsm.compute_path_size(user_id, path=Path(path))
