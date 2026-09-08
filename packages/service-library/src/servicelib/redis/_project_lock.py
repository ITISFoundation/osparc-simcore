import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Final, ParamSpec, TypeVar
from uuid import uuid4

from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus

from ..logging_utils import log_catch
from ._client import RedisClientSDK
from ._decorators import exclusive
from ._errors import CouldNotAcquireLockError, ProjectLockError
from ._utils import handle_redis_returns_union_types

_PROJECT_REDIS_LOCK_KEY: Final[str] = "project_lock:{}"
_PROJECT_REDIS_READ_LOCK_KEY: Final[str] = "project_read_lock:{}:{}"
_PROJECT_REDIS_READERS_SET_KEY: Final[str] = "project_read_locks:{}"

_logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def with_project_locked(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    *,
    project_uuid: str | ProjectID,
    status: ProjectStatus,
    owner: Owner | None,
    notification_cb: Callable[[], Awaitable[None]] | None,
    blocking: bool = False,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Creates a distributed auto-sustained Redis lock for a project.

    Arguments:
        redis_client -- the client to use to access redis
        project_uuid -- the project UUID
        status -- the project status
        owner -- the owner of the lock (default: {None})
        notification_cb -- optional callback called after the project is locked and after it is unlocked

    Returns:
        the decorated function return value

    Raises:
        raises anything from the decorated function and from the optional notification callback
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
                blocking=blocking,
            )
            async def _exclusive_func(*args, **kwargs) -> R:
                if notification_cb is not None:
                    with log_catch(_logger, reraise=False):
                        await notification_cb()
                return await func(*args, **kwargs)

            try:
                return await _exclusive_func(*args, **kwargs)

            except CouldNotAcquireLockError as e:
                raise ProjectLockError from e
            finally:
                # we are now unlocked
                if notification_cb is not None:
                    with log_catch(_logger, reraise=False):
                        await notification_cb()

        return _wrapper

    return _decorator


def with_project_read_locked(
    redis_client: RedisClientSDK | Callable[..., RedisClientSDK],
    *,
    project_uuid: str | ProjectID,
    status: ProjectStatus,
    owner: Owner | None,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Runs concurrent project readers while excluding project writers at admission."""

    def _decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            client = redis_client(*args, **kwargs) if not isinstance(redis_client, RedisClientSDK) else redis_client
            reader_lock_key = _PROJECT_REDIS_READ_LOCK_KEY.format(project_uuid, uuid4())
            readers_set_key = _PROJECT_REDIS_READERS_SET_KEY.format(project_uuid)

            @exclusive(client, lock_key=reader_lock_key)
            async def _read_locked() -> R:
                try:

                    @with_project_locked(
                        client,
                        project_uuid=project_uuid,
                        status=status,
                        owner=owner,
                        notification_cb=None,
                        blocking=True,
                    )
                    async def _register_reader() -> None:
                        await handle_redis_returns_union_types(client.redis.sadd(readers_set_key, reader_lock_key))

                    await _register_reader()
                    return await func(*args, **kwargs)
                finally:
                    await handle_redis_returns_union_types(client.redis.srem(readers_set_key, reader_lock_key))

            return await _read_locked()

        return _wrapper

    return _decorator


async def has_project_read_locks(
    redis_client: RedisClientSDK,
    project_uuid: str | ProjectID,
) -> bool:
    readers_set_key = _PROJECT_REDIS_READERS_SET_KEY.format(project_uuid)
    reader_lock_keys = {
        key.decode() if isinstance(key, bytes) else key
        for key in await handle_redis_returns_union_types(redis_client.redis.smembers(readers_set_key))
    }
    if not reader_lock_keys:
        return False

    async def _lock_exists(key: str) -> bool:
        return bool(await handle_redis_returns_union_types(redis_client.redis.exists(key)))

    lock_exists = await asyncio.gather(*(_lock_exists(key) for key in reader_lock_keys))
    stale_lock_keys = [key for key, exists in zip(reader_lock_keys, lock_exists, strict=True) if not exists]
    if stale_lock_keys:
        await handle_redis_returns_union_types(redis_client.redis.srem(readers_set_key, *stale_lock_keys))

    return any(lock_exists)


async def is_project_locked(redis_client: RedisClientSDK, project_uuid: str | ProjectID) -> bool:
    redis_lock = redis_client.create_lock(_PROJECT_REDIS_LOCK_KEY.format(project_uuid))
    return await redis_lock.locked()


async def get_project_locked_state(redis_client: RedisClientSDK, project_uuid: str | ProjectID) -> ProjectLocked | None:
    """
    Returns:
        ProjectLocked object if the project project_uuid is locked or None otherwise
    """
    if await is_project_locked(redis_client, project_uuid=project_uuid) and (
        lock_value := await redis_client.redis.get(_PROJECT_REDIS_LOCK_KEY.format(project_uuid))
    ):
        return ProjectLocked.model_validate_json(lock_value)
    return None
