from asyncio import AbstractEventLoop, get_event_loop, run_coroutine_threadsafe
from typing import TypeAlias, cast
from uuid import uuid4

from fastapi import FastAPI
from models_library.projects_nodes_io import StorageFileID
from models_library.users import UserID
from servicelib.progress_bar import ProgressReport, ReportCB

from ...dsm import SimcoreS3DataManager, get_dsm_provider
from ._tqdm_utils import get_export_progress, set_absolute_progress

OsparcJobID: TypeAlias = str


async def _async_export(
    app: FastAPI,
    *,
    osparc_job_id: OsparcJobID,
    user_id: UserID,
    paths_to_export: list[StorageFileID],
    progress_cb: ReportCB,
) -> StorageFileID:
    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(app).get(SimcoreS3DataManager.get_location_id()),
    )

    with get_export_progress(
        total=1, description=f"export job: {osparc_job_id}"
    ) as pbar:

        def _sync_progress_updates(report: ProgressReport) -> None:
            set_absolute_progress(pbar, current_progress=report.actual_value)

            # progress for celery task
            progress_cb(report)

        async def _progress_cb(report: ProgressReport) -> None:
            await get_event_loop().run_in_executor(None, _sync_progress_updates, report)
            # TODO: propagate progress via socketio -> also include `osparc_job_id`

        return await dsm.create_s3_export(
            user_id, paths_to_export, progress_cb=_progress_cb
        )


def fake_celery_export(  # TODO: replace this with the  Celery interface
    loop: AbstractEventLoop,
    app: FastAPI,
    user_id: UserID,
    paths_to_export: list[StorageFileID],
) -> StorageFileID:
    # NOTE: `osparc_job_id` is required to associate tasks from the worker to the frontend.
    # The Celery task should propagate this information to the FE togehter with the progress (nmaybe as metadata?).
    # When progress is published via socket.io `osparc_job_id` will be used by the FE to associate the value
    # to the proper elment.
    osparc_job_id = f"some_random_id_{uuid4()}"

    def _progress_cb(report: ProgressReport) -> None:
        _ = report  # TODO: propagate to celery task status

    return run_coroutine_threadsafe(
        _async_export(
            app,
            osparc_job_id=osparc_job_id,
            user_id=user_id,
            paths_to_export=paths_to_export,
            progress_cb=_progress_cb,
        ),
        loop,
    ).result()
