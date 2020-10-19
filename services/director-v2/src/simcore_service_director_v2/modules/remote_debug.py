""" Setup remote debugger with Python Tools for Visual Studio (PTVSD)

"""
import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)

REMOTE_DEBUG_PORT = 3000


def setup(app: FastAPI):
    def on_startup() -> None:
        try:
            logger.debug("Enabling attach ptvsd ...")
            #
            # SEE https://github.com/microsoft/ptvsd#enabling-debugging
            #
            import ptvsd

            ptvsd.enable_attach(
                address=("0.0.0.0", REMOTE_DEBUG_PORT),  # nosec
            )  # nosec
        except ImportError as err:
            raise ValueError(
                "Cannot enable remote debugging. Please install ptvsd first"
            ) from err

        logger.info("Remote debugging enabled: listening port %s", REMOTE_DEBUG_PORT)

    app.add_event_handler("startup", on_startup)
