import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final

from aiohttp import web
from models_library.users import UserID
from servicelib.logging_utils import get_log_record_extra, log_context

from .models import ResourcesDict, UserSession
from .registry import (
    RedisResourceRegistry,
    get_registry,
)
from .settings import ResourceManagerSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


_SOCKET_ID_FIELDNAME: Final[str] = "socket_id"
PROJECT_ID_KEY: Final[str] = "project_id"

assert _SOCKET_ID_FIELDNAME in ResourcesDict.__annotations__  # nosec
assert PROJECT_ID_KEY in ResourcesDict.__annotations__  # nosec


def _get_service_deletion_timeout(app: web.Application) -> int:
    settings: ResourceManagerSettings = get_plugin_settings(app)
    return settings.RESOURCE_MANAGER_RESOURCE_TTL_S


@dataclass
class UserSessionResourcesRegistry:
    """
    Keeps track of resources allocated for a user's session

    A session is started when a socket resource is allocated (via set_socket_id)
    A session can allocate multiple resources

    Implements a wrapper around redis registry (self._registry) containing data about:
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

    user_id: UserID
    client_session_id: str | None  # Every tab that a user opens
    app: web.Application

    @property
    def _registry(self) -> RedisResourceRegistry:
        return get_registry(self.app)

    def _resource_key(self) -> UserSession:
        return UserSession(
            user_id=self.user_id,
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

        await self._registry.set_resource(
            self._resource_key(), (_SOCKET_ID_FIELDNAME, socket_id)
        )
        # NOTE: hearthbeat is not emulated in tests, make sure that with very small GC intervals
        # the resources do not expire; this value is usually in the order of minutes
        timeout = max(3, _get_service_deletion_timeout(self.app))
        await self._registry.set_key_alive(
            self._resource_key(), expiration_time=timeout
        )

    async def get_socket_id(self) -> str | None:
        _logger.debug(
            "user %s/tab %s getting socket from registry...",
            self.user_id,
            self.client_session_id,
        )

        resources = await self._registry.get_resources(self._resource_key())
        key: str | None = resources.get("socket_id", None)
        return key

    async def user_pressed_disconnect(self) -> None:
        """When the user disconnects expire as soon as possible the alive key
        to ensure garbage collection will trigger in the next 2 cycles."""

        await self._registry.set_key_alive(self._resource_key(), expiration_time=1)

    async def remove_socket_id(self) -> None:
        _logger.debug(
            "user %s/tab %s removing socket from registry...",
            self.user_id,
            self.client_session_id,
            extra=get_log_record_extra(user_id=self.user_id),
        )

        await self._registry.remove_resource(self._resource_key(), _SOCKET_ID_FIELDNAME)
        await self._registry.set_key_alive(
            self._resource_key(),
            expiration_time=_get_service_deletion_timeout(self.app),
        )

    async def set_heartbeat(self) -> None:
        """Extends TTL to avoid expiration of all resources under this session"""

        await self._registry.set_key_alive(
            self._resource_key(),
            expiration_time=_get_service_deletion_timeout(self.app),
        )

    async def find_socket_ids(self) -> list[str]:
        _logger.debug(
            "user %s/tab %s finding %s from registry...",
            self.user_id,
            self.client_session_id,
            _SOCKET_ID_FIELDNAME,
            extra=get_log_record_extra(user_id=self.user_id),
        )

        return await self._registry.find_resources(
            UserSession(user_id=self.user_id, client_session_id="*"),
            _SOCKET_ID_FIELDNAME,
        )

    async def find_all_resources_of_user(self, key: str) -> list[str]:
        with log_context(
            _logger,
            logging.DEBUG,
            msg=f"{self.user_id=} finding all {key} from registry",
            extra=get_log_record_extra(user_id=self.user_id),
        ):
            return await get_registry(self.app).find_resources(
                UserSession(user_id=self.user_id, client_session_id="*"), key
            )

    async def find(self, resource_name: str) -> list[str]:
        _logger.debug(
            "user %s/tab %s finding %s from registry...",
            self.user_id,
            self.client_session_id,
            resource_name,
            extra=get_log_record_extra(user_id=self.user_id),
        )

        return await self._registry.find_resources(self._resource_key(), resource_name)

    async def add(self, key: str, value: str) -> None:
        _logger.debug(
            "user %s/tab %s adding %s:%s in registry...",
            self.user_id,
            self.client_session_id,
            key,
            value,
            extra=get_log_record_extra(user_id=self.user_id),
        )

        await self._registry.set_resource(self._resource_key(), (key, value))

    async def remove(self, key: str) -> None:
        _logger.debug(
            "user %s/tab %s removing %s from registry...",
            self.user_id,
            self.client_session_id,
            key,
            extra=get_log_record_extra(user_id=self.user_id),
        )

        await self._registry.remove_resource(self._resource_key(), key)

    @staticmethod
    async def find_users_of_resource(
        app: web.Application, key: str, value: str
    ) -> list[UserSession]:
        registry = get_registry(app)
        return await registry.find_keys(resource=(key, value))

    def get_id(self) -> UserSession:
        if self.client_session_id is None:
            msg = f"Cannot build UserSessionID with missing {self.client_session_id=}"
            raise ValueError(msg)
        return UserSession(
            user_id=self.user_id, client_session_id=self.client_session_id
        )


@contextmanager
def managed_resource(
    user_id: UserID, client_session_id: str | None, app: web.Application
) -> Iterator[UserSessionResourcesRegistry]:
    try:
        registry = UserSessionResourcesRegistry(user_id, client_session_id, app)
        yield registry
    except Exception:
        _logger.debug(
            "Error in web-socket for user:%s, session:%s",
            user_id,
            client_session_id,
            extra=get_log_record_extra(user_id=user_id),
        )
        raise
