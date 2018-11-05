import inspect
import logging
from typing import Dict, List

from aiohttp import web

from .openapi import Spec

logger = logging.getLogger(__name__)


def create_routes_from_map(specs: Spec, handlers_map: Dict) -> List[web.RouteDef]:
    """
        handlers_map[operation_id] == handler
    """
    logger.debug(specs, handlers_map)
    # TODO: key operation_id or other???
    return list()



def create_routes_from_namespace(specs: Spec, handlers_nsp) -> List[web.RouteDef]:
    #TODO: if handlers_nsp is an instance, or a pakcage


    available_handlers = dict(inspect.getmembers(handlers_nsp, inspect.ismethod))
    return create_routes_from_map(specs, available_handlers)
