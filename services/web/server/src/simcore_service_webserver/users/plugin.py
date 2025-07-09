"""users management subsystem"""

import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.observer import setup_observer_registry
from simcore_service_webserver.users_tokens.plugin import setup_users_tokens

from . import _notifications_rest, _preferences_rest, _users_rest
from ._preferences_models import overwrite_user_preferences_defaults

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_USERS",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_users(app: web.Application):
    assert app[APP_SETTINGS_KEY].WEBSERVER_USERS  # nosec
    setup_observer_registry(app)
    overwrite_user_preferences_defaults(app)

    app.router.add_routes(_users_rest.routes)
    app.router.add_routes(_notifications_rest.routes)
    app.router.add_routes(_preferences_rest.routes)

    setup_users_tokens(app)
