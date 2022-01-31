"""
    Notice that this is used as a submodule of groups'a app module
"""
import logging

from aiohttp import web
from pydantic import ValidationError

from .._constants import APP_SETTINGS_KEY
from .service_client import SciCrunch
from .settings import SciCrunchSettings

logger = logging.getLogger(__name__)


def setup_scicrunch_submodule(app: web.Application):
    try:
        settings: SciCrunchSettings = app[APP_SETTINGS_KEY].WEBSERVER_SCICRUNCH
        assert settings  # nosec
        api = SciCrunch.acquire_instance(app, settings)
        assert api == SciCrunch.get_instance(app)  # nosec

    except ValidationError as err:
        logger.warning(
            "Failed to setup interface with K-Core. This functionality will not be available: %s",
            err,
        )
