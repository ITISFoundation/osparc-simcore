""" Setup remote debugger with Python Tools for Visual Studio (PTVSD)

"""
import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup(app: FastAPI):
    remote_debug_port = app.state.settings.DIRECTOR_V2_REMOTE_DEBUG_PORT

    def on_startup() -> None:
        try:
            logger.debug("Enabling attach ptvsd ...")
            #
            # SEE https://github.com/microsoft/ptvsd#enabling-debugging
            #
            import ptvsd

            ptvsd.enable_attach(
                address=("0.0.0.0", remote_debug_port),  # nosec
            )  # nosec
        except ImportError as err:
            raise RuntimeError(
                "Cannot enable remote debugging. Please install ptvsd first"
            ) from err

        logger.info("Remote debugging enabled: listening port %s", remote_debug_port)

    app.add_event_handler("startup", on_startup)
