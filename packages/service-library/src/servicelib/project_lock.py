import datetime
import functools
from collections.abc import Callable, Coroutine
from typing import Any, Final, ParamSpec, TypeAlias, TypeVar

import redis
import redis.exceptions
from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus

from .redis import RedisClientSDK, exclusive

PROJECT_REDIS_LOCK_KEY: str = "project_lock:{}"
PROJECT_LOCK_TIMEOUT: Final[datetime.timedelta] = datetime.timedelta(seconds=10)

ProjectLockError: TypeAlias = redis.exceptions.LockError


P = ParamSpec("P")
R = TypeVar("R")


def with_locked_project(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    *,
    project_uuid: str | ProjectID,
    status: ProjectStatus,
    owner: Owner | None = None,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]
]:
    def _decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @exclusive(
            redis_client,
            lock_key=PROJECT_REDIS_LOCK_KEY.format(project_uuid),
            lock_value=ProjectLocked(
                value=True,
                owner=owner,
                status=status,
            ).model_dump_json(),
        )
        @functools.wraps(func)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await func(*args, **kwargs)

        return _wrapper

    return _decorator
