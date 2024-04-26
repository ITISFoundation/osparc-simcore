""" Main application

"""
import logging
from pprint import pformat
from typing import Any

from aiohttp import web
from servicelib.aiohttp.application import create_safe_application

from ._meta import WELCOME_DB_LISTENER_MSG, WELCOME_GC_MSG, WELCOME_MSG, info
from .activity.plugin import setup_activity
from .announcements.plugin import setup_announcements
from .api_keys.plugin import setup_api_keys
from .application_settings import get_application_settings, setup_settings
from .catalog.plugin import setup_catalog
from .clusters.plugin import setup_clusters
from .db.plugin import setup_db
from .db_listener.plugin import setup_db_listener
from .diagnostics.plugin import setup_diagnostics, setup_profiling_middleware
from .director_v2.plugin import setup_director_v2
from .dynamic_scheduler.plugin import setup_dynamic_scheduler
from .email.plugin import setup_email
from .exporter.plugin import setup_exporter
from .garbage_collector.plugin import setup_garbage_collector
from .groups.plugin import setup_groups
from .invitations.plugin import setup_invitations
from .login.plugin import setup_login
from .long_running_tasks import setup_long_running_tasks
from .meta_modeling.plugin import setup_meta_modeling
from .notifications.plugin import setup_notifications
from .payments.plugin import setup_payments
from .products.plugin import setup_products
from .projects.plugin import setup_projects
from .publications.plugin import setup_publications
from .rabbitmq import setup_rabbitmq
from .redis import setup_redis
from .resource_manager.plugin import setup_resource_manager
from .resource_usage.plugin import setup_resource_tracker
from .rest.plugin import setup_rest
from .scicrunch.plugin import setup_scicrunch
from .security.plugin import setup_security
from .session.plugin import setup_session
from .socketio.plugin import setup_socketio
from .statics.plugin import setup_statics
from .storage.plugin import setup_storage
from .studies_dispatcher.plugin import setup_studies_dispatcher
from .tags.plugin import setup_tags
from .tracing import setup_app_tracing
from .users.plugin import setup_users
from .version_control.plugin import setup_version_control
from .wallets.plugin import setup_wallets

_logger = logging.getLogger(__name__)


async def _welcome_banner(app: web.Application):
    settings = get_application_settings(app)
    print(WELCOME_MSG, flush=True)  # noqa: T201
    if settings.WEBSERVER_GARBAGE_COLLECTOR:
        print("with", WELCOME_GC_MSG, flush=True)  # noqa: T201
    if settings.WEBSERVER_DB_LISTENER:
        print("with", WELCOME_DB_LISTENER_MSG, flush=True)  # noqa: T201


async def _finished_banner(app: web.Application):
    assert app  # nosec
    print(info.get_finished_banner(), flush=True)  # noqa: T201


def create_application() -> web.Application:
    """
    Initializes service
    """
    app = create_safe_application()
    setup_settings(app)

    # WARNING: setup order matters
    # NOTE: compute setup order https://github.com/ITISFoundation/osparc-simcore/issues/1142

    # core modules
    setup_app_tracing(app)  # WARNING: must be UPPERMOST middleware
    setup_db(app)
    setup_long_running_tasks(app)
    setup_redis(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_rabbitmq(app)

    # front-end products
    setup_products(app)
    setup_statics(app)

    # users
    setup_users(app)
    setup_groups(app)

    # resource tracking / billing
    setup_resource_tracker(app)
    setup_payments(app)
    setup_wallets(app)

    # monitoring
    setup_diagnostics(app)
    setup_activity(app)
    setup_notifications(app)
    setup_socketio(app)
    setup_db_listener(app)
    setup_profiling_middleware(app)

    # login
    setup_email(app)
    setup_invitations(app)
    setup_login(app)
    setup_api_keys(app)

    # interaction with other backend services
    setup_director_v2(app)
    setup_dynamic_scheduler(app)
    setup_storage(app)
    setup_catalog(app)

    # resource management
    setup_resource_manager(app)
    setup_garbage_collector(app)

    # projects
    setup_projects(app)
    # project add-ons
    setup_version_control(app)
    setup_meta_modeling(app)

    # tagging
    setup_scicrunch(app)
    setup_tags(app)

    setup_announcements(app)
    setup_publications(app)
    setup_studies_dispatcher(app)
    setup_exporter(app)
    setup_clusters(app)

    # NOTE: *last* events
    app.on_startup.append(_welcome_banner)
    app.on_shutdown.append(_finished_banner)

    _logger.debug("Routes in app: \n %s", pformat(app.router.named_resources()))

    return app


def run_service(app: web.Application, config: dict[str, Any]):
    web.run_app(
        app,
        host=config["main"]["host"],
        port=config["main"]["port"],
        # this gets overriden by the gunicorn config in /docker/boot.sh
        access_log_format='%a %t "%r" %s %b --- [%Dus] "%{Referer}i" "%{User-Agent}i"',
    )


__all__: tuple[str, ...] = (
    "create_application",
    "run_service",
)
