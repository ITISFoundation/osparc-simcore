"""

FIXME: for the moment all routings are here and done by hand
"""

import logging
from typing import List

from aiohttp import web

from servicelib import openapi

from . import computation_api, rest_handlers
from .director import registry_api

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


    # FIXME: temp fix for running pipelines
    path, handle = '/services', registry_api.get_services
    routes.append(web.get(base_path+path, handle))
    path, handle = '/start_pipeline', computation_api.start_pipeline
    routes.append(web.post(base_path+path, handle))


    return routes
