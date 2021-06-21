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
from collections import namedtuple
from contextlib import contextmanager
from typing import Dict, Iterator, List, Optional, Union

import attr
from aiohttp import web

from .config import get_service_deletion_timeout
from .registry import get_registry

log = logging.getLogger(__file__)

SOCKET_ID_KEY = "socket_id"
PROJECT_ID_KEY = "project_id"


UserSessionID = namedtuple("UserSessionID", "user_id client_session_id")


@attr.s(auto_attribs=True)
class WebsocketRegistry:
    """
    Keeps track of resources allocated for a user's session

    A session is started when a socket resource is allocated (via set_socket_id)
    A session can allocate multiple resources

    """

    # TODO: find a more descriptive name ... too many registries!
    #

    user_id: int
    client_session_id: Optional[str]
    app: web.Application

    def _resource_key(self) -> Dict[str, str]:
        return {
            "user_id": f"{self.user_id}",
            "client_session_id": self.client_session_id
            if self.client_session_id
            else "*",
        }

    async def set_socket_id(self, socket_id: str) -> None:
        log.debug(
            "user %s/tab %s adding socket %s in registry...",
            self.user_id,
            self.client_session_id,
            socket_id,
        )
        registry = get_registry(self.app)
        await registry.set_resource(self._resource_key(), (SOCKET_ID_KEY, socket_id))
        # NOTE: hearthbeat is not emulated in tests, make sure that with very small GC intervals
        # the resources do not expire; this value is usually in the order of minutes
        timeout = max(3, get_service_deletion_timeout(self.app))
        await registry.set_key_alive(self._resource_key(), timeout)

    async def get_socket_id(self) -> Optional[str]:
        log.debug(
            "user %s/tab %s getting socket from registry...",
            self.user_id,
            self.client_session_id,
        )
        registry = get_registry(self.app)
        resources = await registry.get_resources(self._resource_key())
        return resources.get(SOCKET_ID_KEY, None)

    async def user_pressed_disconnect(self) -> None:
        """When the user disconnects expire as soon as possible the alive key
        to ensure garbage collection will trigger in the next 2 cycles."""
        registry = get_registry(self.app)
        await registry.set_key_alive(self._resource_key(), 1)

    async def remove_socket_id(self) -> None:
        log.debug(
            "user %s/tab %s removing socket from registry...",
            self.user_id,
            self.client_session_id,
        )
        registry = get_registry(self.app)
        await registry.remove_resource(self._resource_key(), SOCKET_ID_KEY)
        await registry.set_key_alive(
            self._resource_key(), get_service_deletion_timeout(self.app)
        )

    async def set_heartbeat(self) -> None:
        """Extends TTL to avoid expiration of all resources under this session"""
        registry = get_registry(self.app)
        await registry.set_key_alive(
            self._resource_key(), get_service_deletion_timeout(self.app)
        )

    async def find_socket_ids(self) -> List[str]:
        log.debug(
            "user %s/tab %s finding %s from registry...",
            self.user_id,
            self.client_session_id,
            SOCKET_ID_KEY,
        )
        registry = get_registry(self.app)
        user_sockets = await registry.find_resources(
            {"user_id": f"{self.user_id}", "client_session_id": "*"}, SOCKET_ID_KEY
        )
        return user_sockets

    async def find(self, key: str) -> List[str]:
        log.debug(
            "user %s/tab %s finding %s from registry...",
            self.user_id,
            self.client_session_id,
            key,
        )
        registry = get_registry(self.app)
        user_resources = await registry.find_resources(self._resource_key(), key)
        return user_resources

    async def add(self, key: str, value: str) -> None:
        log.debug(
            "user %s/tab %s adding %s:%s in registry...",
            self.user_id,
            self.client_session_id,
            key,
            value,
        )
        registry = get_registry(self.app)
        await registry.set_resource(self._resource_key(), (key, value))

    async def remove(self, key: str) -> None:
        log.debug(
            "user %s/tab %s removing %s from registry...",
            self.user_id,
            self.client_session_id,
            key,
        )
        registry = get_registry(self.app)
        await registry.remove_resource(self._resource_key(), key)

    async def find_users_of_resource(self, key: str, value: str) -> List[UserSessionID]:
        log.debug(
            "user %s/tab %s finding %s:%s in registry...",
            self.user_id,
            self.client_session_id,
            key,
            value,
        )
        registry = get_registry(self.app)
        registry_keys = await registry.find_keys((key, value))
        user_session_id_list = [
            (int(x["user_id"]), x["client_session_id"]) for x in registry_keys
        ]
        return user_session_id_list


@contextmanager
def managed_resource(
    user_id: Union[str, int], client_session_id: Optional[str], app: web.Application
) -> Iterator[WebsocketRegistry]:
    try:
        registry = WebsocketRegistry(int(user_id), client_session_id, app)
        yield registry
    except Exception:
        log.exception(
            "Error in web-socket for user:%s, session:%s", user_id, client_session_id
        )
        raise

    # TODO: PC->SAN?? exception handling? e.g. remove resource from registry?
