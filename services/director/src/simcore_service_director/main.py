#!/usr/bin/env python3

import logging

from aiohttp import web
from simcore_service_director import resources
from simcore_service_director.rest import routing

log = logging.getLogger(__name__)

def main():
    # create web app and serve
    api_spec_path = resources.get_path(resources.RESOURCE_OPEN_API)
    app = routing.create_web_app(api_spec_path.parent, api_spec_path.name)
    web.run_app(app, port=8001)

if __name__ == "__main__":
    main()
