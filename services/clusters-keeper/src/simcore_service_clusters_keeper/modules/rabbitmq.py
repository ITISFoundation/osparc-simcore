import contextlib
import logging
from typing import cast

from fastapi import FastAPI
from models_library.rabbitmq_messages import RabbitMessageBase
from servicelib.logging_utils import log_catch
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings

from ..core.errors import ConfigurationError

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.rabbitmq_client = None
        settings: RabbitSettings | None = app.state.settings.clusters_keeper_RABBITMQ
        if not settings:
            logger.warning("Rabbit MQ client is de-activated in the settings")
            return
        await wait_till_rabbitmq_responsive(settings.dsn)
        app.state.rabbitmq_client = RabbitMQClient(
            client_name="clusters_keeper", settings=settings
        )

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not app.state.rabbitmq_client:
        raise ConfigurationError(
            msg="RabbitMQ client is not available. Please check the configuration."
        )
    return cast(RabbitMQClient, app.state.rabbitmq_client)


async def post_message(app: FastAPI, message: RabbitMessageBase) -> None:
    with log_catch(logger, reraise=False), contextlib.suppress(ConfigurationError):
        # NOTE: if rabbitmq was not initialized the error does not need to flood the logs
        await get_rabbitmq_client(app).publish(message.channel_name, message)
