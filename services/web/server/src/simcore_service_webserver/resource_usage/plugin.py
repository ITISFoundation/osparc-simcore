"""Resource tracking service"""

import logging

from aiohttp import web

from ..application_keys import APP_SETTINGS_APPKEY
from ..application_setup import ModuleCategory, app_setup_func
from ..rabbitmq import setup_rabbitmq
from ..wallets.plugin import setup_wallets
from . import _pricing_plans_admin_rest, _pricing_plans_rest, _service_runs_rest
from ._observer import setup_resource_usage_observer_events

_logger = logging.getLogger(__name__)


@app_setup_func(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_RESOURCE_USAGE_TRACKER",
    depends=["simcore_service_webserver.rest"],
    logger=_logger,
)
def setup_resource_tracker(app: web.Application):
    assert app[APP_SETTINGS_APPKEY].WEBSERVER_RESOURCE_USAGE_TRACKER  # nosec

    setup_rabbitmq(app)
    setup_wallets(app)
    setup_resource_usage_observer_events(app)

    app.router.add_routes(_service_runs_rest.routes)
    app.router.add_routes(_pricing_plans_rest.routes)
    app.router.add_routes(_pricing_plans_admin_rest.routes)
