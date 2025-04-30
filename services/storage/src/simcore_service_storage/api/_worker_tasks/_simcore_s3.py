import functools
import logging
from typing import Any

from aws_library.s3._models import S3ObjectKey
from celery import Task  # type: ignore[import-untyped]
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from models_library.api_schemas_webserver.storage import PathToExport
from models_library.progress_bar import ProgressReport
from models_library.projects_nodes_io import StorageFileID
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.logging_utils import log_context
from servicelib.progress_bar import ProgressBarData

from ...dsm import get_dsm_provider
from ...modules.celery.models import TaskID, TaskId
from ...modules.celery.utils import get_celery_worker, get_fastapi_app
from ...simcore_s3_dsm import SimcoreS3DataManager

_logger = logging.getLogger(__name__)


async def _task_progress_cb(
    task: Task, task_id: TaskId, report: ProgressReport
) -> None:
    worker = get_celery_worker(task.app)
    assert task.name  # nosec
    await worker.set_task_progress(
        task_id=task_id,
        report=report,
    )


async def deep_copy_files_from_project(
    task: Task, task_id: TaskId, user_id: UserID, body: FoldersBody
) -> dict[str, Any]:
    with log_context(
        _logger,
        logging.INFO,
        msg=f"copying {body.source['uuid']} -> {body.destination['uuid']} with {task.request.id}",
    ):
        dsm = get_dsm_provider(get_fastapi_app(task.app)).get(
            SimcoreS3DataManager.get_location_id()
        )
        assert isinstance(dsm, SimcoreS3DataManager)  # nosec
        async with ProgressBarData(
            num_steps=1,
            description="copying files",
            progress_report_cb=functools.partial(_task_progress_cb, task, task_id),
        ) as task_progress:
            await dsm.deep_copy_project_simcore_s3(
                user_id,
                body.source,
                body.destination,
                body.nodes_map,
                task_progress=task_progress,
            )

    return body.destination


async def export_data(
    task: Task,
    task_id: TaskID,
    *,
    user_id: UserID,
    paths_to_export: list[PathToExport],
) -> StorageFileID:
    """
    AccessRightError: in case user can't access project
    """
    with log_context(
        _logger,
        logging.INFO,
        f"'{task_id}' export data (for {user_id=}) fom selection: {paths_to_export}",
    ):
        dsm = get_dsm_provider(get_fastapi_app(task.app)).get(
            SimcoreS3DataManager.get_location_id()
        )
        assert isinstance(dsm, SimcoreS3DataManager)  # nosec

        object_keys = [
            TypeAdapter(S3ObjectKey).validate_python(f"{path_to_export}")
            for path_to_export in paths_to_export
        ]

        async def _progress_cb(report: ProgressReport) -> None:
            assert task.name  # nosec
            await get_celery_worker(task.app).set_task_progress(task_id, report)
            _logger.debug("'%s' progress %s", task_id, report.percent_value)

        async with ProgressBarData(
            num_steps=1,
            description=f"'{task_id}' export data",
            progress_report_cb=_progress_cb,
        ) as progress_bar:
            return await dsm.create_s3_export(
                user_id, object_keys, progress_bar=progress_bar
            )
