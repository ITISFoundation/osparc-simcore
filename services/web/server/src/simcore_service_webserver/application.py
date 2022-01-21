""" Main application

"""
import json
import logging
from typing import Any, Dict

from aiohttp import web
from servicelib.aiohttp.application import create_safe_application

from ._constants import APP_SETTINGS_KEY
from ._meta import WELCOME_MSG
from .activity.module_setup import setup_activity
from .application_settings import ApplicationSettings, setup_settings
from .catalog import setup_catalog
from .clusters.module_setup import setup_clusters
from .computation import setup_computation
from .db import setup_db
from .diagnostics import setup_diagnostics
from .director.module_setup import setup_director
from .director_v2 import setup_director_v2
from .email import setup_email
from .exporter.module_setup import setup_exporter
from .groups import setup_groups
from .login.module_setup import setup_login
from .meta_modeling import setup_meta_modeling
from .products import setup_products
from .projects.module_setup import setup_projects
from .publications import setup_publications
from .remote_debug import setup_remote_debugging
from .resource_manager.module_setup import setup_resource_manager
from .rest import setup_rest
from .security import setup_security
from .session import setup_session
from .socketio.module_setup import setup_socketio
from .statics import setup_statics
from .storage import setup_storage
from .studies_access import setup_studies_access
from .studies_dispatcher.module_setup import setup_studies_dispatcher
from .tags import setup_tags
from .tracing import setup_app_tracing
from .users import setup_users
from .version_control import setup_version_control

log = logging.getLogger(__name__)


def create_application(config: Dict[str, Any]) -> web.Application:
    """
    Initializes service
    """
    log.debug(
        "Initializing app with config:\n%s",
        json.dumps(config, indent=2, sort_keys=True),
    )

    app = create_safe_application(config)

    setup_settings(app)
    settings: ApplicationSettings = app[APP_SETTINGS_KEY]

    # WARNING: setup order matters
    # TODO: create dependency mechanism
    # and compute setup order https://github.com/ITISFoundation/osparc-simcore/issues/1142
    #
    setup_remote_debugging(app)

    # core modules
    setup_app_tracing(app)  # WARNING: must be UPPERMOST middleware
    setup_statics(app)
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app, swagger_doc_enabled=True)
    setup_diagnostics(app)
    setup_email(app)
    setup_computation(app)
    setup_socketio(app)
    setup_login(app)
    setup_director(app)
    setup_director_v2(app)
    setup_storage(app)

    # users
    setup_users(app)
    setup_groups(app)

    # projects
    setup_projects(app)
    # project add-ons
    if settings.WEBSERVER_DEV_FEATURES_ENABLED:
        setup_version_control(app)
        setup_meta_modeling(app)
    else:
        log.info("Skipping add-ons under development: version-control and meta")

    # TODO: classify
    setup_activity(app)
    setup_resource_manager(app)
    setup_tags(app)
    setup_catalog(app)
    setup_publications(app)
    setup_products(app)
    setup_studies_access(app)
    setup_studies_dispatcher(app)
    setup_exporter(app)
    setup_clusters(app)

    async def welcome_banner(_app: web.Application):
        print(WELCOME_MSG, flush=True)

    app.on_startup.append(welcome_banner)

    return app


def run_service(app: web.Application, config: Dict[str, Any]):
    web.run_app(
        app,
        host=config["main"]["host"],
        port=config["main"]["port"],
        # this gets overriden by the gunicorn config if any
        access_log_format='%a %t "%r" %s %b --- [%Dus] "%{Referer}i" "%{User-Agent}i"',
    )


__all__ = ("create_application", "run_service")
