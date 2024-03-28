"""
    Notice that this is used as a submodule of groups'a app module
"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .service_client import SciCrunch
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


async def _on_startup(app: web.Application):
    settings = get_plugin_settings(app)
    api = SciCrunch.acquire_instance(app, settings)
    assert api == SciCrunch.get_instance(app)  # nosec


@app_module_setup(
    "simcore_service_webserver.scicrunch",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_SCICRUNCH",
    logger=_logger,
)
def setup_scicrunch(app: web.Application):
    assert get_plugin_settings(app)  # nosec

    app.on_startup.append(_on_startup)
