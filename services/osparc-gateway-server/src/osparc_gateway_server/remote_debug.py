""" Setup remote debugger with debugpy - a debugger for Python
    https://github.com/microsoft/debugpy

"""
import logging


def setup_remote_debugging(logger: logging.Logger) -> None:
    try:
        logger.debug("Attaching debugpy ...")

        import debugpy

        REMOTE_DEBUGGING_PORT = 3000
        debugpy.listen(("0.0.0.0", REMOTE_DEBUGGING_PORT))
        # debugpy.wait_for_client()

    except ImportError as err:
        raise RuntimeError(
            "Cannot enable remote debugging. Please install debugpy first"
        ) from err

    logger.info("Remote debugging enabled: listening port %s", REMOTE_DEBUGGING_PORT)
