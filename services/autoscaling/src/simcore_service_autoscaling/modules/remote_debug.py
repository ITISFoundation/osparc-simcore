""" Setup remote debugger with Python Tools for Visual Studio (PTVSD)

"""
import logging

from fastapi import FastAPI
from simcore_service_autoscaling.core.settings import get_application_settings

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    remote_debug_port = get_application_settings(app).AUTOSCALING_REMOTE_DEBUG_PORT

    def on_startup() -> None:
        try:
            logger.debug("Enabling attach ptvsd ...")
            #
            # SEE https://github.com/microsoft/ptvsd#enabling-debugging
            #
            import ptvsd

            ptvsd.enable_attach(
                address=("0.0.0.0", remote_debug_port),  # nosec  # noqa: S104
            )  # nosec
        except ImportError as err:
            msg = "Cannot enable remote debugging. Please install ptvsd first"
            raise RuntimeError(msg) from err

        logger.info("Remote debugging enabled: listening port %s", remote_debug_port)

    app.add_event_handler("startup", on_startup)
