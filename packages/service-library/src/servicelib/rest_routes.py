from aiohttp import web
from typing import List
from .openapi import Spec


def create(specs: Spec, basePath:) -> List[web.RouteDef]:
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


    return routes


    # maps spec operations with handlers
    for url, path in spec.paths.items():
        resource = app.router.add_resource(url) #  TODO: specify a name if with x-name
        for method, operation in path.operations.items():
            try:
                resource.add_route(method, available_handlers.pop(operation.operation_id))
            except KeyError as ex:
                pytest.fail("no handler defined for operationId %s" % ex)
