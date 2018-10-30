""" Main application

"""
import json
import logging

from aiohttp import web

from .application_keys import APP_CONFIG_KEY
from .computational_backend import setup_computational_backend
from .db import setup_db
from .login import setup_login
from .email import setup_email
from .rest import setup_rest
from .security import setup_security
from .session import setup_session
from .sockets import setup_sio
from .statics import setup_statics

log = logging.getLogger(__name__)


def create_application(config: dict):
    """
        Initializes service
    """
    log.debug("Initializing app ... ")

    app = web.Application()
    app[APP_CONFIG_KEY] = config

    if config['main'].get('testing'):
        log.debug("Config:\n%s",
            json.dumps(config, indent=2, sort_keys=True))


    # TODO: create dependency mechanism and compute setup order
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_email(app)
    setup_computational_backend(app)
    setup_statics(app)
    setup_sio(app)
    setup_rest(app)
    setup_login(app)

    return app

def run_service(config: dict):
    """ Runs service

    """
    log.debug("Serving app ... ")

    app = create_application(config)
    web.run_app(app,
                host=config["main"]["host"],
                port=config["main"]["port"])


__all__ = (
    'create_application',
    'run_service'
)
