#!/usr/bin/env python3

import logging
from pathlib import Path

from aiohttp import web
from simcore_service_director import registry_proxy
from simcore_service_director.rest import routing


_LOGGER = logging.getLogger(__name__)


logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s-%(lineno)d: %(message)s'
    )


def main():
    # init registry proxy
    registry_proxy.setup_registry_connection()

    # create web app and serve
    base_folder = Path(__file__).parent
    openapi_spec_file = ".openapi/v1/director_api.yaml"
    app = routing.create_web_app(base_folder, openapi_spec_file)
    web.run_app(app, port=8001)

if __name__ == "__main__":
    main()
