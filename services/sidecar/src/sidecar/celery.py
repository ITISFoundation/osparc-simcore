from celery import Celery
from simcore_sdk.config.rabbit import Config as RabbitConfig

from .celery_log_setup import get_task_logger
from .remote_debug import setup_remote_debugging

log = get_task_logger(__name__)
log.info("Inititalizing celery app ...")

rabbit_config = RabbitConfig()

setup_remote_debugging()

# TODO: make it a singleton?
app= Celery(rabbit_config.name,
    broker=rabbit_config.broker,
    backend=rabbit_config.backend)

__all__ = [
    "rabbit_config",
    "app"
]
