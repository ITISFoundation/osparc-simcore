from functools import cached_property
from typing import Generic, TypeVar

from aiocache import Cache
from aiocache.serializers import PickleSerializer
from fastapi import FastAPI
from pydantic import NonNegativeFloat
from settings_library.redis import RedisDatabase

from ...core.settings import ApplicationSettings

T = TypeVar("T")


class ServiceStatusCache(Generic[T]):
    def __init__(self, app: FastAPI, ttl: NonNegativeFloat) -> None:
        settings: ApplicationSettings = app.state.settings

        self._cache = Cache.from_url(
            settings.DYNAMIC_SCHEDULER_REDIS.build_redis_dsn(
                RedisDatabase.DISTRIBUTED_CACHES
            )
        )
        self._cache.serializer = PickleSerializer()
        self.ttl = ttl

    @cached_property
    def namespace(self) -> str:
        return f"{self.__class__.__name__}"

    async def set_value(self, key: str, value: T) -> None:
        await self._cache.set(  # pylint:disable=no-member
            key, value, ttl=self.ttl, namespace=self.namespace
        )

    async def get_value(self, key: str) -> T | None:
        return await self._cache.get(  # pylint:disable=no-member
            key, namespace=self.namespace
        )
