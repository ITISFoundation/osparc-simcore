"""
    Notice that this is used as a submodule of groups'a app module
"""
import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .service_client import SciCrunch
from .settings import get_plugin_settings

logger = logging.getLogger(__name__)


@app_module_setup(
    "simcore_service_webserver.scicrunch",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_SCICRUNCH",
    logger=logger,
)
def setup_scicrunch(app: web.Application):
    settings = get_plugin_settings(app)

    # init client and injects in app
    api = SciCrunch.acquire_instance(app, settings)
    assert api == SciCrunch.get_instance(app)  # nosec
