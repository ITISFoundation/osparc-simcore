""" Setup remote debugger with Python Tools for Visual Studio (PTVSD)

"""
import logging

logger = logging.getLogger(__name__)


def setup_remote_debugging():
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

    logger.info("Remote debugging enabled: listening port %s", REMOTE_DEBUGGING_PORT)
