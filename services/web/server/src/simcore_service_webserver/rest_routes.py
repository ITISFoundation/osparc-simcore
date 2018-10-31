"""

FIXME: for the moment all routings are here and done by hand
"""

import logging
from typing import List

from aiohttp import web

from servicelib import openapi

from .login import routes as auth_routes

from . import rest_handlers, registry_api, comp_backend_api
from .application_keys import APP_OPENAPI_SPECS_KEY

log = logging.getLogger(__name__)


def create(specs: openapi.Spec) -> List[web.RouteDef]:
    # TODO: consider the case in which server creates routes for both v0 and v1!!!
    # TODO: should this be taken from servers instead?
    BASEPATH = '/v' + specs.info.version.split('.')[0]

    log.debug("creating %s ", __name__)
    routes = []

    # TODO: routing will be done automatically using operation_id/tags, etc...

    # diagnostics --
    path, handle = '/', rest_handlers.check_health
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(BASEPATH+path, handle, name=operation_id) )

    path, handle = '/check/{action}', rest_handlers.check_action
    operation_id = specs.paths[path].operations['post'].operation_id
    routes.append( web.post(BASEPATH+path, handle, name=operation_id) )


    # auth --
    routes.extend( auth_routes.create(specs) )


    # FIXME: temp fix for running pipelines
    path, handle = '/services', registry_api.get_services
    routes.append(web.get(BASEPATH+path, handle))
    path, handle = '/start_pipeline', comp_backend_api.start_pipeline
    routes.append(web.post(BASEPATH+path, handle))

    return routes


def setup(app: web.Application):
    valid_specs = app[APP_OPENAPI_SPECS_KEY]

    assert valid_specs, "No API specs in app[%s]. Skipping setup %s "% (APP_OPENAPI_SPECS_KEY, __name__)

    routes = create(valid_specs)
    app.router.add_routes(routes)
