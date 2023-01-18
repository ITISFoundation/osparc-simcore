import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .garbage_collector_settings import get_plugin_settings
from .garbage_collector_task import run_background_task
from .garbage_collector_tasks_api_keys import create_background_task_to_prune_api_keys
from .garbage_collector_tasks_users import create_background_task_for_trial_accounts
from .login.plugin import setup_login_storage
from .projects.plugin import setup_projects_db, setup_projects_model_schema
from .socketio.plugin import setup_socketio_server

logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_GARBAGE_COLLECTOR",
    logger=logger,
)
def setup_garbage_collector(app: web.Application):

    # TODO: review these partial inits! project-api is code smell!!

    ## needs a partial init of projects plugin since this plugin uses projects-api
    # - project-api needs access to db
    setup_projects_db(app)
    # - projects-api needs access to schema
    setup_projects_model_schema(app)
    # - project needs access to socketio via notify_project_state_update
    setup_socketio_server(app)
    # - project needs access to user-api that is connected to login plugin
    setup_login_storage(app)

    settings = get_plugin_settings(app)

    app.cleanup_ctx.append(run_background_task)

    # NOTE: scaling web-servers will lead to having multiple tasks upgrading the db
    # not a huge deal. Instead this task runs in the GC.
    # If more tasks of this nature are needed, we should setup some sort of registration mechanism
    # with a interface such that plugins can pass tasks to the GC plugin to handle them
    interval_s = settings.GARBAGE_COLLECTOR_EXPIRED_USERS_CHECK_INTERVAL_S
    app.cleanup_ctx.append(create_background_task_for_trial_accounts(interval_s))

    # SEE https://github.com/ITISFoundation/osparc-issues/issues/705
    wait_period_s = settings.GARBAGE_COLLECTOR_PRUNE_APIKEYS_INTERVAL_S
    app.cleanup_ctx.append(create_background_task_to_prune_api_keys(wait_period_s))
