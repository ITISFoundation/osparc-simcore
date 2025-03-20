import logging
from typing import Any

from celery import Task
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from models_library.users import UserID
from servicelib.logging_utils import log_context

from ...dsm import get_dsm_provider
from ...modules.celery.utils import get_fastapi_app
from ...simcore_s3_dsm import SimcoreS3DataManager

_logger = logging.getLogger(__name__)


async def deep_copy_files_from_project(
    task: Task, user_id: UserID, body: FoldersBody
) -> dict[str, Any]:
    with log_context(
        _logger,
        logging.INFO,
        msg=f"copying {body.source['uuid']} -> {body.destination['uuid']}",
    ):
        dsm = get_dsm_provider(get_fastapi_app(task.app)).get(
            SimcoreS3DataManager.get_location_id()
        )
        assert isinstance(dsm, SimcoreS3DataManager)  # nosec
        await dsm.deep_copy_project_simcore_s3(
            user_id,
            body.source,
            body.destination,
            body.nodes_map,
            task_progress=None,  # TODO: fix by using a real progress bar
        )

    return body.destination
