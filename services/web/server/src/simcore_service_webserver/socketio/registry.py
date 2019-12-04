""" registry containing data about how a user is connected.

    there is one websocket per opened tab in a browser. 
    {
        user_id: { # identifies the user
            tab_id: { # identifies the browser tab
                server_id: identifies which server serves the socket,
                socket_id: identifies the socket on the server,
                project_id: identifies the project opened in the tab
            }
        }
    }
    
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import attr
from aiohttp import web

from .config import get_redis_client

log = logging.getLogger(__name__)



@attr.s(auto_attribs=True)
class AbstractSocketRegistry(ABC):
    app: web.Application
    def __init__(self, app: web.Application):
        self.app = app
        super().__init__()

    @abstractmethod
    async def add_socket(self, user_id: str, tab_id: str, socket_id: str) -> int:
        pass

    @abstractmethod
    async def remove_socket(self, socket_id: str) -> Optional[int]:
        pass

    @abstractmethod
    async def find_sockets(self, user_id: str) -> List[str]:
        pass

    @abstractmethod
    async def find_owner(self, socket_id: str) -> Optional[str]:
        pass




REDIS_HASH_KEY:str = "user_id_{user_id}:tab_id_{tab_id}"
REDIS_HASH_KEY_ALL_USERS:str = "user_id_*:tab_id_{tab_id}"
REDIS_HASH_KEY_ALL_TABS:str = "user_id_{user_id}:tab_id_*"
REDIS_HASH_KEY_ALL:str = "user_id_*:tab_id_*"

@attr.s(auto_attribs=True)
class RedisUserSocketRegistry(AbstractSocketRegistry):
    """ Keeps a record of connected sockets per user

        redis structure is following
        Redis Hash: key=user_id:tab_id values={server_id socket_id project_id}
    """
    async def add_socket(self, user_id: str, tab_id: str, socket_id: str) -> int:
        client = get_redis_client(self.app)
        key = REDIS_HASH_KEY.format(user_id=user_id, tab_id=tab_id)
        await client.hmset_dict(key, user_id=user_id, tab_id=tab_id, server=id(__name__), socket_id=socket_id)
        # number of sockets is equal to number of tabs
        return len(await client.keys(REDIS_HASH_KEY_ALL_TABS.format(user_id=user_id)))

    async def remove_socket(self, socket_id: str) -> Optional[int]:
        client = get_redis_client(self.app)
        async for key in client.iscan(match=REDIS_HASH_KEY_ALL):
            if socket_id in await client.hget(key, "socket_id"):
                user_id = await client.hget(key, "user_id")
                await client.delete(key)
                return len(await client.keys(REDIS_HASH_KEY_ALL_TABS.format(user_id=user_id)))
            
        return None


    async def find_sockets(self, user_id: str) -> List[str]:
        client = get_redis_client(self.app)
        socket_ids = []
        async for key in client.iscan(match=REDIS_HASH_KEY_ALL_TABS.format(user_id=user_id)):
            socket_ids.append(await client.hget(key, "socket_id"))
        return socket_ids

    async def find_owner(self, socket_id: str) -> Optional[str]:
        client = get_redis_client(self.app)
        async for key in client.iscan(match=REDIS_HASH_KEY_ALL):
            if socket_id in await client.hget(key, "socket_id"):
                user_id = await client.hget(key, "user_id")
                return user_id
        return None

@attr.s(auto_attribs=True)
class InMemoryUserSocketRegistry(AbstractSocketRegistry):
    """ Keeps a record of connect sockets
    {
        user_id: { # identifies the user
            tab_id: { # identifies the browser tab
                server_id: identifies which server serves the socket,
                socket_id: identifies the socket on the server,
                project_id: identifies the project opened in the tab
            }
        }
    }
    """
    # pylint: disable=unsubscriptable-object
    # pylint: disable=no-member
    user_to_tabs_map: Dict = {}

    async def add_socket(self, user_id: str, tab_id: str, socket_id: str) -> int:
        if user_id not in self.user_to_tabs_map:
            self.user_to_tabs_map[user_id] = {}

        self.user_to_tabs_map[user_id].update({
            tab_id: {
                "server_id": id(__name__),
                "socket_id": socket_id,
                "project_id": None
            }
        })
        log.debug("user %s is connected with following tabs: %s", user_id, self.user_to_tabs_map[user_id])
        return len(self.user_to_tabs_map[user_id])

    async def remove_socket(self, socket_id: str) -> Optional[int]:
        for user_id, tabs in self.user_to_tabs_map.items():            
            for tab_id, tab_props in tabs.items():
                if socket_id in tab_props["socket_id"]:
                    del tabs[tab_id]                    
                    log.debug("user %s disconnected socket %s", user_id, socket_id)
                    return len(self.user_to_tabs_map[user_id])
        return None

    async def find_sockets(self, user_id: str) -> List[str]:
        if user_id not in self.user_to_tabs_map:
            return []
        tabs = self.user_to_tabs_map[user_id]
        list_sockets = [tab_props["socket_id"] for _tab_id, tab_props in tabs.items()]
        return list_sockets

    async def find_owner(self, socket_id: str) -> Optional[str]:
        for user_id, tabs in self.user_to_tabs_map.items():
            for _tab_id, tab_props in tabs.items():
                if socket_id in tab_props["socket_id"]:
                    return user_id
        return None
