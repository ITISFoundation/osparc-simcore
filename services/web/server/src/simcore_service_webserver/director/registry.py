""" Local registry of running interactive services

FIXME: this is not reliable with server replicas. Temporary
solution until director provides full CRUD on running services

NOTE: Analogous to the services/web/server/src/simcore_service_webserver/director/interactive_services_manager.py
__REGISTRY but scoped in the application
"""
import logging
from collections import defaultdict
from typing import Dict

import attr
from aiohttp import web

logger = logging.getLogger(__name__)



def _default_dict_factory():
    return defaultdict(list)

@attr.s(auto_attribs=True)
class InteractiveServiceLocalRegistry:
    """ Keeps a record of running interactive services

        - Assumes every service is owned by a single user
    """
    # pylint: disable=E1136
    # pylint: disable=E1101
    user_to_services_map: Dict = attr.Factory(_default_dict_factory)

    #def as_starting()
    #def as_stopping()

    def as_started(self, user_id:str, service_id: str) -> int:
        """ registers service as started and returns curent user's owned services

        """
        if service_id not in self.user_to_services_map[user_id]:
            self.user_to_services_map[user_id].append(service_id)
        return len(self.user_to_services_map[user_id])

    def as_stopped(self, service_id: str):
        for userid, services in self.user_to_services_map.items():
            if service_id in services:
                services.remove(service_id)
                logger.debug("user %s stopped service %s", userid, service_id)
                break

    def find_owner(self, service_id: str) -> str:
        """
        :param service_id: running interactive service
        :type service_id: str
        :return: user id owning service or None if unknown
        :rtype: str
        """
        for userid, services in self.user_to_services_map.items():
            if service_id in services:
                return userid
        return None


def get_registry(app: web.Application)->InteractiveServiceLocalRegistry:
    return app[__name__ + ".registry"]

def set_registry(app: web.Application, reg:InteractiveServiceLocalRegistry):
    app[__name__ + ".registry"] = reg



# Missing CRUD operations on director API ------
# GET /running_interactive_services?filter=user={user_id}
