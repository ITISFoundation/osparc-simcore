""" Setup remote debugger with Python Tools for Visual Studio (PTVSD)

"""
import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup(app: FastAPI):
    API_SERVER_REMOTE_DEBUG_PORT = app.state.settings.API_SERVER_REMOTE_DEBUG_PORT

    def on_startup() -> None:
        try:
            logger.debug("Enabling attach ptvsd ...")
            #
            # SEE https://github.com/microsoft/ptvsd#enabling-debugging
            #
            import ptvsd

            ptvsd.enable_attach(
                address=("0.0.0.0", API_SERVER_REMOTE_DEBUG_PORT),  # nosec
            )  # nosec
        except ImportError as err:
            msg = "Cannot enable remote debugging. Please install ptvsd first"
            raise RuntimeError(msg) from err

        logger.info(
            "Remote debugging enabled: listening port %s", API_SERVER_REMOTE_DEBUG_PORT
        )

    app.add_event_handler("startup", on_startup)
