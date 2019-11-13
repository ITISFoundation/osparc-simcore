""" InMemory registry of connecting socket IDs to user IDs.
This is not usable when scaling the webserver. Prefer a DB-based version
"""

import logging
from collections import defaultdict
from typing import Dict, List, Optional

import attr

log = logging.getLogger(__name__)

def _default_dict_factory():
    return defaultdict(list)


@attr.s(auto_attribs=True)
class InMemoryUserSocketRegistry:
    """ Keeps a record of connect sockets
    """
    user_to_sockets_map: Dict = attr.Factory(_default_dict_factory)

    def add_socket(self, user_id: str, socket_id: str) -> int:
        if socket_id not in self.user_to_sockets_map[user_id]:
            self.user_to_sockets_map[user_id].append(socket_id)
            log.debug("user %s is connected with sockets: %s", user_id, self.user_to_sockets_map[user_id])
        return len(self.user_to_sockets_map[user_id])

    def remove_socket(self, socket_id: str):
        for user_id, socket_ids in self.user_to_sockets_map.items():
            if socket_id in socket_ids:
                socket_ids.remove(socket_id)
                log.debug("user %s disconnected socket %s", user_id, socket_id)
                break

    def find_sockets(self, user_id: str) -> List[str]:
        return self.user_to_sockets_map[user_id]

    def find_owner(self, socket_id: str) -> Optional[str]:
        for user_id, socket_ids in self.user_to_sockets_map.items():
            if socket_id in socket_ids:
                return user_id
        return None
