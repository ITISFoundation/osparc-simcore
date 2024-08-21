import datetime
import logging
from asyncio.log import logger
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

import redis
from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus
from redis.asyncio.lock import Lock
from servicelib.background_task import periodic_task
from servicelib.logging_utils import log_context

from ..redis import get_redis_lock_manager_client
from ..users.api import FullNameDict
from .exceptions import ProjectLockError

_logger = logging.getLogger(__name__)

PROJECT_REDIS_LOCK_KEY: str = "project_lock:{}"
PROJECT_LOCK_TIMEOUT: Final[datetime.timedelta] = datetime.timedelta(seconds=10)
ProjectLock = Lock


async def _auto_extend_project_lock(project_lock: Lock) -> None:
    # NOTE: the background task already catches anything that might raise here
    await project_lock.reacquire()


@asynccontextmanager
async def lock_project(
    app: web.Application,
    project_uuid: str | ProjectID,
    status: ProjectStatus,
    user_id: int,
    user_fullname: FullNameDict,
) -> AsyncIterator[None]:
    """Context manager to lock and unlock a project by user_id

    Raises:
        ProjectLockError: if project is already locked
    """

    redis_lock = get_redis_lock_manager_client(app).lock(
        PROJECT_REDIS_LOCK_KEY.format(project_uuid),
        timeout=PROJECT_LOCK_TIMEOUT.total_seconds(),
    )
    try:
        if not await redis_lock.acquire(
            blocking=False,
            token=ProjectLocked(
                value=True,
                owner=Owner(user_id=user_id, **user_fullname),  # type: ignore[arg-type]
                status=status,
            ).json(),
        ):
            msg = f"Lock for project {project_uuid!r} user {user_id!r} could not be acquired"
            raise ProjectLockError(msg)

        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"with lock for {user_id=}:{user_fullname=}:{project_uuid=}:{status=}",
        ):
            async with periodic_task(
                _auto_extend_project_lock,
                interval=0.6 * PROJECT_LOCK_TIMEOUT,
                task_name=f"{PROJECT_REDIS_LOCK_KEY.format(project_uuid)}_lock_auto_extend",
                project_lock=redis_lock,
            ):
                yield

    finally:
        # let's ensure we release that stuff
        try:
            if await redis_lock.owned():
                await redis_lock.release()
        except (redis.exceptions.LockError, redis.exceptions.LockNotOwnedError) as exc:
            logger.warning(
                "releasing %s unexpectedly raised an exception: %s",
                f"{redis_lock=!r}",
                f"{exc}",
            )


async def is_project_locked(
    app: web.Application, project_uuid: str | ProjectID
) -> bool:
    redis_lock = get_redis_lock_manager_client(app).lock(
        PROJECT_REDIS_LOCK_KEY.format(project_uuid)
    )
    return await redis_lock.locked()


async def get_project_locked_state(
    app: web.Application, project_uuid: str | ProjectID
) -> ProjectLocked | None:
    """
    Returns:
        ProjectLocked object if the project project_uuid is locked or None otherwise
    """
    if await is_project_locked(app, project_uuid):
        redis_locks_client = get_redis_lock_manager_client(app)

        if lock_value := await redis_locks_client.get(
            PROJECT_REDIS_LOCK_KEY.format(project_uuid)
        ):
            return ProjectLocked.parse_raw(lock_value)
    return None
