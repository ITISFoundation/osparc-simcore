""" InMemory registry of connecting socket IDs to user IDs.
This is not usable when scaling the webserver. Prefer a DB-based version
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

import attr
from aiohttp import web

from .config import get_redis_client

log = logging.getLogger(__name__)

def _default_dict_factory():
    return defaultdict(list)
@attr.s(auto_attribs=True)
class RedisUserSocketRegistry:
    """ Keeps a record of connected sockets per user
    """
    app: web.Application

    def __init__(self, app: web.Application):
        super().__init__()
        self.app = app

    async def add_socket(self, user_id: str, socket_id: str) -> int:
        client = get_redis_client(self.app)
        await client.sadd(f"user_id:{user_id}", socket_id)
        return await client.scard(f"user_id:{user_id}")

    async def remove_socket(self, socket_id: str) -> Optional[int]:
        client = get_redis_client(self.app)
        async for key in client.iscan(match="user_id:*"):
            if await client.sismember(key, socket_id):
                await client.srem(key, socket_id)
                return await client.scard(key)
        return None


    async def find_sockets(self, user_id: str) -> List[str]:
        client = get_redis_client(self.app)
        socket_ids = await client.smembers(f"user_id:{user_id}")
        return list(socket_ids)

    async def find_owner(self, socket_id: str) -> Optional[str]:
        client = get_redis_client(self.app)
        async for key in client.iscan(match="user_id:*"):
            if await client.sismember(key, socket_id):
                user_id = key.split(":")[1]
                return user_id

        return None

@attr.s(auto_attribs=True)
class InMemoryUserSocketRegistry:
    """ Keeps a record of connect sockets
    """
    # pylint: disable=unsubscriptable-object
    # pylint: disable=no-member
    user_to_sockets_map: Dict = attr.Factory(_default_dict_factory)

    async def add_socket(self, user_id: str, socket_id: str) -> int:
        if socket_id not in self.user_to_sockets_map[user_id]:
            self.user_to_sockets_map[user_id].append(socket_id)
            log.debug("user %s is connected with sockets: %s", user_id, self.user_to_sockets_map[user_id])
        return len(self.user_to_sockets_map[user_id])

    async def remove_socket(self, socket_id: str) -> Optional[int]:
        for user_id, socket_ids in self.user_to_sockets_map.items():
            if socket_id in socket_ids:
                socket_ids.remove(socket_id)
                log.debug("user %s disconnected socket %s", user_id, socket_id)
                return len(socket_ids)
        return None

    async def find_sockets(self, user_id: str) -> List[str]:
        return self.user_to_sockets_map[user_id]

    async def find_owner(self, socket_id: str) -> Optional[str]:
        for user_id, socket_ids in self.user_to_sockets_map.items():
            if socket_id in socket_ids:
                return user_id
        return None
