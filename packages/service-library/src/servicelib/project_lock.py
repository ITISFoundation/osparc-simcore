import datetime
import logging
from asyncio.log import logger
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final, TypeAlias

import redis
import redis.exceptions
from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus
from redis.asyncio.lock import Lock

from .background_task import periodic_task
from .logging_utils import log_context

_logger = logging.getLogger(__name__)

PROJECT_REDIS_LOCK_KEY: str = "project_lock:{}"
PROJECT_LOCK_TIMEOUT: Final[datetime.timedelta] = datetime.timedelta(seconds=10)
ProjectLock = Lock

ProjectLockError: TypeAlias = redis.exceptions.LockError


async def _auto_extend_project_lock(project_lock: Lock) -> None:
    # NOTE: the background task already catches anything that might raise here
    await project_lock.reacquire()


@asynccontextmanager
async def lock_project(
    redis_lock: Lock,
    project_uuid: str | ProjectID,
    status: ProjectStatus,
    owner: Owner | None = None,
) -> AsyncIterator[None]:
    """Context manager to lock and unlock a project by user_id

    Raises:
        ProjectLockError: if project is already locked
    """

    try:
        if not await redis_lock.acquire(
            blocking=False,
            token=ProjectLocked(
                value=True,
                owner=owner,
                status=status,
            ).model_dump_json(),
        ):
            msg = f"Lock for project {project_uuid!r} owner {owner!r} could not be acquired"
            raise ProjectLockError(msg)

        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"with lock for {owner=}:{project_uuid=}:{status=}",
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
