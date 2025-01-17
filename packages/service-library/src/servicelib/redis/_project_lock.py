import functools
from collections.abc import Callable, Coroutine
from typing import Any, Final, ParamSpec, TypeVar

from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus

from ._client import RedisClientSDK
from ._decorators import exclusive
from ._errors import CouldNotAcquireLockError, ProjectLockError

_PROJECT_REDIS_LOCK_KEY: Final[str] = "project_lock:{}"


P = ParamSpec("P")
R = TypeVar("R")


def with_project_locked(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    *,
    project_uuid: str | ProjectID,
    status: ProjectStatus,
    owner: Owner | None = None,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]
]:
    """creates a distributed auto sustained Redis lock for project with project_uuid, keeping its status and owner in the lock data

    Arguments:
        redis_client -- the client to use to access redis
        project_uuid -- the project UUID
        status -- the project status

    Keyword Arguments:
        owner -- the owner of the lock (default: {None})

    Returns:
        the decorated function return value
    """

    def _decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            @exclusive(
                redis_client,
                lock_key=_PROJECT_REDIS_LOCK_KEY.format(project_uuid),
                lock_value=ProjectLocked(
                    value=True,
                    owner=owner,
                    status=status,
                ).model_dump_json(),
            )
            async def _exclusive_func(*args, **kwargs) -> R:
                return await func(*args, **kwargs)

            try:
                return await _exclusive_func(*args, **kwargs)
            except CouldNotAcquireLockError as e:
                raise ProjectLockError from e

        return _wrapper

    return _decorator


async def is_project_locked(
    redis_client: RedisClientSDK, project_uuid: str | ProjectID
) -> bool:
    redis_lock = redis_client.create_lock(_PROJECT_REDIS_LOCK_KEY.format(project_uuid))
    return await redis_lock.locked()


async def get_project_locked_state(
    redis_client: RedisClientSDK, project_uuid: str | ProjectID
) -> ProjectLocked | None:
    """
    Returns:
        ProjectLocked object if the project project_uuid is locked or None otherwise
    """
    if await is_project_locked(redis_client, project_uuid=project_uuid) and (
        lock_value := await redis_client.redis.get(
            _PROJECT_REDIS_LOCK_KEY.format(project_uuid)
        )
    ):
        return ProjectLocked.model_validate_json(lock_value)
    return None
