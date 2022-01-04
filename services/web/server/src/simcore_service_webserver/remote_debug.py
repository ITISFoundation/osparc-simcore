""" Setup remote debugger with Python Tools for Visual Studio (PTVSD)

"""
import logging

from aiohttp import web
from models_library.basic_types import BootModeEnum
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .constants import APP_SETTINGS_KEY
from .settings import ApplicationSettings

logger = logging.getLogger(__name__)


@app_module_setup(__name__, ModuleCategory.ADDON, logger=logger, depends=[])
def setup_remote_debugging(app: web.Application):
    application_settings: ApplicationSettings = app[APP_SETTINGS_KEY]
    assert application_settings.boot_mode  # nosec
    if application_settings.boot_mode == BootModeEnum.DEBUG:
        try:
            logger.debug("Enabling attach ptvsd ...")
            #
            # SEE https://github.com/microsoft/ptvsd#enabling-debugging
            #
            import ptvsd

            REMOTE_DEBUGGING_PORT = 3000
            ptvsd.enable_attach(
                address=("0.0.0.0", REMOTE_DEBUGGING_PORT),
            )
        except ImportError as err:
            raise Exception(
                "Cannot enable remote debugging. Please install ptvsd first"
            ) from err

        logger.info(
            "Remote debugging enabled: listening port %s", REMOTE_DEBUGGING_PORT
        )
