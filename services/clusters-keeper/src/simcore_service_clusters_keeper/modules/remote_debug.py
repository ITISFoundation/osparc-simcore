""" Setup remote debugger with debugpy - a debugger for Python
    https://github.com/microsoft/debugpy

"""
import logging

from fastapi import FastAPI

_logger = logging.getLogger(__name__)
_REMOTE_DEBUGGING_PORT = 3000


def setup_remote_debugging(app: FastAPI) -> None:
    def on_startup() -> None:
        try:
            _logger.debug("Attaching debugpy ...")

            import debugpy

            debugpy.listen(("0.0.0.0", _REMOTE_DEBUGGING_PORT))  # nosec  # noqa: S104

        except ImportError as err:
            msg = "Cannot enable remote debugging. Please install debugpy first"
            raise RuntimeError(msg) from err

        _logger.info(
            "Remote debugging enabled: listening port %s", _REMOTE_DEBUGGING_PORT
        )

    app.add_event_handler("startup", on_startup)
