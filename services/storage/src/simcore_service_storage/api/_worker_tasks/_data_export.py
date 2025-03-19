import logging
from typing import cast

from celery import Task  # type: ignore[import-untyped]
from models_library.progress_bar import ProgressReport
from models_library.projects_nodes_io import StorageFileID
from models_library.users import UserID

from ...dsm import get_dsm_provider
from ...modules.celery.utils import get_celery_worker_client, get_fastapi_app
from ...simcore_s3_dsm import SimcoreS3DataManager
from ._tqdm_utils import get_export_progress, set_absolute_progress

_logger = logging.getLogger(__name__)


async def data_export(
    task: Task,
    *,
    user_id: UserID,
    paths_to_export: list[StorageFileID],
) -> StorageFileID:
    _logger.info("Exporting for user '%s' files: %s", user_id, paths_to_export)

    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(get_fastapi_app(task.app)).get(
            SimcoreS3DataManager.get_location_id()
        ),
    )

    with get_export_progress(total=1, description=f"{task.name}") as pbar:

        async def _progress_cb(report: ProgressReport) -> None:
            set_absolute_progress(pbar, current_progress=report.actual_value)
            await get_celery_worker_client(task.app).set_task_progress(task, report)

        return await dsm.create_s3_export(
            user_id, paths_to_export, progress_cb=_progress_cb
        )
