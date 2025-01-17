from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Awaitable, ParamSpec, TypeVar

from aiohttp import web
from models_library.projects_access import Owner
from models_library.projects_state import ProjectStatus
from servicelib.redis._project_lock import with_project_locked

from ..redis import get_redis_lock_manager_client_sdk

P = ParamSpec("P")
R = TypeVar("R")


def with_project_locked_and_notify(
    app: web.Application,
    *,
    project_uuid: str,
    status: ProjectStatus,
    owner: Owner,
    notification_cb: Awaitable | None,
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
                owner=owner,
            )
            async def _locked_func() -> R:
                if notification_cb is not None:
                    await notification_cb

                return await func(*args, **kwargs)

            result = await _locked_func()
            if notification_cb is not None:
                await notification_cb
            return result

        return _wrapper

    return _decorator
