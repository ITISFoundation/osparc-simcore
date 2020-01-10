""" wrapper around redis registry containing data about:
    - user_id - socket_it - client_session_id relation
    - which resources a specific user/socket/client has opened

    there is one websocket per opened tab in a browser.
    {
        user_id: { # identifies the user
            client_session_id: { # identifies the browser tab
                socket_id: identifies the socket on the server,
                project_id: identifies the project opened in the tab
            }
        }
    }

"""

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
    client_session_id: str
    app: web.Application

    def _resource_key(self) -> Dict[str,str]:
        return {
            "user_id": self.user_id,
            "client_session_id": self.client_session_id if self.client_session_id else "*"
            }

    async def set_socket_id(self, socket_id: str) -> None:
        log.debug("user %s/tab %s adding socket %s in registry...", self.user_id, self.client_session_id, socket_id)
        registry = get_registry(self.app)
        await registry.set_resource(self._resource_key(), (SOCKET_ID_KEY, socket_id))
        await registry.set_key_alive(self._resource_key(), True)

    async def remove_socket_id(self) -> None:
        log.debug("user %s/tab %s removing socket from registry...", self.user_id, self.client_session_id)
        registry = get_registry(self.app)
        await registry.remove_resource(self._resource_key(), SOCKET_ID_KEY)
        await registry.set_key_alive(self._resource_key(), False, get_service_deletion_timeout(self.app))

    async def find_socket_ids(self) -> List[str]:
        log.debug("user %s/tab %s finding %s from registry...", self.user_id, self.client_session_id, SOCKET_ID_KEY)
        registry = get_registry(self.app)
        user_sockets = await registry.find_resources({"user_id": self.user_id, "client_session_id": "*"}, SOCKET_ID_KEY)
        return user_sockets

    async def find(self, key: str) -> List[str]:
        log.debug("user %s/tab %s finding %s from registry...", self.user_id, self.client_session_id, key)
        registry = get_registry(self.app)
        user_resources = await registry.find_resources(self._resource_key(), key)
        return user_resources

    async def add(self, key: str, value: str) -> None:
        log.debug("user %s/tab %s adding %s:%s in registry...", self.user_id, self.client_session_id, key, value)
        registry = get_registry(self.app)
        await registry.set_resource(self._resource_key(), (key,value))

    async def remove(self, key: str) -> None:
        log.debug("user %s/tab %s removing %s from registry...", self.user_id, self.client_session_id, key)
        registry = get_registry(self.app)
        await registry.remove_resource(self._resource_key(), key)

    async def find_users_of_resource(self, key: str, value: str) -> List[str]:
        log.debug("user %s/tab %s finding %s:%s in registry..." ,self.user_id, self.client_session_id, key, value)
        registry = get_registry(self.app)
        registry_keys = await registry.find_keys((key, value))
        users = list({x["user_id"] for x in registry_keys})
        return users

@contextmanager
def managed_resource(user_id: str, client_session_id: str, app: web.Application) -> WebsocketRegistry:
    registry = WebsocketRegistry(user_id, client_session_id, app)
    yield registry
