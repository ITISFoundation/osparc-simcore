"""

FIXME: for the moment all routings are here and done by hand
"""

import logging
from typing import List

from aiohttp import web

from simcore_servicelib import openapi

from . import auth_handlers as handlers
from .settings.constants import API_URL_VERSION, APP_OAS_KEY

log = logging.getLogger(__name__)


def create(specs: openapi.Spec) -> List[web.RouteDef]:
    # TODO: consider the case in which server creates routes for both v0 and v1!!!
    BASEPATH = '/v' + specs.info.version.split('.')[0]

    log.debug("creating %s ", __name__)
    routes = []

    # TODO: this will be done automatically
    path = '/'
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(BASEPATH+path, handlers.check_health, name=operation_id) )

    path = '/check/{action}'
    operation_id = specs.paths[path].operations['post'].operation_id
    routes.append( web.post(BASEPATH+path, handlers.check_action, name=operation_id) )

    return routes


def setup(app: web.Application):
    valid_specs = app[APP_OAS_KEY]

    assert valid_specs, "No API specs in app[%s]. Skipping setup %s "% (APP_OAS_KEY, __name__)

    routes = create(valid_specs)
    app.router.add_routes(routes)
