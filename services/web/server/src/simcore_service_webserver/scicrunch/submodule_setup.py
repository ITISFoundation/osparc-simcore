"""
    Notice that this is used as a submodule of groups'a app module
"""
import logging

from aiohttp import web
from pydantic import ValidationError
from simcore_service_webserver.session_settings import assert_valid_config

from .service_client import SciCrunch
from .settings import assert_valid_config

logger = logging.getLogger(__name__)


def setup_scicrunch_submodule(app: web.Application):
    try:
        # TODO: tmp
        settings = assert_valid_config(app)
        #
        api = SciCrunch.acquire_instance(app, settings)
        assert api == SciCrunch.get_instance(app)  # nosec

    except ValidationError as err:
        logger.warning(
            "Failed to setup interface with K-Core. This functionality will not be available: %s",
            err,
        )
