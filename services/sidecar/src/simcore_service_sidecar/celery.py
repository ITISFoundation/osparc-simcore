from celery.signals import worker_shutting_down

from .celery_configurator import get_rabbitmq_config_and_celery_app
from .celery_log_setup import get_task_logger
from .celery_task_utils import cancel_task
from .cli import run_sidecar
from .remote_debug import setup_remote_debugging

setup_remote_debugging()

rabbit_config, app = get_rabbitmq_config_and_celery_app()

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


__all__ = ["rabbit_config", "app"]
