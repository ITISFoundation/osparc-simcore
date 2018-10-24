"""

FIXME: for the moment all routings are here and done by hand
"""

import logging
from typing import List

from aiohttp import web

from servicelib import openapi

from . import handlers as auth_handlers
#from .login import fake_handlers as auth_handlers


log = logging.getLogger(__name__)


def create(specs: openapi.Spec) -> List[web.RouteDef]:
    # TODO: consider the case in which server creates routes for both v0 and v1!!!
    # TODO: should this be taken from servers instead?
    BASEPATH = '/v' + specs.info.version.split('.')[0]

    log.debug("creating %s ", __name__)
    routes = []

    # TODO: routing will be done automatically using operation_id/tags, etc...

    # auth --
    path, handle = '/auth/register', auth_handlers.register
    operation_id = specs.paths[path].operations['post'].operation_id
    routes.append( web.post(BASEPATH+path, handle, name=operation_id) )

    path, handle = '/auth/login', auth_handlers.login
    operation_id = specs.paths[path].operations['post'].operation_id
    routes.append( web.post(BASEPATH+path, handle, name=operation_id) )

    path, handle = '/auth/logout', auth_handlers.logout
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(BASEPATH+path, handle, name=operation_id) )

    path, handle = '/auth/confirmation/{code}', auth_handlers.email_confirmation
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(BASEPATH+path, handle, name=operation_id) )

    return routes
