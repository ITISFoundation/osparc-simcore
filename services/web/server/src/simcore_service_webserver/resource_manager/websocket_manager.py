import logging
from contextlib import contextmanager
from typing import Dict, List

import attr
from aiohttp import web

from .config import get_service_deletion_timeout
from .registry import get_registry

log = logging.getLogger(__file__)

SOCKET_ID_KEY = "socket_id"

@attr.s(auto_attribs=True)
class WebsocketRegistry:
    user_id: str
    tab_id: str
    app: web.Application

    def _resource_key(self) -> Dict[str,str]:
        return {
            "user_id": self.user_id,
            "tab_id": self.tab_id
            }

    async def set_socket_id(self, socket_id: str) -> None:
        log.debug("user %s/tab %s adding socket %s in registry...", self.user_id, self.tab_id, socket_id)
        registry = get_registry(self.app)
        await registry.set_resource(self._resource_key(), (SOCKET_ID_KEY, socket_id))
        await registry.set_key_alive(self._resource_key(), True)
    
    async def remove_socket_id(self) -> None:
        log.debug("user %s/tab %s removing socket from registry...", self.user_id, self.tab_id)
        registry = get_registry(self.app)
        await registry.remove_resource(self._resource_key(), SOCKET_ID_KEY)
        await registry.set_key_alive(self._resource_key(), False, get_service_deletion_timeout(self.app))

    async def find_socket_ids(self) -> List[str]:
        log.debug("user %s/tab %s finding sockets from registry...", self.user_id, self.tab_id)
        registry = get_registry(self.app)
        user_sockets = await registry.find_resources({"user_id": self.user_id}, SOCKET_ID_KEY)
        return user_sockets

    async def add(self, key: str, value: str) -> None:
        log.debug("user %s/tab %s adding %s:%s in registry...", self.user_id, self.tab_id, key, value)
        registry = get_registry(self.app)
        await registry.set_resource(self._resource_key(), (key,value))        

    async def remove(self, key: str) -> None:
        log.debug("user %s/tab %s removing %s from registry...", self.user_id, self.tab_id, key)
        registry = get_registry(self.app)
        await registry.remove_resource(self._resource_key(), key)

@contextmanager
def managed_resource(user_id: str, tab_id: str, app: web.Application) -> WebsocketRegistry:
    registry = WebsocketRegistry(user_id, tab_id, app)
    yield registry
