""" Main application

"""
import logging

from aiohttp import web

from .db import setup_db
from .security import setup_security
from .rest import setup_rest
from .session import setup_session
from .statics import setup_statics
from .computational_backend import setup_computational_backend
from .sockets import setup_sio
from .settings.constants import APP_CONFIG_KEY


log = logging.getLogger(__name__)

def create_application(config):
    """
        Initializes service
    """
    log.debug("Initializing app ... ")

    app = web.Application()
    app[APP_CONFIG_KEY] = config

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_computational_backend(app)
    setup_statics(app)
    setup_sio(app)
    setup_rest(app)

    return app

def run_service(config):
    """ Runs service

    NOTICE it is sync!
    """
    log.debug("Serving app ... ")

    app = create_application(config)
    web.run_app(app,
                host=config["app"]["host"],
                port=config["app"]["port"])
