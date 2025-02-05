""" tags management subsystem

"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ..rabbitmq import setup_rabbitmq
from ..rest.plugin import setup_rest
from . import (
    _itis_vip_syncer_service,
    _licensed_items_checkouts_rest,
    _licensed_items_purchases_rest,
    _licensed_items_rest,
    _rpc,
)
from .settings import LicensesSettings, get_plugin_settings

_logger = logging.getLogger(__name__)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_LICENSES",
    logger=_logger,
)
def setup_licenses(app: web.Application):
    settings: LicensesSettings = get_plugin_settings(app)

    # routes
    setup_rest(app)
    app.router.add_routes(_licensed_items_rest.routes)
    app.router.add_routes(_licensed_items_purchases_rest.routes)
    app.router.add_routes(_licensed_items_checkouts_rest.routes)

    setup_rabbitmq(app)
    if app[APP_SETTINGS_KEY].WEBSERVER_RABBITMQ:
        app.on_startup.append(_rpc.register_rpc_routes_on_startup)

    if settings.LICENSES_ITIS_VIP_SYNCER_ENABLED and settings.LICENSES_ITIS_VIP:
        _itis_vip_syncer_service.setup_itis_vip_syncer(
            app,
            settings=settings.LICENSES_ITIS_VIP,
            resync_after=settings.LICENSES_ITIS_VIP_SYNCER_PERIODICITY,
        )
