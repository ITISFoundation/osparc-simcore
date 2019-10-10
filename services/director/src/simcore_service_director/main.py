#!/usr/bin/env python3

import logging

from aiohttp import ClientSession, web
from servicelib.monitoring import setup_monitoring
from simcore_service_director import registry_cache_task, resources
from simcore_service_director.rest import routing

from .config import CLIENT_SESSION_KEY

log = logging.getLogger(__name__)


async def _persistent_session(app: web.Application):
    app[CLIENT_SESSION_KEY] = session = ClientSession()
    yield
    await session.close()


def setup_app() -> web.Application:
    api_spec_path = resources.get_path(resources.RESOURCE_OPEN_API)
    app = routing.create_web_app(api_spec_path.parent, api_spec_path.name)

    registry_cache_task.setup(app)

    # TODO: temporary disabled until service is updated
    if False: #pylint: disable=using-constant-test
        setup_monitoring(app, "simcore_service_director")

    app.cleanup_ctx.append(_persistent_session)

    return app

def main():
    app = setup_app()
    web.run_app(app, port=8080)

if __name__ == "__main__":
    main()
