import logging
from pathlib import Path

from aiohttp_apiset import SwaggerRouter
from aiohttp_apiset.swagger.loader import ExtendedSchemaFile
from aiohttp_apiset.swagger.operations import OperationIdMapping

from . import handlers
from .config import (
    openapi_path,
    API_URL_VERSION
)

from ..comp_backend_api import comp_backend_routes
from ..registry_api import registry_routes


log = logging.getLogger(__name__)


def create_router(oas3_path: Path=None):
    """
        Creates a router provided openapi specification file version 3 (oas3)

        oas3_path: path to rest-api specifications. Mostly used for testing different apis
    """
    if oas3_path is None:
        oas3_path = openapi_path()

    log.debug("OAS3 in %s", oas3_path)

    # generate a version 3 of the API documentation
    router = SwaggerRouter(
        swagger_ui='/apidoc/',
        version_ui=3, # forces the use of version 3 by default
        search_dirs=[ str(oas3_path.parent) ],
        default_validate=True,
    )

    # TODO: check root_factory in SwaggerRouter?!
    # TODO: Deprecated since version 3.3: The custom routers support is deprecated, the parameter will be removed in 4.0.
    # See https://docs.aiohttp.org/en/stable/web_advanced.html#custom-routing-criteria

    return router

def include_oaspecs_routes(router, oas3_path: Path=None):
    if oas3_path is None:
        oas3_path = openapi_path()

    # create the default mapping of the operationId to the implementation code in handlers
    opmap = _create_default_operation_mapping(oas3_path, handlers)

    # Include our specifications in a router,
    # Gets file in http://localhost:8080/apidoc/swagger.yaml?spec=/v1
    router.include(
        spec=oas3_path,
        operationId_mapping=opmap,
        name=API_URL_VERSION,  # name to access in swagger-ui,
        basePath="/" + API_URL_VERSION # BUG: in apiset with openapi 3.0.0 [Github bug entry](https://github.com/aamalev/aiohttp_apiset/issues/45)
    )

def include_other_routes(router):
    # FIXME: create a router in scsdk that extends SwaggerRouter
    def _add_routes(self, routes):
        """Append routes to route table.

        Parameter should be a sequence of RouteDef objects.
        """
        for route_obj in routes:
            route_obj.register(self)


    basePath="/" + API_URL_VERSION
    router.add_get(basePath+"/ping", handlers.ping, name="ping")

    # TODO: add authorization on there routes
    #app.router.add_routes(registry_routes)
    #app.router.add_routes(comp_backend_routes)
    _add_routes(router, registry_routes)
    _add_routes(router, comp_backend_routes)

    # middlewares
    # setup_swagger(app, swagger_url=prefix+"/doc")


def _create_default_operation_mapping(specs_file, handlers_module):
    """
        maps every route's "operationId" in the OAS with a function with the same
        name within ``handlers_module``

        Ensures all operationId tags are mapped to handlers_module's functions
    """
    operation_mapping = {}
    yaml_specs = ExtendedSchemaFile(specs_file)
    paths = yaml_specs['paths']
    for path in paths.items():
        for method in path[1].items(): # can be get, post, patch, put, delete...
            op_str = "operationId"
            if op_str not in method[1]:
                raise ValueError("The API %s does not contain the operationId tag for route %s %s" % (specs_file, path[0], method[0]))
            operation_id = method[1][op_str]
            operation_mapping[operation_id] = getattr(handlers_module, operation_id)
    return OperationIdMapping(**operation_mapping)



__all__ = (
    'create_router',
    'include_oaspecs_routes',
    'include_other_routes'
)
