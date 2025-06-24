import logging
from abc import ABC, abstractmethod
from asyncio import Task
from datetime import timedelta
from typing import Final, Generic, TypeVar

from common_library.async_tools import cancel_wait_task
from pydantic import NonNegativeInt
from servicelib.background_task import create_periodic_task
from servicelib.logging_utils import log_catch, log_context
from servicelib.redis import RedisClientSDK
from servicelib.utils import logged_gather
from settings_library.redis import RedisDatabase

_logger = logging.getLogger(__name__)

_REDIS_MAX_CONCURRENCY: Final[NonNegativeInt] = 10
_DEFAULT_CLEANUP_INTERVAL: Final[timedelta] = timedelta(minutes=1)

Identifier = TypeVar("Identifier")
ResourceObject = TypeVar("ResourceObject")
CleanupContext = TypeVar("CleanupContext")


class BaseDistributedIdentifierManager(
    ABC, Generic[Identifier, ResourceObject, CleanupContext]
):
    """Used to implement managers for resources that require book keeping
    in a distributed system.

    NOTE: that ``Identifier`` and ``CleanupContext`` are serialized and deserialized
    to and from Redis.

    Generics:
        Identifier -- a user defined object: used to uniquely identify the resource
        ResourceObject -- a user defined object: referring to an existing resource
        CleanupContext -- a user defined object: contains all necessary
            arguments used for removal and cleanup.
    """

    def __init__(
        self,
        redis_client_sdk: RedisClientSDK,
        *,
        cleanup_interval: timedelta = _DEFAULT_CLEANUP_INTERVAL,
    ) -> None:
        """
        Arguments:
            redis_client_sdk -- client connecting to Redis

        Keyword Arguments:
            cleanup_interval -- interval at which cleanup for unused
            resources runs (default: {_DEFAULT_CLEANUP_INTERVAL})
        """

        if not redis_client_sdk.redis_dsn.endswith(
            f"{RedisDatabase.DISTRIBUTED_IDENTIFIERS}"
        ):
            msg = (
                f"Redis endpoint {redis_client_sdk.redis_dsn} contains the wrong database."
                f"Expected {RedisDatabase.DISTRIBUTED_IDENTIFIERS}"
            )
            raise TypeError(msg)

        self._redis_client_sdk = redis_client_sdk
        self.cleanup_interval = cleanup_interval

        self._cleanup_task: Task | None = None

    async def setup(self) -> None:
        self._cleanup_task = create_periodic_task(
            self._cleanup_unused_identifiers,
            interval=self.cleanup_interval,
            task_name="cleanup_unused_identifiers_task",
        )

    async def shutdown(self) -> None:
        if self._cleanup_task:
            await cancel_wait_task(self._cleanup_task, max_delay=5)

    @classmethod
    def class_path(cls) -> str:
        return f"{cls.__module__}.{cls.__name__}"

    @classmethod
    def _redis_key_prefix(cls) -> str:
        return f"{cls.class_path()}:"

    @classmethod
    def _to_redis_key(cls, identifier: Identifier) -> str:
        return f"{cls._redis_key_prefix()}{cls._serialize_identifier(identifier)}"

    @classmethod
    def _from_redis_key(cls, redis_key: str) -> Identifier:
        sad = redis_key.removeprefix(cls._redis_key_prefix())
        return cls._deserialize_identifier(sad)

    async def _get_identifier_context(
        self, identifier: Identifier
    ) -> CleanupContext | None:
        raw: str | None = await self._redis_client_sdk.redis.get(
            self._to_redis_key(identifier)
        )
        return self._deserialize_cleanup_context(raw) if raw else None

    async def _get_tracked(self) -> dict[Identifier, CleanupContext]:
        identifiers: list[Identifier] = [
            self._from_redis_key(redis_key)
            for redis_key in await self._redis_client_sdk.redis.keys(
                f"{self._redis_key_prefix()}*"
            )
        ]

        cleanup_contexts: list[CleanupContext | None] = await logged_gather(
            *(self._get_identifier_context(identifier) for identifier in identifiers),
            max_concurrency=_REDIS_MAX_CONCURRENCY,
        )

        return {
            identifier: cleanup_context
            for identifier, cleanup_context in zip(
                identifiers, cleanup_contexts, strict=True
            )
            # NOTE: cleanup_context will be None if the key was removed before
            # recovering all the cleanup_contexts
            if cleanup_context is not None
        }

    async def _cleanup_unused_identifiers(self) -> None:
        # removes no longer used identifiers
        tracked_data: dict[Identifier, CleanupContext] = await self._get_tracked()
        _logger.info("Will remove unused  %s", list(tracked_data.keys()))

        for identifier, cleanup_context in tracked_data.items():
            if await self.is_used(identifier, cleanup_context):
                continue

            await self.remove(identifier)

    async def create(
        self, *, cleanup_context: CleanupContext, **extra_kwargs
    ) -> tuple[Identifier, ResourceObject]:
        """Used for creating the resources

        Arguments:
            cleanup_context -- user defined CleanupContext object
            **extra_kwargs -- can be overloaded by the user

        Returns:
            tuple[identifier for the resource, resource object]
        """
        identifier, result = await self._create(**extra_kwargs)
        await self._redis_client_sdk.redis.set(
            self._to_redis_key(identifier),
            self._serialize_cleanup_context(cleanup_context),
        )
        return identifier, result

    async def remove(self, identifier: Identifier, *, reraise: bool = False) -> None:
        """Attempts to remove the resource, if an error occurs it is logged.

        Arguments:
            identifier -- user chosen identifier for the resource
            reraise -- when True raises any exception raised by ``destroy`` (default: {False})
        """

        cleanup_context = await self._get_identifier_context(identifier)
        if cleanup_context is None:
            _logger.warning(
                "Something went wrong, did not find any context for %s", identifier
            )
            return

        with (
            log_context(
                _logger, logging.DEBUG, f"{self.__class__}: removing {identifier}"
            ),
            log_catch(_logger, reraise=reraise),
        ):
            await self._destroy(identifier, cleanup_context)

        await self._redis_client_sdk.redis.delete(self._to_redis_key(identifier))

    @classmethod
    @abstractmethod
    def _deserialize_identifier(cls, raw: str) -> Identifier:
        """User provided deserialization for the identifier

        Arguments:
            raw -- stream to be deserialized

        Returns:
            an identifier object
        """

    @classmethod
    @abstractmethod
    def _serialize_identifier(cls, identifier: Identifier) -> str:
        """User provided serialization for the identifier

        Arguments:
            cleanup_context -- user defined identifier object

        Returns:
            object encoded as string
        """

    @classmethod
    @abstractmethod
    def _deserialize_cleanup_context(cls, raw: str) -> CleanupContext:
        """User provided deserialization for the context

        Arguments:
            raw -- stream to be deserialized

        Returns:
            an object of the type chosen by the user
        """

    @classmethod
    @abstractmethod
    def _serialize_cleanup_context(cls, cleanup_context: CleanupContext) -> str:
        """User provided serialization for the context

        Arguments:
            cleanup_context -- user defined cleanup context object

        Returns:
            object encoded as string
        """

    @abstractmethod
    async def is_used(
        self, identifier: Identifier, cleanup_context: CleanupContext
    ) -> bool:
        """Check if the resource associated to the ``identifier`` is
        still being used.
        # NOTE: a resource can be created but not in use.

        Arguments:
            identifier -- user chosen identifier for the resource
            cleanup_context -- user defined CleanupContext object

        Returns:
            True if ``identifier`` is still being used
        """

    @abstractmethod
    async def _create(self, **extra_kwargs) -> tuple[Identifier, ResourceObject]:
        """Used INTERNALLY for creating the resources.
        # NOTE: should not be used directly, use the public
        version ``create`` instead.

        Arguments:
            **extra_kwargs -- can be overloaded by the user

        Returns:
            tuple[identifier for the resource, resource object]
        """

    @abstractmethod
    async def get(
        self, identifier: Identifier, **extra_kwargs
    ) -> ResourceObject | None:
        """If exists, returns the resource.

        Arguments:
            identifier -- user chosen identifier for the resource
            **extra_kwargs -- can be overloaded by the user

        Returns:
            None if the resource does not exit
        """

    @abstractmethod
    async def _destroy(
        self, identifier: Identifier, cleanup_context: CleanupContext
    ) -> None:
        """Used to destroy an existing resource
        # NOTE: should not be used directly, use the public
        version ``remove`` instead.

        Arguments:
            identifier -- user chosen identifier for the resource
            cleanup_context -- user defined CleanupContext object
        """
