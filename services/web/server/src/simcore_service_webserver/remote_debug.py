""" Setup remote debugger with Python Tools for Visual Studio (PTVSD)

"""
import logging

from aiohttp import web
from models_library.basic_types import BootModeEnum
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ._constants import APP_SETTINGS_KEY
from .application_settings import ApplicationSettings

logger = logging.getLogger(__name__)

_REMOTE_DEBUGGING_PORT = 3000


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    settings_name="WEBSERVER_REMOTE_DEBUG",
    logger=logger,
    depends=[],
)
def setup_remote_debugging(app: web.Application):
    application_settings: ApplicationSettings = app[APP_SETTINGS_KEY]
    assert application_settings.WEBSERVER_REMOTE_DEBUG is True  # nosec

    if application_settings.SC_BOOT_MODE == BootModeEnum.DEBUG:
        try:
            logger.debug("Enabling attach ptvsd ...")
            #
            # SEE https://github.com/microsoft/ptvsd#enabling-debugging
            #
            import ptvsd

            ptvsd.enable_attach(
                address=("0.0.0.0", _REMOTE_DEBUGGING_PORT),  # nosec
            )
        except ImportError as err:
            raise ValueError(
                "Cannot enable remote debugging. Please install ptvsd first"
            ) from err

        logger.info(
            "Remote debugging enabled: listening port %s", _REMOTE_DEBUGGING_PORT
        )
