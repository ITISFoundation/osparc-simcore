from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from aiohttp import web
from models_library.projects_access import Owner
from models_library.projects_state import ProjectStatus
from servicelib.redis._project_lock import with_project_locked

from ..redis import get_redis_lock_manager_client_sdk
from ..users.api import FullNameDict
from .projects_api import retrieve_and_notify_project_locked_state

P = ParamSpec("P")
R = TypeVar("R")


def with_project_locked_and_notify(
    app: web.Application,
    *,
    project_uuid: str,
    status: ProjectStatus,
    user_id: int,
    user_name: FullNameDict,
    notify_users: bool,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]
]:
    def _decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @wraps(func)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            @with_project_locked(
                get_redis_lock_manager_client_sdk(app),
                project_uuid=project_uuid,
                status=status,
                owner=Owner(user_id=user_id, **user_name),
            )
            async def _locked_func() -> R:
                if notify_users:
                    await retrieve_and_notify_project_locked_state(
                        user_id, project_uuid, app
                    )

                return await func(*args, **kwargs)

            result = await _locked_func()
            if notify_users:
                await retrieve_and_notify_project_locked_state(
                    user_id, project_uuid, app
                )
            return result

        return _wrapper

    return _decorator
