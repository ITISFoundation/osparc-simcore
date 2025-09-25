"""users management subsystem"""

import logging
from typing import Final

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup
from servicelib.aiohttp.observer import setup_observer_registry

from ..user_notifications.bootstrap import (
    setup_user_notification_feature,
)
from ..user_preferences.bootstrap import setup_user_preferences_feature
from ..user_tokens.bootstrap import setup_user_tokens_feature
from ._controller.rest import accounts_rest, users_rest

_logger = logging.getLogger(__name__)

APP_USERS_CLIENT_KEY: Final = web.AppKey("APP_USERS_CLIENT_KEY", object)


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

    app.router.add_routes(users_rest.routes)
    app.router.add_routes(accounts_rest.routes)

    setup_user_notification_feature(app)
    setup_user_preferences_feature(app)
    setup_user_tokens_feature(app)
