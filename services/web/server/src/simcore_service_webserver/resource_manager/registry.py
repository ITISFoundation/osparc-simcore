""" Wrapper around a Redis-backed registry for storing resources in a hash (https://redis.io/topics/data-types).

    Redis stores key/values.

    key hashes are generated from a dictionary (e.g. {"user_id":"a_user_id, "some_other_id":123} will
    create a hash named "user_id=a_user_id:some_other_id=123:resources")
    resources are tuples (resource_name, resource_value) that are stored with a key as Redis fields.
    A same key can have a lot of fields provided they have a different name.

    A key can be set as "alive". This creates a secondary key (e.g. "user_id=a_user_id:some_other_id=123:alive").
    This key can have a timeout value. When the key times out then the key disappears from Redis automatically.


"""

import logging

import redis.asyncio as aioredis
from aiohttp import web
from models_library.basic_types import UUIDStr
from servicelib.redis_utils import handle_redis_returns_union_types
from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)

from ..redis import get_redis_resources_client
from ._constants import APP_CLIENT_SOCKET_REGISTRY_KEY

_logger = logging.getLogger(__name__)

# redis `resources` db has composed-keys formatted as '${user_id=}:${client_session_id=}:{suffix}'
#    Example:
#        Key: user_id=1:client_session_id=7f40353b-db02-4474-a44d-23ce6a6e428c:alive = 1
#        Key: user_id=1:client_session_id=7f40353b-db02-4474-a44d-23ce6a6e428c:resources = {project_id: ... , socket_id: ...}
#
_ALIVE_SUFFIX = "alive"  # points to a string type
_RESOURCE_SUFFIX = "resources"  # points to a hash (like a dict) type


class _UserRequired(TypedDict, total=True):
    user_id: str | int


class UserSessionDict(_UserRequired):
    """Parts of the key used in redis for a user-session"""

    client_session_id: str


class ResourcesDict(TypedDict, total=False):
    """Field-value pairs of {user_id}:{client_session_id}:resources key"""

    project_id: UUIDStr
    socket_id: str


class RedisResourceRegistry:
    """Keeps a record of connected sockets per user

    redis structure is following
    Redis Hash: key=user_id:client_session_id values={server_id socket_id project_id}

    Example:
        Key: user_id=1:client_session_id=7f40353b-db02-4474-a44d-23ce6a6e428c:alive = 1
        Key: user_id=1:client_session_id=7f40353b-db02-4474-a44d-23ce6a6e428c:resources = {project_id: ... , socket_id: ...}
    """

    def __init__(self, app: web.Application):
        self._app = app

    @property
    def app(self) -> web.Application:
        return self._app

    @classmethod
    def _hash_key(cls, key: UserSessionDict) -> str:
        hash_key: str = ":".join(f"{k}={v}" for k, v in key.items())
        return hash_key

    @classmethod
    def _decode_hash_key(cls, hash_key: str) -> UserSessionDict:
        tmp_key = (
            hash_key[: -len(f":{_RESOURCE_SUFFIX}")]
            if hash_key.endswith(f":{_RESOURCE_SUFFIX}")
            else hash_key[: -len(f":{_ALIVE_SUFFIX}")]
        )
        key = dict(x.split("=") for x in tmp_key.split(":"))
        return UserSessionDict(**key)  # type: ignore

    @property
    def client(self) -> aioredis.Redis:
        client: aioredis.Redis = get_redis_resources_client(self.app)
        return client

    async def set_resource(
        self, key: UserSessionDict, resource: tuple[str, str]
    ) -> None:
        hash_key = f"{self._hash_key(key)}:{_RESOURCE_SUFFIX}"
        field, value = resource
        await handle_redis_returns_union_types(
            self.client.hset(hash_key, mapping={field: value})
        )

    async def get_resources(self, key: UserSessionDict) -> ResourcesDict:
        hash_key = f"{self._hash_key(key)}:{_RESOURCE_SUFFIX}"
        fields = await handle_redis_returns_union_types(self.client.hgetall(hash_key))
        return ResourcesDict(**fields)

    async def remove_resource(self, key: UserSessionDict, resource_name: str) -> None:
        hash_key = f"{self._hash_key(key)}:{_RESOURCE_SUFFIX}"
        await handle_redis_returns_union_types(
            self.client.hdel(hash_key, resource_name)
        )

    async def find_resources(
        self, key: UserSessionDict, resource_name: str
    ) -> list[str]:
        resources: list[str] = []
        # the key might only be partialy complete
        partial_hash_key = f"{self._hash_key(key)}:{_RESOURCE_SUFFIX}"
        async for scanned_key in self.client.scan_iter(match=partial_hash_key):
            if await handle_redis_returns_union_types(
                self.client.hexists(scanned_key, resource_name)
            ):
                key_value = await handle_redis_returns_union_types(
                    self.client.hget(scanned_key, resource_name)
                )
                if key_value is not None:
                    resources.append(key_value)
        return resources

    async def find_keys(self, resource: tuple[str, str]) -> list[UserSessionDict]:
        if not resource:
            return []

        field, value = resource
        return [
            self._decode_hash_key(hash_key)
            async for hash_key in self.client.scan_iter(match=f"*:{_RESOURCE_SUFFIX}")
            if value
            == await handle_redis_returns_union_types(self.client.hget(hash_key, field))
        ]

    async def set_key_alive(self, key: UserSessionDict, timeout: int) -> None:
        # setting the timeout to always expire, timeout > 0
        timeout = int(max(1, timeout))
        hash_key = f"{self._hash_key(key)}:{_ALIVE_SUFFIX}"
        await self.client.set(hash_key, 1, ex=timeout)

    async def is_key_alive(self, key: UserSessionDict) -> bool:
        hash_key = f"{self._hash_key(key)}:{_ALIVE_SUFFIX}"
        return bool(await self.client.exists(hash_key) > 0)

    async def remove_key(self, key: UserSessionDict) -> None:
        await self.client.delete(
            f"{self._hash_key(key)}:{_RESOURCE_SUFFIX}",
            f"{self._hash_key(key)}:{_ALIVE_SUFFIX}",
        )

    async def get_all_resource_keys(
        self,
    ) -> tuple[list[UserSessionDict], list[UserSessionDict]]:
        alive_keys = [
            self._decode_hash_key(hash_key)
            async for hash_key in self.client.scan_iter(match=f"*:{_ALIVE_SUFFIX}")
        ]
        dead_keys = [
            self._decode_hash_key(hash_key)
            async for hash_key in self.client.scan_iter(match=f"*:{_RESOURCE_SUFFIX}")
            if self._decode_hash_key(hash_key) not in alive_keys
        ]

        return (alive_keys, dead_keys)


def get_registry(app: web.Application) -> RedisResourceRegistry:
    client: RedisResourceRegistry = app[APP_CLIENT_SOCKET_REGISTRY_KEY]
    assert isinstance(client, RedisResourceRegistry)  # nosec
    return client
