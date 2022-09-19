""" users management subsystem

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.rest_routing import (
    get_handlers_from_namespace,
    iter_path_operations,
    map_handlers_with_operations,
)

from . import users_handlers
from ._constants import APP_OPENAPI_SPECS_KEY
from .users_bg_tasks import run_background_task_to_monitor_expiration_trial_accounts

logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_USERS",
    depends=["simcore_service_webserver.rest"],
    logger=logger,
)
def setup_users(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_USERS  # nosec

    # routes related with users
    specs = app[APP_OPENAPI_SPECS_KEY]
    routes = map_handlers_with_operations(
        get_handlers_from_namespace(users_handlers),
        filter(lambda o: "me" in o[1].split("/"), iter_path_operations(specs)),
        strict=True,
    )
    app.router.add_routes(routes)

    # NOTE: scaling web-servers will lead to having multiple tasks upgrading the db
    # not a huge deal but perhaps this task could be registered as a GC task and
    # run only when that service is active
    app.cleanup_ctx.append(run_background_task_to_monitor_expiration_trial_accounts)
