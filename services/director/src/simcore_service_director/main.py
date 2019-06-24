#!/usr/bin/env python3

import logging

from aiohttp import web

from servicelib.monitoring import setup_monitoring
from simcore_service_director import registry_cache_task, resources
from simcore_service_director.rest import routing

log = logging.getLogger(__name__)

def setup_app() -> web.Application:
    api_spec_path = resources.get_path(resources.RESOURCE_OPEN_API)
    app = routing.create_web_app(api_spec_path.parent, api_spec_path.name)
    registry_cache_task.setup(app)
    setup_monitoring(app, "simcore_service_director")
    return app

def main():
    app = setup_app()
    web.run_app(app, port=8080)

if __name__ == "__main__":
    main()
