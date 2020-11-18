""" Main application

"""
import json
import logging
from typing import Dict

from aiohttp import web

from servicelib.application import create_safe_application

from ._meta import WELCOME_MSG
from .activity import setup_activity
from .catalog import setup_catalog
from .computation import setup_computation
from .db import setup_db
from .diagnostics import setup_diagnostics
from .director import setup_director
from .director_v2 import setup_director_v2
from .email import setup_email
from .groups import setup_groups
from .login import setup_login
from .products import setup_products
from .projects import setup_projects
from .publications import setup_publications
from .resource_manager import setup_resource_manager
from .rest import setup_rest
from .security import setup_security
from .session import setup_session
from .settings import setup_settings
from .socketio import setup_socketio
from .statics import setup_statics
from .storage import setup_storage
from .studies_access import setup_studies_access
from .tags import setup_tags
from .tracing import setup_app_tracing
from .users import setup_users

log = logging.getLogger(__name__)


def create_application(config: Dict) -> web.Application:
    """
    Initializes service
    """
    log.debug(
        "Initializing app with config:\n%s",
        json.dumps(config, indent=2, sort_keys=True),
    )

    app = create_safe_application(config)

    setup_settings(app)

    # TODO: create dependency mechanism
    # and compute setup order https://github.com/ITISFoundation/osparc-simcore/issues/1142
    setup_app_tracing(app)
    setup_statics(app)
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_diagnostics(app)
    setup_email(app)
    setup_computation(app)
    setup_socketio(app)
    setup_login(app)
    setup_director(app)
    setup_director_v2(app)
    setup_storage(app)
    setup_users(app)
    setup_groups(app)
    setup_projects(app)
    setup_activity(app)
    setup_resource_manager(app)
    setup_tags(app)
    setup_catalog(app)
    setup_publications(app)
    setup_products(app)
    setup_studies_access(app)

    return app


def run_service(config: dict):
    """Runs service"""
    log.debug("Serving app ... ")

    app = create_application(config)

    async def welcome_banner(_app: web.Application):
        print(WELCOME_MSG, flush=True)

    app.on_startup.append(welcome_banner)

    web.run_app(app, host=config["main"]["host"], port=config["main"]["port"])


__all__ = ("create_application", "run_service")
