#!/usr/bin/env python3

import logging

from aiohttp import web
from simcore_service_director import resources, registry_cache_task
from simcore_service_director.rest import routing

log = logging.getLogger(__name__)

def setup_app() -> web.Application:
    api_spec_path = resources.get_path(resources.RESOURCE_OPEN_API)
    app = routing.create_web_app(api_spec_path.parent, api_spec_path.name)
    registry_cache_task.setup(app)
    return app

def main():
    app = setup_app()
    web.run_app(app, port=8080)

if __name__ == "__main__":
    main()
