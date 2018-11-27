"""

FIXME: for the moment all routings are here and done by hand
"""

import logging
from typing import List

from aiohttp import web

from servicelib.openapi import OpenApiSpec

from . import handlers

log = logging.getLogger(__name__)


def create(specs: OpenApiSpec) -> List[web.RouteDef]:
    # TODO: consider the case in which server creates routes for both v0 and v1!!!
    # TODO: should this be taken from servers instead?
    BASEPATH = '/v' + specs.info.version.split('.')[0]

    log.debug("creating %s ", __name__)
    routes = []

    # TODO: routing will be done automatically using operation_id/tags, etc...
    #   routes = auto_routing(specs, handlers)

    # diagnostics --
    path, handle = '/', handlers.check_health
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(BASEPATH+path, handle, name=operation_id) )

    path, handle = '/check/{action}', handlers.check_action
    operation_id = specs.paths[path].operations['post'].operation_id
    routes.append( web.post(BASEPATH+path, handle, name=operation_id) )

    path, handle = '/locations', handlers.get_storage_locations
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(BASEPATH+path, handle, name=operation_id) )

    path, handle = '/locations/{location_id}/files/metadata', handlers.get_files_metadata
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(BASEPATH+path, handle, name=operation_id) )

    path, handle = '/locations/{location_id}/files/{fileId}/metadata', handlers.get_file_metadata
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(BASEPATH+path, handle, name=operation_id) )

    # TODO: Implements update
    # path, handle = '/{location_id}/files/{fileId}/metadata', handlers.update_file_metadata
    # operation_id = specs.paths[path].operations['patch'].operation_id
    # routes.append( web.patch(BASEPATH+path, handle, name=operation_id) )

    path, handle = '/locations/{location_id}/files/{fileId}', handlers.download_file
    operation_id = specs.paths[path].operations['get'].operation_id
    routes.append( web.get(BASEPATH+path, handle, name=operation_id) )

    path, handle = '/locations/{location_id}/files/{fileId}', handlers.delete_file
    operation_id = specs.paths[path].operations['delete'].operation_id
    routes.append( web.delete(BASEPATH+path, handle, name=operation_id) )

    path, handle = '/locations/{location_id}/files/{fileId}', handlers.upload_file
    operation_id = specs.paths[path].operations['put'].operation_id
    routes.append( web.put(BASEPATH+path, handle, name=operation_id) )


    return routes
