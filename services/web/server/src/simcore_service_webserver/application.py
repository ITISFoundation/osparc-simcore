""" Main application

"""
import json
import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.monitoring import setup_monitoring

from .application_proxy import setup_app_proxy
from .computation import setup_computation
from .db import setup_db
from .director import setup_director
from .email import setup_email
from .login import setup_login
from .projects import setup_projects
from .rest import setup_rest
from .s3 import setup_s3
from .security import setup_security
from .session import setup_session
from .sockets import setup_sockets
from .statics import setup_statics
from .storage import setup_storage
from .studies_access import setup_studies_access
from .users import setup_users

log = logging.getLogger(__name__)

from typing import Dict

def create_application(config: Dict) -> web.Application:
    """
        Initializes service
    """
    log.debug("Initializing app ... ")

    app = web.Application()
    app[APP_CONFIG_KEY] = config

    log.debug("Config:\n%s",
        json.dumps(config, indent=2, sort_keys=True))

    testing = config["main"].get("testing", False)
    monitoring = config["main"]["monitoring_enabled"]
    # TODO: create dependency mechanism and compute setup order

    # TODO: distinguish between different replicas {simcore_service_webserver, replica=1}?
    if monitoring:
        setup_monitoring(app, "simcore_service_webserver")
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
    setup_projects(app) # needs storage
    setup_studies_access(app)

    if config['director']["enabled"]:
        setup_app_proxy(app) # TODO: under development!!!

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
