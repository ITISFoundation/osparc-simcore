""" Setup remote debugger with Python Tools for Visual Studio (PTVSD)

"""
import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    settings = app.state.settings

    def on_startup() -> None:
        try:
            logger.debug("Enabling attach ptvsd ...")
            #
            # SEE https://github.com/microsoft/ptvsd#enabling-debugging
            #
            import ptvsd  # pylint: disable=import-outside-toplevel

            ptvsd.enable_attach(address=(settings.host, settings.remote_debug_port))

        except ImportError as err:
            raise Exception(
                "Cannot enable remote debugging. Please install ptvsd first"
            ) from err

        logger.info(
            "Remote debugging enabled: listening port %s", settings.remote_debug_port
        )

    app.add_event_handler("startup", on_startup)
