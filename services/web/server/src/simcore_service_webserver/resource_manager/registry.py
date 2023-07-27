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
from typing import TypedDict

import redis.asyncio as aioredis
from aiohttp import web
from models_library.basic_types import UUIDStr

from ..redis import get_redis_resources_client
from ._constants import APP_CLIENT_SOCKET_REGISTRY_KEY

_logger = logging.getLogger(__name__)

ALIVE_SUFFIX = "alive"
RESOURCE_SUFFIX = "resources"


class _RegistryKeyPrefixRequired(TypedDict, total=True):
    user_id: str | int


class RegistryKeyPrefixDict(_RegistryKeyPrefixRequired):
    """Parts of the redis key w/o suffix"""

    client_session_id: str


class ResourcesValueDict(TypedDict, total=False):
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
    def _hash_key(cls, key: RegistryKeyPrefixDict) -> str:
        hash_key: str = ":".join(f"{k}={v}" for k, v in key.items())
        return hash_key

    @classmethod
    def _decode_hash_key(cls, hash_key: str) -> RegistryKeyPrefixDict:
        tmp_key = (
            hash_key[: -len(f":{RESOURCE_SUFFIX}")]
            if hash_key.endswith(f":{RESOURCE_SUFFIX}")
            else hash_key[: -len(f":{ALIVE_SUFFIX}")]
        )
        key = dict(x.split("=") for x in tmp_key.split(":"))
        return RegistryKeyPrefixDict(**key)  # type: ignore

    @property
    def client(self) -> aioredis.Redis:
        client: aioredis.Redis = get_redis_resources_client(self.app)
        return client

    async def set_resource(
        self, key: RegistryKeyPrefixDict, resource: tuple[str, str]
    ) -> None:
        hash_key = f"{self._hash_key(key)}:{RESOURCE_SUFFIX}"
        field, value = resource
        await self.client.hset(hash_key, mapping={field: value})

    async def get_resources(self, key: RegistryKeyPrefixDict) -> ResourcesValueDict:
        hash_key = f"{self._hash_key(key)}:{RESOURCE_SUFFIX}"
        fields = await self.client.hgetall(hash_key)
        return ResourcesValueDict(**fields)  # type: ignore

    async def remove_resource(
        self, key: RegistryKeyPrefixDict, resource_name: str
    ) -> None:
        hash_key = f"{self._hash_key(key)}:{RESOURCE_SUFFIX}"
        await self.client.hdel(hash_key, resource_name)

    async def find_resources(
        self, key: RegistryKeyPrefixDict, resource_name: str
    ) -> list[str]:
        resources: list[str] = []
        # the key might only be partialy complete
        partial_hash_key = f"{self._hash_key(key)}:{RESOURCE_SUFFIX}"
        async for scanned_key in self.client.scan_iter(match=partial_hash_key):
            if await self.client.hexists(scanned_key, resource_name):
                resources.append(await self.client.hget(scanned_key, resource_name))
        return resources

    async def find_keys(self, resource: tuple[str, str]) -> list[RegistryKeyPrefixDict]:
        keys: list[RegistryKeyPrefixDict] = []
        if not resource:
            return keys

        field, value = resource

        async for hash_key in self.client.scan_iter(match=f"*:{RESOURCE_SUFFIX}"):
            if value == await self.client.hget(hash_key, field):
                keys.append(self._decode_hash_key(hash_key))
        return keys

    async def set_key_alive(self, key: RegistryKeyPrefixDict, timeout: int) -> None:
        # setting the timeout to always expire, timeout > 0
        timeout = int(max(1, timeout))
        hash_key = f"{self._hash_key(key)}:{ALIVE_SUFFIX}"
        await self.client.set(hash_key, 1, ex=timeout)

    async def is_key_alive(self, key: RegistryKeyPrefixDict) -> bool:
        hash_key = f"{self._hash_key(key)}:{ALIVE_SUFFIX}"
        return await self.client.exists(hash_key) > 0

    async def remove_key(self, key: RegistryKeyPrefixDict) -> None:
        await self.client.delete(
            f"{self._hash_key(key)}:{RESOURCE_SUFFIX}",
            f"{self._hash_key(key)}:{ALIVE_SUFFIX}",
        )

    async def get_all_resource_keys(
        self,
    ) -> tuple[list[RegistryKeyPrefixDict], list[RegistryKeyPrefixDict]]:
        alive_keys = [
            self._decode_hash_key(hash_key)
            async for hash_key in self.client.scan_iter(match=f"*:{ALIVE_SUFFIX}")
        ]
        dead_keys = [
            self._decode_hash_key(hash_key)
            async for hash_key in self.client.scan_iter(match=f"*:{RESOURCE_SUFFIX}")
            if self._decode_hash_key(hash_key) not in alive_keys
        ]

        return (alive_keys, dead_keys)


def get_registry(app: web.Application) -> RedisResourceRegistry:
    client: RedisResourceRegistry = app[APP_CLIENT_SOCKET_REGISTRY_KEY]
    assert isinstance(client, RedisResourceRegistry)  # nosec
    return client
