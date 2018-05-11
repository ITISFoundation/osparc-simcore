"""
    Uses socketio and aiohtttp framework
"""
import os
import logging

from aiohttp import web

from async_sio import SIO
import config

CONFIG = config.CONFIG[os.environ.get('SIMCORE_WEB_CONFIG', 'default')]

LOGGER = logging.getLogger(__file__)

# TODO: add logging level via command line (e.g. increase logger level in production for diagonstics)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s-%(lineno)d: %(message)s'
    )

def create_app(args=()):
    """ Creates main application

    """
    #pylint: disable=W0613
    LOGGER.debug("Starting as %s ...", CONFIG)

    client_dir = CONFIG.SIMCORE_CLIENT_OUTDIR

    app = web.Application()
    SIO.attach(app)

    # http requests handlers
    async def _index(request):
        """Serve the client-side application."""
        LOGGER.debug("index.request:\n %s", request)

        index_path = os.path.join(client_dir, 'index.html')
        with open(index_path) as fhnd:
            return web.Response(text=fhnd.read(), content_type='text/html')

    # TODO: check whether this can be done at once
    app.router.add_static('/qxapp', os.path.join(client_dir, 'qxapp'))
    app.router.add_static(
        '/transpiled', os.path.join(client_dir, 'transpiled'))
    app.router.add_static('/resource', os.path.join(client_dir, 'resource'))
    app.router.add_get('/', _index)

    return app


if __name__ == '__main__':
    web.run_app(create_app(),
                host=CONFIG.SIMCORE_WEB_HOSTNAME,
                port=CONFIG.SIMCORE_WEB_PORT)
