import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Final

import redis
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_state import ProjectLocked, ProjectStatus
from redis.asyncio.lock import Lock
from servicelib.background_task import periodic_task
from servicelib.logging_utils import log_context
from simcore_postgres_database.utils_projects import ProjectsRepo

from ..core.settings import ApplicationSettings
from .efs_manager import EfsManager
from .modules.redis import get_redis_lock_client

_logger = logging.getLogger(__name__)


PROJECT_REDIS_LOCK_KEY: str = "project_lock:{}"
PROJECT_LOCK_TIMEOUT: Final[timedelta] = timedelta(seconds=10)


async def _auto_extend_project_lock(project_lock: Lock) -> None:
    # NOTE: the background task already catches anything that might raise here
    await project_lock.reacquire()


@asynccontextmanager
async def lock_project(
    app: FastAPI,
    project_uuid: ProjectID,
    status: ProjectStatus = ProjectStatus.MAINTAINING,
) -> AsyncIterator[None]:
    """Context manager to lock and unlock a project by user_id

    Raises:
        ProjectLockError: if project is already locked
    """

    redis_lock = get_redis_lock_client(app).redis.lock(
        PROJECT_REDIS_LOCK_KEY.format(project_uuid),
        timeout=PROJECT_LOCK_TIMEOUT.total_seconds(),
    )
    try:
        if not await redis_lock.acquire(
            blocking=False,
            token=ProjectLocked(
                value=True,
                owner=None,
                status=status,
            ).json(),
        ):
            msg = f"Lock for project {project_uuid!r} could not be acquired"
            raise ValueError(msg)

        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"with lock for {project_uuid=}:{status=}",
        ):
            async with periodic_task(
                _auto_extend_project_lock,
                interval=0.6 * PROJECT_LOCK_TIMEOUT,
                task_name=f"{PROJECT_REDIS_LOCK_KEY.format(project_uuid)}_lock_auto_extend",
                project_lock=redis_lock,
            ):
                yield

    finally:
        try:
            if await redis_lock.owned():
                await redis_lock.release()
        except (redis.exceptions.LockError, redis.exceptions.LockNotOwnedError) as exc:
            _logger.warning(
                "releasing %s unexpectedly raised an exception: %s",
                f"{redis_lock=!r}",
                f"{exc}",
            )


async def removal_policy_task(app: FastAPI) -> None:
    _logger.info("Removal policy task started")

    app_settings: ApplicationSettings = app.state.settings
    assert app_settings  # nosec
    efs_manager: EfsManager = app.state.efs_manager

    base_start_timestamp = datetime.now(tz=timezone.utc)

    efs_project_ids: list[
        ProjectID
    ] = await efs_manager.list_projects_across_whole_efs()

    projects_repo = ProjectsRepo(app.state.engine)
    for project_id in efs_project_ids:
        _project_last_change_date = await projects_repo.get_project_last_change_date(
            project_id
        )
        if (
            _project_last_change_date is None
            or _project_last_change_date
            < base_start_timestamp
            - app_settings.EFS_REMOVAL_POLICY_TASK_AGE_LIMIT_TIMEDELTA
        ):
            _logger.info(
                "Removing data for project %s started, project last change date %s, efs removal policy task age limit timedelta %s",
                project_id,
                _project_last_change_date,
                app_settings.EFS_REMOVAL_POLICY_TASK_AGE_LIMIT_TIMEDELTA,
            )
            async with lock_project(app, project_uuid=project_id):
                await efs_manager.remove_project_efs_data(project_id)
