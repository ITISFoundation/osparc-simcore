#!/usr/bin/env python3

import logging

from aiohttp import web

from simcore_service_director import config, registry_proxy
from simcore_service_director.rest import routing

log = logging.getLogger(__name__)

def main():
    # init registry proxy
    registry_proxy.setup_registry_connection()

    # create web app and serve
    app = routing.create_web_app(config.OPEN_API_BASE_FOLDER, config.OPEN_API_SPEC_FILE)
    web.run_app(app, port=8001)

if __name__ == "__main__":
    main()
