"""

FIXME: for the moment all routings are here and done by hand
"""

import logging
from typing import List

from aiohttp import web

from servicelib import openapi

from . import handlers as login_handlers
#from .login import fake_handlers as login_handlers


log = logging.getLogger(__name__)


def create(specs: openapi.Spec) -> List[web.RouteDef]:
    # TODO: consider the case in which server creates routes for both v0 and v1!!!
    # TODO: should this be taken from servers instead?
    base_path = openapi.get_base_path(specs)

    log.debug("creating %s ", __name__)
    routes = []

    # TODO: routing will be done automatically using operation_id/tags, etc...

    # auth --
    path, handler = '/auth/register', login_handlers.register
    operation_id = specs.paths[path].operations['post'].operation_id
    routes.append( web.post(base_path+path, handler, name=operation_id) )

    path, handler = '/auth/login', login_handlers.login
    operation_id = specs.paths[path].operations['post'].operation_id
    routes.append( web.post(base_path+path, handler, name=operation_id) )

    path, handler = '/auth/logout', login_handlers.logout
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(base_path+path, handler, name=operation_id) )

    path, handler = '/auth/confirmation/{code}', login_handlers.email_confirmation
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(base_path+path, handler, name=operation_id) )

    path, handler = '/auth/change-email', login_handlers.change_email
    operation_id = specs.paths[path].operations['post'].operation_id
    routes.append( web.post(base_path+path, handler, name=operation_id) )

    return routes


# alias
create_routes = create

__all__ = (
    'create_routes'
)
