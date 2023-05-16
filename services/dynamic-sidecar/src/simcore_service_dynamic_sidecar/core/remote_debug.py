""" Setup remote debugger with Python Tools for Visual Studio (PTVSD)

"""
import logging

from fastapi import FastAPI

from .settings import ApplicationSettings

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings

    def on_startup() -> None:
        try:
            logger.debug("Enabling attach ptvsd ...")
            #
            # SEE https://github.com/microsoft/ptvsd#enabling-debugging
            #
            # pylint: disable=import-outside-toplevel
            import ptvsd

            ptvsd.enable_attach(
                address=(
                    settings.DYNAMIC_SIDECAR_HOST,
                    settings.DYNAMIC_SIDECAR_REMOTE_DEBUG_PORT,
                )
            )

        except ImportError as err:
            raise ValueError(
                "Cannot enable remote debugging. Please install ptvsd first"
            ) from err

        logger.info(
            "Remote debugging enabled: listening port %s",
            settings.DYNAMIC_SIDECAR_REMOTE_DEBUG_PORT,
        )

    app.add_event_handler("startup", on_startup)
