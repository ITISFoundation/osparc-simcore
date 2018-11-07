""" rest - routes mapping based on oaspecs



TODO: filtering predicates either on spec-paths or handle functions
TODO: check signature of handler functions (see inspect.signature and check for annotations)
TODO: tools to check mapping completeness
"""

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
    # TODO: key operation_id or other ask key-map???
    routes = []
    _handlers_map = handlers_map.copy()

    for url, path in specs.paths.items():
        for method, operation in path.operations.items():
            handler = _handlers_map.pop(operation.operation_id, None)
            if handler:
                routes.append( web.route(method.upper(), url, handler, name=operation.operation_id) )
            else:
                logger.debug("Could not map %s %s %s", url, method.upper(), operation.operation_id)


    #assert _handlers_map, "Not all handlers are assigned?"

    return routes



def create_routes_from_namespace(specs: Spec, handlers_nsp) -> List[web.RouteDef]:
    #TODO: if handlers_nsp is an instance, or a pakcage

    # TODO: add some kind of filter??
    available_handlers = dict(inspect.getmembers(handlers_nsp, inspect.ismethod))

    return create_routes_from_map(specs, available_handlers)
