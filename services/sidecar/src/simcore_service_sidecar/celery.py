from celery.signals import worker_ready, worker_shutting_down

from .celery_configurator import create_celery_app
from .celery_log_setup import get_task_logger
from .celery_task_utils import cancel_task
from .cli import run_sidecar
from .remote_debug import setup_remote_debugging

setup_remote_debugging()

app = create_celery_app()

log = get_task_logger(__name__)


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
    cancel_task(run_sidecar)


@worker_ready.connect
def worker_ready_handler(*args, **kwargs):  # pylint: disable=unused-argument
    log.info("!!!!!!!!!!!!!! Worker is READY now !!!!!!!!!!!!!!!!!!")


__all__ = ["app"]
