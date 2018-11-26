""" Main application

"""
import json
import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY

from .computation import setup_computation
from .db import setup_db
from .director import setup_director
from .email import setup_email
from .login import setup_login
from .rest import setup_rest
from .s3 import setup_s3
from .security import setup_security
from .session import setup_session
from .sockets import setup_sockets
from .statics import setup_statics
from .storage import setup_storage
from .projects import setup_projects
from .users import setup_users

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

    testing = config["main"].get("testing", False)

    # TODO: create dependency mechanism and compute setup order
    setup_statics(app)
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app, debug=testing)
    setup_email(app)
    setup_computation(app)
    setup_sockets(app)
    setup_login(app)
    setup_director(app)
    setup_s3(app)
    setup_storage(app)
    setup_users(app)
    setup_projects(app, debug=True) # TODO: deactivate fakes i.e. debug=testing

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
