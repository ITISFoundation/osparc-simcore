import logging

from celery.signals import worker_ready, worker_shutting_down

from .__version__ import __version__
from .celery_configurator import create_celery_app
from .cli import run_sidecar
from .remote_debug import setup_remote_debugging
from .utils import cancel_task_by_fct_name

setup_remote_debugging()

app = create_celery_app()

log = logging.getLogger(__name__)

#
# SEE https://patorjk.com/software/taag/#p=display&h=0&f=Ogre&t=Celery-sidecar
#
WELCOME_MSG = r"""

   ___        _                                 _      _
  / __\  ___ | |  ___  _ __  _   _         ___ (_)  __| |  ___   ___   __ _  _ __
 / /    / _ \| | / _ \| '__|| | | | _____ / __|| | / _` | / _ \ / __| / _` || '__|
/ /___ |  __/| ||  __/| |   | |_| ||_____|\__ \| || (_| ||  __/| (__ | (_| || |
\____/  \___||_| \___||_|    \__, |       |___/|_| \__,_| \___| \___| \__,_||_|
                             |___/                                                 {0} - {1}
""".format(
    __version__, app.conf.osparc_sidecar_bootmode.value
)


@worker_shutting_down.connect
def worker_shutting_down_handler(
    # pylint: disable=unused-argument
    sig,
    how,
    exitcode,
    **kwargs
):
    # NOTE: this function shall be adapted when we switch to python 3.7+
    log.warning("detected worker_shutting_down signal(%s, %s, %s)", sig, how, exitcode)
    cancel_task_by_fct_name(run_sidecar.__name__)


@worker_ready.connect
def worker_ready_handler(*args, **kwargs):  # pylint: disable=unused-argument
    print(WELCOME_MSG, flush=True)


__all__ = ["app"]
