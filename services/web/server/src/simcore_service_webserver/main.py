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
from . import rest
from .rest import setup_rest
from . import resources


_LOGGER = logging.getLogger(__name__)

def init_app(config):
    """
        Initializes service
    """
    _LOGGER.debug("Initializing app ... ")

    oas_path = resources.get_path(".openapi/v1/test_1.0.0-oas3.yaml")
    router = rest.routing.create_router(oas_path)

    app = web.Application(router=router)
    app["config"] = config

    setup_db(app)
    setup_session(app)
    setup_auth(app)
    setup_computational_backend(app)
    setup_statics(app)
    setup_sio(app)
    setup_api(app)
    setup_rest(app)

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
