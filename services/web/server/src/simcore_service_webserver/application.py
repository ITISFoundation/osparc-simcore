""" Main application

"""
import logging
from pprint import pformat
from typing import Any

from aiohttp import web
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.invitations import setup_invitations

from ._meta import WELCOME_GC_MSG, WELCOME_MSG, info
from .activity.plugin import setup_activity
from .application_settings import setup_settings
from .catalog import setup_catalog
from .clusters.plugin import setup_clusters
from .computation import setup_computation
from .db import setup_db
from .diagnostics import setup_diagnostics
from .director.plugin import setup_director
from .director_v2 import setup_director_v2
from .email import setup_email
from .exporter.plugin import setup_exporter
from .garbage_collector import setup_garbage_collector
from .groups import setup_groups
from .login.plugin import setup_login
from .long_running_tasks import setup_long_running_tasks
from .meta_modeling import setup_meta_modeling
from .products import setup_products
from .projects.plugin import setup_projects
from .publications import setup_publications
from .rabbitmq import setup_rabbitmq_client
from .redis import setup_redis
from .remote_debug import setup_remote_debugging
from .resource_manager.plugin import setup_resource_manager
from .rest import setup_rest
from .scicrunch.plugin import setup_scicrunch
from .security import setup_security
from .session import setup_session
from .socketio.plugin import setup_socketio
from .statics import setup_statics
from .storage import setup_storage
from .studies_dispatcher.plugin import setup_studies_dispatcher
from .tags import setup_tags
from .tracing import setup_app_tracing
from .users import setup_users
from .version_control import setup_version_control

log = logging.getLogger(__name__)


def create_application() -> web.Application:
    """
    Initializes service
    """
    app = create_safe_application()
    settings = setup_settings(app)

    # WARNING: setup order matters
    # TODO: create dependency mechanism
    # and compute setup order https://github.com/ITISFoundation/osparc-simcore/issues/1142
    #
    setup_remote_debugging(app)

    # core modules
    setup_app_tracing(app)  # WARNING: must be UPPERMOST middleware
    setup_db(app)
    setup_long_running_tasks(app)
    setup_redis(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)

    # front-end products
    setup_products(app)
    setup_statics(app)

    # monitoring
    setup_diagnostics(app)
    setup_activity(app)
    setup_rabbitmq_client(app)
    setup_computation(app)
    setup_socketio(app)

    # login
    setup_email(app)
    setup_invitations(app)
    setup_login(app)

    # interaction with other backend services
    setup_director(app)
    setup_director_v2(app)
    setup_storage(app)
    setup_catalog(app)

    # resource management
    setup_resource_manager(app)
    setup_garbage_collector(app)

    # users
    setup_users(app)
    setup_groups(app)

    # projects
    setup_projects(app)
    # project add-ons
    setup_version_control(app)
    setup_meta_modeling(app)

    # tagging
    setup_scicrunch(app)
    setup_tags(app)

    setup_publications(app)
    setup_studies_dispatcher(app)
    setup_exporter(app)
    setup_clusters(app)

    async def welcome_banner(_app: web.Application):
        print(WELCOME_MSG, flush=True)
        if settings.WEBSERVER_GARBAGE_COLLECTOR:
            print("with", WELCOME_GC_MSG, flush=True)

    async def finished_banner(_app: web.Application):
        print(info.get_finished_banner(), flush=True)

    # NOTE: *last* events
    app.on_startup.append(welcome_banner)
    app.on_shutdown.append(finished_banner)

    log.debug("Routes in app: \n %s", pformat(app.router.named_resources()))

    return app


def run_service(app: web.Application, config: dict[str, Any]):
    web.run_app(
        app,
        host=config["main"]["host"],
        port=config["main"]["port"],
        # this gets overriden by the gunicorn config if any
        access_log_format='%a %t "%r" %s %b --- [%Dus] "%{Referer}i" "%{User-Agent}i"',
    )


__all__ = ("create_application", "run_service")
