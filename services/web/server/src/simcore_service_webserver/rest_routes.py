""" Create diagnostics routes and maps them to rest_handlers

"""

import logging
from typing import List

from aiohttp import web

from servicelib import openapi

from . import rest_handlers

log = logging.getLogger(__name__)


def create(specs: openapi.Spec) -> List[web.RouteDef]:
    # TODO: consider the case in which server creates routes for both v0 and v1!!!
    # TODO: should this be taken from servers instead?
    base_path = openapi.get_base_path(specs)

    log.debug("creating %s ", __name__)
    routes = []

    # TODO: routing will be done automatically using operation_id/tags, etc...

    # diagnostics --
    path, handle = '/', rest_handlers.check_health
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(base_path+path, handle, name=operation_id) )

    path, handle = '/check/{action}', rest_handlers.check_action
    operation_id = specs.paths[path].operations['post'].operation_id
    routes.append( web.post(base_path+path, handle, name=operation_id) )


    return routes
