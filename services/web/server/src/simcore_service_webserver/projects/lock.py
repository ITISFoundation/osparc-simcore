import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus
from servicelib.project_lock import PROJECT_LOCK_TIMEOUT, PROJECT_REDIS_LOCK_KEY
from servicelib.project_lock import lock_project as common_lock_project

from ..redis import get_redis_lock_manager_client
from ..users.api import FullNameDict

_logger = logging.getLogger(__name__)


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
    owner = Owner(user_id=user_id, **user_fullname)

    async with common_lock_project(
        redis_lock, project_uuid=project_uuid, status=status, owner=owner
    ):
        yield


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
            return ProjectLocked.model_validate_json(lock_value)
    return None
