import logging

from celery import Celery
from celery.utils.log import get_task_logger

from simcore_sdk.config.rabbit import Config as RabbitConfig

# TODO: configure via command line or config file. Add in config.yaml
logging.basicConfig(level=logging.DEBUG)

_LOGGER = get_task_logger(__name__)
_LOGGER.setLevel(logging.DEBUG)


rabbit_config = RabbitConfig()

# TODO: make it a singleton?
app= Celery(rabbit_config.name,
    broker=rabbit_config.broker,
    backend=rabbit_config.backend)




__all__ = [
    "rabbit_config",
    "app"
]
