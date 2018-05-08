"""
    Uses socketio and aiohtttp framework
"""

import logging
import os

from aiohttp import web

from async_sio import SIO
from config import CONFIG


def create_app(args=()):
    """ Creates main application """
    #pylint: disable=W0613

    #FIXME: this config needs to be identical as in main!!!
    app_config = CONFIG[os.environ.get('SIMCORE_WEB_CONFIG', 'default')]

    logging.basicConfig(level=app_config.LOG_LEVEL)

    client_dir = app_config.SIMCORE_CLIENT_OUTDIR

    app = web.Application()
    SIO.attach(app)

    # http requests handlers
    async def _index(request):
        """Serve the client-side application."""
        logging.debug("index.request:\n %s", request)

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
    _CONFIG = CONFIG[os.environ.get('SIMCORE_WEB_CONFIG', 'default')]
    web.run_app(create_app(),
                host=_CONFIG.SIMCORE_WEB_HOSTNAME,
                port=_CONFIG.SIMCORE_WEB_PORT)
