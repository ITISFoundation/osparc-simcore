import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.logging_utils import set_parent_module_log_level

from ..application_settings import get_application_settings
from ..login.plugin import setup_login_storage
from ..products.plugin import setup_products
from ..projects._projects_repository_legacy import setup_projects_db
from ..socketio.plugin import setup_socketio
from . import _tasks_api_keys, _tasks_core, _tasks_trash, _tasks_users
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.garbage_collector",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_GARBAGE_COLLECTOR",
    logger=_logger,
)
def setup_garbage_collector(app: web.Application) -> None:
    # for trashing
    setup_products(app)

    # - project-api needs access to db
    setup_projects_db(app)
    # - project needs access to socketio via notify_project_state_update
    setup_socketio(app)
    # - project needs access to user-api that is connected to login plugin
    setup_login_storage(app)

    settings = get_plugin_settings(app)

    app.cleanup_ctx.append(_tasks_core.create_background_task_for_garbage_collection())

    set_parent_module_log_level(
        _logger.name, min(logging.INFO, get_application_settings(app).log_level)
    )

    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/6592

    # NOTE: scaling web-servers will lead to having multiple tasks upgrading the db
    # not a huge deal. Instead this task runs in the GC.
    # If more tasks of this nature are needed, we should setup some sort of registration mechanism
    # with a interface such that plugins can pass tasks to the GC plugin to handle them
    interval_s = settings.GARBAGE_COLLECTOR_EXPIRED_USERS_CHECK_INTERVAL_S
    app.cleanup_ctx.append(
        _tasks_users.create_background_task_for_trial_accounts(interval_s)
    )

    # SEE https://github.com/ITISFoundation/osparc-issues/issues/705
    wait_period_s = settings.GARBAGE_COLLECTOR_PRUNE_APIKEYS_INTERVAL_S
    app.cleanup_ctx.append(
        _tasks_api_keys.create_background_task_to_prune_api_keys(wait_period_s)
    )

    # SEE https://github.com/ITISFoundation/osparc-issues#468
    app.cleanup_ctx.append(
        _tasks_trash.create_background_task_to_prune_trash(wait_period_s)
    )
