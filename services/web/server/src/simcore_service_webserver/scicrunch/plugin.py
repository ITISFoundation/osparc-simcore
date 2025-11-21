import logging

from aiohttp import web
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.scicrunch._repository import ScicrunchResourcesRepository

from ..application_setup import ModuleCategory, app_setup_func
from ._client import SciCrunch
from ._service import ScicrunchResourcesService
from .scicrunch_service import SCICRUNCH_SERVICE_APPKEY
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)


async def _on_startup(app: web.Application):
    settings = get_plugin_settings(app)

    # 1. scicrunch http client
    client = SciCrunch.acquire_instance(app, settings)
    assert client == SciCrunch.get_instance(app)  # nosec

    # 2. scicrunch repository (uses app[ENGINE_DB_CLIENT_APPKEY])
    repo = ScicrunchResourcesRepository.create_from_app(app)
    assert repo  # nosec

    # 3. scicrunch resources service
    service = ScicrunchResourcesService(
        repo=repo,
        client=client,
    )

    # store service in app
    app[SCICRUNCH_SERVICE_APPKEY] = service


@app_setup_func(
    "simcore_service_webserver.scicrunch",
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_SCICRUNCH",
    logger=_logger,
)
def setup_scicrunch(app: web.Application):
    assert get_plugin_settings(app)  # nosec

    setup_db(app)  # needs engine

    app.on_startup.append(_on_startup)
