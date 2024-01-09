from typing import Generic, TypeVar

from aiocache import Cache
from aiocache.serializers import PickleSerializer
from fastapi import FastAPI
from pydantic import NonNegativeFloat
from settings_library.redis import RedisDatabase

from ...core.settings import ApplicationSettings

T = TypeVar("T")


class ServiceStatusCache(Generic[T]):
    def __init__(self, app: FastAPI, *, ttl: NonNegativeFloat, namespace: str) -> None:
        settings: ApplicationSettings = app.state.settings

        self.cache = Cache.from_url(
            settings.DYNAMIC_SCHEDULER_REDIS.build_redis_dsn(
                RedisDatabase.DISTRIBUTED_CACHES
            )
        )
        self.cache.serializer = PickleSerializer()
        self.cache.namespace = namespace
        self.cache.ttl = ttl

    async def set_value(self, key: str, value: T) -> None:
        await self.cache.set(key, value)  # pylint:disable=no-member

    async def get_value(self, key: str) -> T | None:
        result: T | None = await self.cache.get(key)  # pylint:disable=no-member
        return result

    async def clear(self) -> None:
        await self.cache.clear()  # pylint:disable=no-member
