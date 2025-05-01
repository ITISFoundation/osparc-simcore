import contextlib
import logging
from typing import cast

import distributed
from models_library.rabbitmq_messages import RabbitMessageBase
from servicelib.logging_utils import log_catch
from servicelib.rabbitmq import RabbitMQClient, wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings

from .errors import ConfigurationError

logger = logging.getLogger(__name__)


async def on_startup(
    worker: distributed.Worker, rabbit_settings: RabbitSettings
) -> None:
    worker.rabbitmq_client = None
    settings: RabbitSettings | None = rabbit_settings
    if not settings:
        logger.warning("Rabbit MQ client is de-activated in the settings")
        return
    await wait_till_rabbitmq_responsive(settings.dsn)
    worker.rabbitmq_client = RabbitMQClient(
        client_name="dask-sidecar", settings=settings
    )


async def on_shutdown(worker: distributed.Worker) -> None:
    if worker.rabbitmq_client:
        await worker.rabbitmq_client.close()


def get_rabbitmq_client(worker: distributed.Worker) -> RabbitMQClient:
    if not worker.rabbitmq_client:
        raise ConfigurationError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    return cast(RabbitMQClient, worker.rabbitmq_client)


async def post_message(worker: distributed.Worker, message: RabbitMessageBase) -> None:
    with log_catch(logger, reraise=False), contextlib.suppress(ConfigurationError):
        # NOTE: if rabbitmq was not initialized the error does not need to flood the logs
        await get_rabbitmq_client(worker).publish(message.channel_name, message)
