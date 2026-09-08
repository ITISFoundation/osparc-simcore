import functools
import logging
import time
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Final, ParamSpec, TypeVar
from uuid import uuid4

from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus

from ..background_task import periodic_task
from ..logging_utils import log_catch
from ._client import RedisClientSDK
from ._constants import DEFAULT_LOCK_TTL
from ._decorators import exclusive
from ._errors import CouldNotAcquireLockError, ProjectLockError
from ._utils import handle_redis_returns_union_types

_PROJECT_REDIS_LOCK_KEY: Final[str] = "project_lock:{}"
_PROJECT_REDIS_READ_LOCK_KEY: Final[str] = "project_read_lock:{}:{}"
_PROJECT_REDIS_READERS_ZSET_KEY: Final[str] = "project_read_locks:{}"

_logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


async def _refresh_project_read_lock_registration(
    redis_client: RedisClientSDK,
    *,
    reader_lock_key: str,
    readers_zset_key: str,
) -> None:
    now = time.time()
    await handle_redis_returns_union_types(redis_client.redis.zremrangebyscore(readers_zset_key, "-inf", now))
    await handle_redis_returns_union_types(
        redis_client.redis.zadd(
            readers_zset_key,
            {reader_lock_key: now + DEFAULT_LOCK_TTL.total_seconds()},
        )
    )
    await handle_redis_returns_union_types(redis_client.redis.expire(readers_zset_key, DEFAULT_LOCK_TTL))


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
            readers_zset_key = _PROJECT_REDIS_READERS_ZSET_KEY.format(project_uuid)

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
                        await _refresh_project_read_lock_registration(
                            client,
                            reader_lock_key=reader_lock_key,
                            readers_zset_key=readers_zset_key,
                        )

                    await _register_reader()
                    async with periodic_task(
                        _refresh_project_read_lock_registration,
                        interval=DEFAULT_LOCK_TTL / 2,
                        task_name=f"project-read-lock/refresh-registration/{reader_lock_key}",
                        raise_on_error=True,
                        redis_client=client,
                        reader_lock_key=reader_lock_key,
                        readers_zset_key=readers_zset_key,
                    ):
                        return await func(*args, **kwargs)
                finally:
                    await handle_redis_returns_union_types(client.redis.zrem(readers_zset_key, reader_lock_key))

            return await _read_locked()

        return _wrapper

    return _decorator


async def has_project_read_locks(
    redis_client: RedisClientSDK,
    project_uuid: str | ProjectID,
) -> bool:
    readers_zset_key = _PROJECT_REDIS_READERS_ZSET_KEY.format(project_uuid)
    await handle_redis_returns_union_types(redis_client.redis.zremrangebyscore(readers_zset_key, "-inf", time.time()))
    return bool(await handle_redis_returns_union_types(redis_client.redis.zcard(readers_zset_key)))


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
