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


__version__ = "0.0.1"

_LOGGER = logging.getLogger(__name__)

def init_app(config):
    """
        Initializes service

    NOTICE it is sync!
    """
    _LOGGER.debug("Initializing app ... ")

    app = web.Application()
    app["config"] = config

    setup_db(app)
    setup_session(app)
    setup_auth(app)
    setup_computational_backend(app)
    setup_statics(app)
    setup_sio(app)
    setup_api(app)

    return app

def run(config):
    """ Runs service

    NOTICE it is sync!
    """
    _LOGGER.debug("Serving app ... ")

    app = init_app(config)
    web.run_app(app,
                host=config["app"]["host"],
                port=config["app"]["port"])
