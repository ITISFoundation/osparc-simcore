"""

FIXME: for the moment all routings are here and done by hand
"""

import logging
from typing import List

from aiohttp import web

from servicelib import openapi

from . import storage_handlers

log = logging.getLogger(__name__)


def create(specs: openapi.Spec) -> List[web.RouteDef]:
    # TODO: consider the case in which server creates routes for both v0 and v1!!!
    # TODO: should this be taken from servers instead?
    BASEPATH = '/v' + specs.info.version.split('.')[0]

    log.debug("creating %s ", __name__)
    routes = []

    # TODO: routing will be done automatically using operation_id/tags, etc...

    # storage --
    path, handler = '/storage/locations', storage_handlers.get_storage_locations
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(BASEPATH+path, handler, name=operation_id) )


    return routes
