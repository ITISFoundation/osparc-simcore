"""
    Uses socketio and aiohtttp framework
"""
import asyncio
import logging
import os

from aiohttp import web
from aiohttp_swagger import setup_swagger

import config
from async_sio import SIO
from comp_backend_api import comp_backend_routes
from comp_backend_subscribe import subscribe
from registry_api import registry_routes

CONFIG = config.CONFIG[os.environ.get('SIMCORE_WEB_CONFIG', 'default')]

_LOGGER = logging.getLogger(__file__)

# TODO: add logging level via command line (e.g. increase logger level in production for diagonstics)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s-%(lineno)d: %(message)s'
    )

def create_app(args=()):
    """ Creates main application

    """
    #pylint: disable=W0613
    _LOGGER.debug("Starting as %s ...", CONFIG)

    # subscribe to rabbit
    loop = asyncio.get_event_loop()
    loop.create_task(subscribe())

    client_dir = CONFIG.SIMCORE_CLIENT_OUTDIR

    app = web.Application()
    SIO.attach(app)

    # http requests handlers
    async def _index(request):
        """Serve the client-side application."""
        _LOGGER.debug("index.request:\n %s", request)

        index_path = os.path.join(client_dir, 'index.html')
        with open(index_path) as fhnd:
            return web.Response(text=fhnd.read(), content_type='text/html')

    # TODO: check whether this can be done at once
    app.router.add_static('/qxapp', os.path.join(client_dir, 'qxapp'))
    app.router.add_static(
        '/transpiled', os.path.join(client_dir, 'transpiled'))
    app.router.add_static('/resource', os.path.join(client_dir, 'resource'))
    app.router.add_get('/', _index)

    app.router.add_routes(registry_routes)
    app.router.add_routes(comp_backend_routes)

    setup_swagger(app)

    return app


if __name__ == '__main__':
    web.run_app(create_app(),
                host=CONFIG.SIMCORE_WEB_HOSTNAME,
                port=CONFIG.SIMCORE_WEB_PORT)
