""" Setup remote debugger with Python Tools for Visual Studio (PTVSD)

"""
import logging
import os

REMOTE_DEBUG_PORT = 3000

log = logging.getLogger(__name__)


def setup_remote_debugging(force_enabled=False, *, boot_mode=None):
    """
        Programaticaly enables remote debugging if SC_BOOT_MODE==debug-ptvsd
    """
    boot_mode = boot_mode or os.environ.get("SC_BOOT_MODE")
    if boot_mode == "debug-ptvsd" or force_enabled:
        try:
            log.debug("Enabling attach ptvsd ...")
            #
            # SEE https://github.com/microsoft/ptvsd#enabling-debugging
            #
            import ptvsd

            ptvsd.enable_attach(
                address=("0.0.0.0", REMOTE_DEBUG_PORT), redirect_output=True  # nosec
            )  # nosec
        except ImportError:
            raise ValueError(
                "Cannot enable remote debugging. Please install ptvsd first"
            )

        log.info("Remote debugging enabled: listening port %s", REMOTE_DEBUG_PORT)
    else:
        log.debug("Booting without remote debugging since SC_BOOT_MODE=%s", boot_mode)


__all__ = ["setup_remote_debugging"]
