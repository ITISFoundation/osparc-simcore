"""users management subsystem"""

import logging
from typing import Final

from aiohttp import web
from servicelib.aiohttp.observer import setup_observer_registry

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import ModuleCategory, app_setup_func
from ..user_notifications.bootstrap import (
    setup_user_notification_feature,
)
from ..user_preferences.bootstrap import setup_user_preferences_feature
from ..user_tokens.bootstrap import setup_user_tokens_feature
from ._controller.rest import accounts_rest, users_rest

_logger = logging.getLogger(__name__)

APP_USERS_CLIENT_KEY: Final = web.AppKey("APP_USERS_CLIENT_KEY", object)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_USERS",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_users(app: web.Application):
    assert app[APP_SETTINGS_APPKEY].WEBSERVER_USERS  # nosec
    setup_observer_registry(app)

    app.router.add_routes(users_rest.routes)
    app.router.add_routes(accounts_rest.routes)

    setup_user_notification_feature(app)
    setup_user_preferences_feature(app)
    setup_user_tokens_feature(app)
