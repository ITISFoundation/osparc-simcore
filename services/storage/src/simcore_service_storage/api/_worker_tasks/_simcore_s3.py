import datetime
import functools
import logging
from typing import Any

from aws_library.s3._models import S3ObjectKey
from celery import Task  # type: ignore[import-untyped]
from celery_library.worker.app_server import get_app_server
from models_library.api_schemas_storage.search_async_jobs import SearchResultItem
from models_library.api_schemas_storage.storage_schemas import (
    UNDEFINED_SIZE,
    FoldersBody,
    LinkType,
    PresignedLink,
)
from models_library.api_schemas_webserver.storage import PathToExport
from models_library.progress_bar import ProgressReport
from models_library.projects import ProjectID
from models_library.projects_nodes_io import StorageFileID
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.celery.models import (
    TaskKey,
    TaskStreamItem,
)
from servicelib.logging_utils import log_context
from servicelib.progress_bar import ProgressBarData

from ...dsm import get_dsm_provider
from ...simcore_s3_dsm import SimcoreS3DataManager

_logger = logging.getLogger(__name__)


async def _task_progress_cb(
    task: Task, task_key: TaskKey, report: ProgressReport
) -> None:
    worker = get_app_server(task.app).task_manager
    assert task.name  # nosec
    await worker.set_task_progress(
        task_key=task_key,
        report=report,
    )


async def deep_copy_files_from_project(
    task: Task, task_key: TaskKey, user_id: UserID, body: FoldersBody
) -> dict[str, Any]:
    with log_context(
        _logger,
        logging.INFO,
        msg=f"copying {body.source['uuid']} -> {body.destination['uuid']} with {task.request.id}",
    ):
        dsm = get_dsm_provider(get_app_server(task.app).app).get(
            SimcoreS3DataManager.get_location_id()
        )
        assert isinstance(dsm, SimcoreS3DataManager)  # nosec
        async with ProgressBarData(
            num_steps=1,
            description="copying files",
            progress_report_cb=functools.partial(_task_progress_cb, task, task_key),
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
    task_key: TaskKey,
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
        f"'{task_key}' export data (for {user_id=}) fom selection: {paths_to_export}",
    ):
        dsm = get_dsm_provider(get_app_server(task.app).app).get(
            SimcoreS3DataManager.get_location_id()
        )
        assert isinstance(dsm, SimcoreS3DataManager)  # nosec

        object_keys = [
            TypeAdapter(S3ObjectKey).validate_python(f"{path_to_export}")
            for path_to_export in paths_to_export
        ]

        async def _progress_cb(report: ProgressReport) -> None:
            assert task.name  # nosec
            await get_app_server(task.app).task_manager.set_task_progress(
                task_key, report
            )
            _logger.debug("'%s' progress %s", task_key, report.percent_value)

        async with ProgressBarData(
            num_steps=1,
            description=f"'{task_key}' export data",
            progress_report_cb=_progress_cb,
        ) as progress_bar:
            return await dsm.create_s3_export(
                user_id, object_keys, progress_bar=progress_bar
            )


async def export_data_as_download_link(
    task: Task,
    task_key: TaskKey,
    *,
    user_id: UserID,
    paths_to_export: list[PathToExport],
) -> PresignedLink:
    """
    AccessRightError: in case user can't access project
    """
    s3_object = await export_data(
        task=task, task_key=task_key, user_id=user_id, paths_to_export=paths_to_export
    )

    dsm = get_dsm_provider(get_app_server(task.app).app).get(
        SimcoreS3DataManager.get_location_id()
    )

    download_link = await dsm.create_file_download_link(
        user_id=user_id, file_id=s3_object, link_type=LinkType.PRESIGNED
    )
    return PresignedLink(link=download_link)


async def search(
    task: Task,
    task_key: TaskKey,
    *,
    user_id: UserID,
    project_id: ProjectID | None,
    name_pattern: str,
    modified_at: tuple[datetime.datetime | None, datetime.datetime | None] | None,
) -> None:
    with log_context(
        _logger,
        logging.INFO,
        f"'{task_key}' search file {name_pattern=}",
    ):
        app_server = get_app_server(task.app)
        dsm = get_dsm_provider(app_server.app).get(
            SimcoreS3DataManager.get_location_id()
        )

        assert isinstance(dsm, SimcoreS3DataManager)  # nosec

        async for items in dsm.search(
            user_id=user_id,
            project_id=project_id,
            name_pattern=name_pattern,
            modified_at=modified_at,
            limit=1,  # NOTE: yield items as they come
        ):
            if not items:
                continue

            data = [
                TaskStreamItem(
                    data=SearchResultItem(
                        name=item.file_name,
                        project_id=item.project_id,
                        # NOTE: dirs in S3 are virtual, so we do not have created_at, last_modified info
                        created_at=None if item.is_directory else item.created_at,
                        modified_at=None if item.is_directory else item.last_modified,
                        is_directory=item.is_directory,
                        size=UNDEFINED_SIZE if item.is_directory else item.file_size,
                        path=item.object_name,
                    )
                )
                for item in items
            ]

            await app_server.task_manager.push_task_stream_items(
                task_key,
                *data,
            )

    await app_server.task_manager.set_task_stream_done(task_key)
