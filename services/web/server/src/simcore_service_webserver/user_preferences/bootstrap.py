import logging

from aiohttp import web

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import ensure_single_setup
from ..rabbitmq import setup_rabbitmq
from ._controller import rpc
from ._controller.rest import user_preferences_rest
from ._models import overwrite_user_preferences_defaults

_logger = logging.getLogger(__name__)


@ensure_single_setup(__name__, logger=_logger)
def setup_user_preferences_feature(app: web.Application):
    overwrite_user_preferences_defaults(app)
    app.router.add_routes(user_preferences_rest.routes)

    setup_rabbitmq(app)
    if app[APP_SETTINGS_APPKEY].WEBSERVER_RABBITMQ:
        app.on_startup.append(rpc.register_rpc_routes_on_startup)
