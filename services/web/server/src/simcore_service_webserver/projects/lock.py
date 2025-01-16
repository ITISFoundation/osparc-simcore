from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus
from servicelib.project_lock import PROJECT_REDIS_LOCK_KEY, with_project_locked

from ..redis import get_redis_lock_manager_client, get_redis_lock_manager_client_sdk
from ..users.api import FullNameDict

P = ParamSpec("P")
R = TypeVar("R")


def with_locked_project_from_app(
    app: web.Application,
    *,
    project_uuid: str | ProjectID,
    status: ProjectStatus,
    user_id: int,
    user_fullname: FullNameDict,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]
]:
    def _decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @with_project_locked(
            get_redis_lock_manager_client_sdk(app),
            project_uuid=project_uuid,
            status=status,
            owner=Owner(user_id=user_id, **user_fullname),
        )
        @wraps(func)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await func(*args, **kwargs)

        return _wrapper

    return _decorator


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
