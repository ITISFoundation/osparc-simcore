""" Main application

"""
import logging

from aiohttp import web

from .db import setup_db
from .auth import setup_auth
from .api import setup_api
from .session import setup_session
from .statics import setup_statics
from .computational_backend import setup_computational_backend
from . async_sio import setup_sio

from .config import get_config

__version__ = "0.0.1"


def init_app(argv=None):
    """
    NOTICE it is async!
    """
    app = web.Application()
    app['config'] = get_config(argv)

    setup_sio(app)
    setup_db(app)
    setup_session(app)
    setup_auth(app)
    setup_api(app)
    setup_statics(app)
    setup_computational_backend(app)

    return app


def main(argv):
    """
    NOTICE it is sync!
    """
    logging.basicConfig(level=logging.DEBUG)

    app = init_app(argv)
    config = get_config(argv)
    web.run_app(app,
                host=config['host'],
                port=config['port'])
