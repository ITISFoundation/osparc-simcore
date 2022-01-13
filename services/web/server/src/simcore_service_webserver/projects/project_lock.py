from typing import Optional, Union

import aioredlock
from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_state import Owner, ProjectLocked, ProjectStatus
from simcore_service_webserver.resource_manager.redis import (
    get_redis_lock_manager,
    get_redis_lock_manager_client,
)

from ..users_api import UserNameDict

PROJECT_REDIS_LOCK_KEY: str = "project:{}"

ProjectLock = aioredlock.Lock
ProjectLockError = aioredlock.LockError


async def lock_project(
    app: web.Application,
    project_uuid: Union[str, ProjectID],
    status: ProjectStatus,
    user_id: int,
    user_name: UserNameDict,
) -> ProjectLock:
    """returns a distributed redis lock on the project defined by its UUID.
    NOTE: can be used as a context manager

    try:
        async with await lock_project(app, project_uuid, ProjectStatus.CLOSING, user_id, user_name):
            close_project(project_uuid) # do something with the project that requires the project to be locked


    except aioredlock.LockError:
        pass # the lock could not be acquired

    """
    return await get_redis_lock_manager(app).lock(
        PROJECT_REDIS_LOCK_KEY.format(project_uuid),
        lock_timeout=None,
        lock_identifier=ProjectLocked(
            value=True,
            owner=Owner(user_id=user_id, **user_name),
            status=status,
        ).json(),
    )


async def is_project_locked(
    app: web.Application, project_uuid: Union[str, ProjectID]
) -> bool:
    return await get_redis_lock_manager(app).is_locked(
        PROJECT_REDIS_LOCK_KEY.format(project_uuid)
    )


async def get_project_locked_state(
    app: web.Application, project_uuid: Union[str, ProjectID]
) -> Optional[ProjectLocked]:
    """returns the ProjectLocked object if the project is locked"""
    if await is_project_locked(app, project_uuid):
        project_locked: Optional[str] = await get_redis_lock_manager_client(app).get(
            PROJECT_REDIS_LOCK_KEY.format(project_uuid)
        )
        if project_locked:
            return ProjectLocked.parse_raw(project_locked)
