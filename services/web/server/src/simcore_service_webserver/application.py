""" Main application

"""
import json
import logging
from typing import Dict

from aiohttp import web

from servicelib.application import create_safe_application
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.monitoring import setup_monitoring
from servicelib.tracing import setup_tracing

from .activity import setup_activity
from .application_proxy import setup_app_proxy
from .computation import setup_computation
from .db import setup_db
from .director import setup_director
from .email import setup_email
from .login import setup_login
from .projects import setup_projects
from .resource_manager import setup_resource_manager
from .rest import setup_rest
from .s3 import setup_s3
from .security import setup_security
from .session import setup_session
from .socketio import setup_sockets
from .statics import setup_statics
from .storage import setup_storage
from .studies_access import setup_studies_access
from .users import setup_users

log = logging.getLogger(__name__)


@app_module_setup("servicelib.monitoring", ModuleCategory.ADDON,
    config_enabled="main.monitoring_enabled",
    logger=log)
def setup_app_monitoring(app: web.Application):
    # TODO: distinguish between different replicas {simcore_service_webserver, replica=1}?
    # TODO: move option to section?
    return setup_monitoring(app, "simcore_service_webserver")

@app_module_setup("tracing", ModuleCategory.ADDON, config_enabled="tracing.enabled", logger=log)
def setup_app_tracing(app: web.Application, config: Dict):
    host=config["main"]["host"]
    port=config["main"]["port"]
    return setup_tracing(app, "simcore_service_webserver", host, port, config["tracing"])


def create_application(config: Dict) -> web.Application:
    """
        Initializes service
    """
    log.debug("Initializing app with config:\n%s",
        json.dumps(config, indent=2, sort_keys=True))

    app = create_safe_application(config)

    # testing = config["main"].get("testing", False)

    # TODO: create dependency mechanism and compute setup order https://github.com/ITISFoundation/osparc-simcore/issues/1142
    setup_app_monitoring(app)
    setup_app_tracing(app, config)
    setup_statics(app)
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
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
    setup_activity(app)
    setup_app_proxy(app) # TODO: under development!!!
    setup_resource_manager(app)

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
