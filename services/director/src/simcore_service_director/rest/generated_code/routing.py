"""GENERATED CODE from codegen.sh
It is advisable to not modify this code if possible.
This will be overriden next time the code generator is called.

use create_web_app to initialise the web application using the specification file.
The base folder is the root of the package.
"""


import logging
from pathlib import Path

from aiohttp import hdrs, web
from aiohttp_apiset import SwaggerRouter
from aiohttp_apiset.exceptions import ValidationError
from aiohttp_apiset.middlewares import Jsonify, jsonify
from aiohttp_apiset.swagger.loader import ExtendedSchemaFile
from aiohttp_apiset.swagger.operations import OperationIdMapping

from .. import handlers
from .models.base_model_ import Model

log = logging.getLogger(__name__)

@web.middleware
async def __handle_errors(request, handler):
    try:
        log.debug("error middleware handling request %s to handler %s", request, handler)
        response = await handler(request)
        return response
    except ValidationError as ex:
        # aiohttp apiset errors
        log.exception("error happened in handling route")
        error = dict(status=ex.status, message=ex.to_tree())
        error_enveloped = dict(error=error)        
        return web.json_response(error_enveloped, status=ex.status)
    except web.HTTPError as ex:
        log.exception("error happened in handling route")
        error = dict(status=ex.status, message=str(ex.reason))
        error_enveloped = dict(data=error)        
        return web.json_response(error_enveloped, status=ex.status)


def create_web_app(base_folder, spec_file, additional_middlewares = None):
    # create the default mapping of the operationId to the implementation code in handlers
    opmap = __create_default_operation_mapping(Path(base_folder / spec_file))

    # generate a version 3 of the API documentation
    router = SwaggerRouter(
        swagger_ui='/apidoc/',
        version_ui=3, # forces the use of version 3 by default
        search_dirs=[base_folder],
        default_validate=True,
    )

    # add automatic jsonification of the models located in generated code
    jsonify.singleton = Jsonify(indent=3, ensure_ascii=False)
    jsonify.singleton.add_converter(Model, lambda o: o.to_dict(), score=0)

    middlewares = [jsonify, __handle_errors]
    if additional_middlewares:
        middlewares.extend(additional_middlewares)
    # create the web application using the API
    app = web.Application(
        router=router,
        middlewares=middlewares,
    )
    router.set_cors(app, domains='*', headers=(
        (hdrs.ACCESS_CONTROL_EXPOSE_HEADERS, hdrs.AUTHORIZATION),
    ))

    # Include our specifications in a router,
    # is now available in the swagger-ui to the address http://localhost:8080/swagger/?spec=v1
    router.include(
        spec=Path(base_folder / spec_file),
        operationId_mapping=opmap,
        name='v0',  # name to access in swagger-ui,
        basePath="/v0" # BUG: in apiset with openapi 3.0.0 [Github bug entry](https://github.com/aamalev/aiohttp_apiset/issues/45)
    )

    return app

def __create_default_operation_mapping(specs_file):
    operation_mapping = {}
    yaml_specs = ExtendedSchemaFile(specs_file)
    paths = yaml_specs['paths']
    for path in paths.items():
        for method in path[1].items(): # can be get, post, patch, put, delete...
            op_str = "operationId"
            if op_str not in method[1]:
                raise Exception("The API %s does not contain the operationId tag for route %s %s" % (specs_file, path[0], method[0]))
            operation_id = method[1][op_str]
            operation_mapping[operation_id] = getattr(handlers, operation_id)
    return OperationIdMapping(**operation_mapping)
