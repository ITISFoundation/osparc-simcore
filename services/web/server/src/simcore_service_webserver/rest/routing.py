import logging
from pathlib import Path

from aiohttp_apiset import SwaggerRouter
from aiohttp_apiset.swagger.loader import ExtendedSchemaFile
from aiohttp_apiset.swagger.operations import OperationIdMapping

from . import handlers

_LOGGER = logging.getLogger(__name__)


def create_router( oas3_path :Path):
    _LOGGER.debug("OAS3 in %s", oas3_path)

    # generate a version 3 of the API documentation
    router = SwaggerRouter(
        swagger_ui='/apidoc/',
        version_ui=3, # forces the use of version 3 by default
        search_dirs=[ str(oas3_path.parent) ],
        default_validate=True,
    )

    version_prefix = str(oas3_path.parent.name)

    # create the default mapping of the operationId to the implementation code in handlers
    opmap = _create_default_operation_mapping(oas3_path, handlers)

    # Include our specifications in a router,
    # is now available in the swagger-ui to the address http://localhost:8080/swagger/?spec=v1
    router.include(
        spec=oas3_path,
        operationId_mapping=opmap,
        name=version_prefix,  # name to access in swagger-ui,
        basePath="/" + version_prefix # BUG: in apiset with openapi 3.0.0 [Github bug entry](https://github.com/aamalev/aiohttp_apiset/issues/45)
    )

    return router


def _create_default_operation_mapping(specs_file, handlers_module):
    """
        maps every route's "operationId" in the OAS with a function with the same
        name within ``handlers_module``
    """
    operation_mapping = {}
    yaml_specs = ExtendedSchemaFile(specs_file)
    paths = yaml_specs['paths']
    for path in paths.items():
        for method in path[1].items(): # can be get, post, patch, put, delete...
            op_str = "operationId"
            if op_str not in method[1]:
                raise Exception("The API %s does not contain the operationId tag for route %s %s" % (specs_file, path[0], method[0]))
            operation_id = method[1][op_str]
            operation_mapping[operation_id] = getattr(handlers_module, operation_id)
    return OperationIdMapping(**operation_mapping)



__all__ = [
    "create_router"
]
