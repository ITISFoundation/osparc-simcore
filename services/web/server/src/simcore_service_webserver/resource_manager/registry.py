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
from typing import Dict, List, Tuple

import aioredis
import attr
from aiohttp import web

from .config import APP_CLIENT_SOCKET_REGISTRY_KEY
from .redis import get_redis_client

log = logging.getLogger(__name__)

RESOURCE_SUFFIX = "resources"
ALIVE_SUFFIX = "alive"


@attr.s(auto_attribs=True)
class RedisResourceRegistry:
    """Keeps a record of connected sockets per user

    redis structure is following
    Redis Hash: key=user_id:client_session_id values={server_id socket_id project_id}
    """

    app: web.Application

    @classmethod
    def _hash_key(cls, key: Dict[str, str]) -> str:
        hash_key = ":".join(f"{item[0]}={item[1]}" for item in key.items())
        return hash_key

    @classmethod
    def _decode_hash_key(cls, hash_key: str) -> Dict[str, str]:
        tmp_key = (
            hash_key[: -len(f":{RESOURCE_SUFFIX}")]
            if hash_key.endswith(f":{RESOURCE_SUFFIX}")
            else hash_key[: -len(f":{ALIVE_SUFFIX}")]
        )
        key = dict(x.split("=") for x in tmp_key.split(":"))
        return key

    @property
    def client(self) -> aioredis.Redis:
        return get_redis_client(self.app)

    async def set_resource(
        self, key: Dict[str, str], resource: Tuple[str, str]
    ) -> None:
        hash_key = f"{self._hash_key(key)}:{RESOURCE_SUFFIX}"
        field, value = resource
        await self.client.hmset_dict(hash_key, **{field: value})

    async def get_resources(self, key: Dict[str, str]) -> Dict[str, str]:
        hash_key = f"{self._hash_key(key)}:{RESOURCE_SUFFIX}"
        return await self.client.hgetall(hash_key)

    async def remove_resource(self, key: Dict[str, str], resource_name: str) -> None:
        hash_key = f"{self._hash_key(key)}:{RESOURCE_SUFFIX}"
        await self.client.hdel(hash_key, resource_name)

    async def find_resources(
        self, key: Dict[str, str], resource_name: str
    ) -> List[str]:
        resources = []
        # the key might only be partialy complete
        partial_hash_key = f"{self._hash_key(key)}:{RESOURCE_SUFFIX}"
        async for key in self.client.iscan(match=partial_hash_key):
            if await self.client.hexists(key, resource_name):
                resources.append(await self.client.hget(key, resource_name))
        return resources

    async def find_keys(self, resource: Tuple[str, str]) -> List[Dict[str, str]]:
        keys = []
        if not resource:
            return keys

        field, value = resource

        async for hash_key in self.client.iscan(match=f"*:{RESOURCE_SUFFIX}"):
            if value == await self.client.hget(hash_key, field):
                keys.append(self._decode_hash_key(hash_key))
        return keys

    async def set_key_alive(self, key: Dict[str, str], timeout: int) -> None:
        # setting the timeout to always expire, timeout > 0
        timeout = int(max(1, timeout))
        hash_key = f"{self._hash_key(key)}:{ALIVE_SUFFIX}"
        await self.client.set(hash_key, 1, expire=timeout)

    async def is_key_alive(self, key: Dict[str, str]) -> bool:
        hash_key = f"{self._hash_key(key)}:{ALIVE_SUFFIX}"
        return await self.client.exists(hash_key) > 0

    async def remove_key(self, key: Dict[str, str]) -> None:
        await self.client.delete(
            f"{self._hash_key(key)}:{RESOURCE_SUFFIX}",
            f"{self._hash_key(key)}:{ALIVE_SUFFIX}",
        )

    async def get_all_resource_keys(
        self,
    ) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        alive_keys = [
            self._decode_hash_key(hash_key)
            async for hash_key in self.client.iscan(match=f"*:{ALIVE_SUFFIX}")
        ]
        dead_keys = [
            self._decode_hash_key(hash_key)
            async for hash_key in self.client.iscan(match=f"*:{RESOURCE_SUFFIX}")
            if self._decode_hash_key(hash_key) not in alive_keys
        ]

        return (alive_keys, dead_keys)


def get_registry(app: web.Application) -> RedisResourceRegistry:
    return app[APP_CLIENT_SOCKET_REGISTRY_KEY]
