"""
Notice that this is used as a submodule of groups'a app module
"""

import logging

from aiohttp import web
from conftest import app
from simcore_service_webserver.scicrunch._repository import ScicrunchResourcesRepository

from ..application_setup import ModuleCategory, app_setup_func
from ._service import ScicrunchResourcesService
from .scicrunch_service import SCICRUNCH_SERVICE_APPKEY
from .service_client import SciCrunch
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


async def _on_startup(app: web.Application):
    settings = get_plugin_settings(app)

    client = SciCrunch.acquire_instance(app, settings)
    assert client == SciCrunch.get_instance(app)  # nosec

    service = ScicrunchResourcesService(
        repo=ScicrunchResourcesRepository.create_from_app(app),
        client=SciCrunch.get_instance(app),
    )

    app[SCICRUNCH_SERVICE_APPKEY] = service


@app_setup_func(
    "simcore_service_webserver.scicrunch",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_SCICRUNCH",
    logger=_logger,
)
def setup_scicrunch(app: web.Application):
    assert get_plugin_settings(app)  # nosec

    app.on_startup.append(_on_startup)
