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
from dataclasses import dataclass
from typing import Iterator

from aiohttp import web
from servicelib.logging_utils import get_log_record_extra, log_context

from .registry import RegistryKeyPrefixDict, ResourcesValueDict, get_registry
from .settings import ResourceManagerSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


SOCKET_ID_KEY = "socket_id"
PROJECT_ID_KEY = "project_id"

assert SOCKET_ID_KEY in ResourcesValueDict.__annotations__.keys()  # nosec
assert PROJECT_ID_KEY in ResourcesValueDict.__annotations__.keys()  # nosec


def get_service_deletion_timeout(app: web.Application) -> int:
    settings: ResourceManagerSettings = get_plugin_settings(app)
    return settings.RESOURCE_MANAGER_RESOURCE_TTL_S


@dataclass(order=True, frozen=True)
class UserSessionID:
    user_id: int
    client_session_id: str


@dataclass
class WebsocketRegistry:
    """
    Keeps track of resources allocated for a user's session

    A session is started when a socket resource is allocated (via set_socket_id)
    A session can allocate multiple resources

    """

    # TODO: find a more descriptive name ... too many registries!
    #

    user_id: int
    client_session_id: str | None
    app: web.Application

    def _resource_key(self) -> RegistryKeyPrefixDict:
        return RegistryKeyPrefixDict(
            user_id=f"{self.user_id}",
            client_session_id=self.client_session_id or "*",
        )

    async def set_socket_id(self, socket_id: str) -> None:
        _logger.debug(
            "user %s/tab %s adding socket %s in registry...",
            self.user_id,
            self.client_session_id,
            socket_id,
            extra=get_log_record_extra(user_id=self.user_id),
        )
        registry = get_registry(self.app)
        await registry.set_resource(self._resource_key(), (SOCKET_ID_KEY, socket_id))
        # NOTE: hearthbeat is not emulated in tests, make sure that with very small GC intervals
        # the resources do not expire; this value is usually in the order of minutes
        timeout = max(3, get_service_deletion_timeout(self.app))
        await registry.set_key_alive(self._resource_key(), timeout)

    async def get_socket_id(self) -> str | None:
        _logger.debug(
            "user %s/tab %s getting socket from registry...",
            self.user_id,
            self.client_session_id,
        )
        registry = get_registry(self.app)
        resources = await registry.get_resources(self._resource_key())
        key: str | None = resources.get("socket_id", None)
        return key

    async def user_pressed_disconnect(self) -> None:
        """When the user disconnects expire as soon as possible the alive key
        to ensure garbage collection will trigger in the next 2 cycles."""
        registry = get_registry(self.app)
        await registry.set_key_alive(self._resource_key(), 1)

    async def remove_socket_id(self) -> None:
        _logger.debug(
            "user %s/tab %s removing socket from registry...",
            self.user_id,
            self.client_session_id,
            extra=get_log_record_extra(user_id=self.user_id),
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

    async def find_socket_ids(self) -> list[str]:
        _logger.debug(
            "user %s/tab %s finding %s from registry...",
            self.user_id,
            self.client_session_id,
            SOCKET_ID_KEY,
            extra=get_log_record_extra(user_id=self.user_id),
        )
        registry = get_registry(self.app)
        user_sockets = await registry.find_resources(
            {"user_id": f"{self.user_id}", "client_session_id": "*"}, SOCKET_ID_KEY
        )
        return user_sockets

    async def find_all_resources_of_user(self, key: str) -> list[str]:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"{self.user_id=} finding all {key} from registry",
            extra=get_log_record_extra(user_id=self.user_id),
        ):
            resources = await get_registry(self.app).find_resources(
                {"user_id": f"{self.user_id}", "client_session_id": "*"}, key
            )
            return resources

    async def find(self, key: str) -> list[str]:
        _logger.debug(
            "user %s/tab %s finding %s from registry...",
            self.user_id,
            self.client_session_id,
            key,
            extra=get_log_record_extra(user_id=self.user_id),
        )
        registry = get_registry(self.app)
        user_resources = await registry.find_resources(self._resource_key(), key)
        return user_resources

    async def add(self, key: str, value: str) -> None:
        _logger.debug(
            "user %s/tab %s adding %s:%s in registry...",
            self.user_id,
            self.client_session_id,
            key,
            value,
            extra=get_log_record_extra(user_id=self.user_id),
        )
        registry = get_registry(self.app)
        await registry.set_resource(self._resource_key(), (key, value))

    async def remove(self, key: str) -> None:
        _logger.debug(
            "user %s/tab %s removing %s from registry...",
            self.user_id,
            self.client_session_id,
            key,
            extra=get_log_record_extra(user_id=self.user_id),
        )
        registry = get_registry(self.app)
        await registry.remove_resource(self._resource_key(), key)

    async def find_users_of_resource(self, key: str, value: str) -> list[UserSessionID]:
        _logger.debug(
            "user %s/tab %s finding %s:%s in registry...",
            self.user_id,
            self.client_session_id,
            key,
            value,
            extra=get_log_record_extra(user_id=self.user_id),
        )
        registry = get_registry(self.app)
        registry_keys = await registry.find_keys((key, value))
        user_session_id_list = [
            UserSessionID(int(x["user_id"]), x["client_session_id"])
            for x in registry_keys
        ]
        return user_session_id_list


@contextmanager
def managed_resource(
    user_id: str | int, client_session_id: str | None, app: web.Application
) -> Iterator[WebsocketRegistry]:
    try:
        registry = WebsocketRegistry(int(user_id), client_session_id, app)
        yield registry
    except Exception:
        _logger.exception(
            "Error in web-socket for user:%s, session:%s",
            user_id,
            client_session_id,
            extra=get_log_record_extra(user_id=user_id),
        )
        raise

    # TODO: PC->SAN?? exception handling? e.g. remove resource from registry?
