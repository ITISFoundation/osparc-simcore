#!/usr/bin/env python3

import logging
from pathlib import Path

from aiohttp import hdrs, web
from aiohttp_apiset import SwaggerRouter
from aiohttp_apiset.middlewares import jsonify, Jsonify
from aiohttp_apiset.swagger.operations import OperationIdMapping

from director import api

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s-%(lineno)d: %(message)s'
    )

BASE = Path(__file__).parent

# operationId-handler association
opmap = OperationIdMapping(
    **{"api.root_get": api.root_get,
    "list_interactive_services_get": api.list_interactive_services_get}
)

def mainApiSet():
    router = SwaggerRouter(
        swagger_ui='/swagger/',
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
    )

    web.run_app(app)


main = mainApiSet


if __name__ == "__main__":
    main()
