""" Setup remote debugger with Python Tools for Visual Studio (PTVSD)

"""
import os

from .celery_log_setup import get_task_logger

log = get_task_logger(__name__)


def setup_remote_debugging(force_enabled=False):
    """ Programaticaly enables remote debugging if SC_BOOT_MODE==debug-ptvsd

    """
    boot_mode = os.environ["SC_BOOT_MODE"]

    if boot_mode == "debug-ptvsd" or force_enabled:
        try:
            log.debug("Enabling attach ptvsd ...")
            #
            # SEE https://github.com/microsoft/ptvsd#enabling-debugging
            #
            import ptvsd
            ptvsd.enable_attach(address=('0.0.0.0', 3000), redirect_output=True)

        except ImportError:
            log.exception("Unable to use remote debugging. ptvsd is not installed")

        else:
            log.info("Remote debugging enabled")
    else:
        log.debug("Booting without remote debugging since SC_BOOT_MODE=%s", boot_mode)


__all__ = [
    'setup_remote_debugging'
]
