#!/usr/bin/env python3

import logging
from pathlib import Path

from aiohttp import hdrs, web
from aiohttp_apiset import SwaggerRouter
from aiohttp_apiset.middlewares import Jsonify, jsonify
from aiohttp_apiset.swagger.operations import OperationIdMapping
from aiohttp_apiset.swagger.loader import ExtendedSchemaFile

from director import api

SPEC_FILE = "director_api.yaml"

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s-%(lineno)d: %(message)s'
    )

BASE = Path(__file__).parent


def create_default_operation_mapping(specs_file):
    operation_mapping = {}
    yaml_specs = ExtendedSchemaFile(specs_file)
    paths = yaml_specs['paths']
    for path in paths.items():
        for method in path[1].items(): # can be get, post, patch, put, delete...
            op_str = "operationId"
            if op_str not in method[1]:
                raise Exception("The API %s does not contain the operationId tag for route %s %s" % (specs_file, path[0], method[0]))
            operation_id = method[1][op_str]            
            operation_mapping[operation_id] = getattr(api, operation_id)
    return OperationIdMapping(**operation_mapping)

def mainApiSet():
    opmap = create_default_operation_mapping(Path(BASE / SPEC_FILE))

    router = SwaggerRouter(
        swagger_ui='/apidoc/',
        version_ui=3, # forces the use of version 3 by default
        search_dirs=[BASE],
        default_validate=True,
    )

    # TODO: clean up TPOS!
    jsonify.singleton = Jsonify(indent=3, ensure_ascii=False)
    jsonify.singleton.add_converter('director.models.base_model_.Model', lambda o: o.to_dict(), score=0)

    app = web.Application(
        router=router,
        middlewares=[jsonify],
    )
    router.set_cors(app, domains='*', headers=(
        (hdrs.ACCESS_CONTROL_EXPOSE_HEADERS, hdrs.AUTHORIZATION),
    ))




    # Include our specifications in a router,
    # is now available in the swagger-ui to the address http://localhost:8080/swagger/?spec=v1
    router.include(
        spec='director_api.yaml',
        operationId_mapping=opmap,
        name='v1',  # name to access in swagger-ui,
        basePath="/v1" # BUG: in apiset with openapi 3.0.0 [Github bug entry](https://github.com/aamalev/aiohttp_apiset/issues/45)
    )

    web.run_app(app, port=8001)


main = mainApiSet


if __name__ == "__main__":
    main()
