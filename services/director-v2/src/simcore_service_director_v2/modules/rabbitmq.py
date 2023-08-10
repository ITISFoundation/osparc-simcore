import logging
from typing import cast

from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings

from ..core.errors import ConfigurationError

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: RabbitSettings = app.state.settings.DIRECTOR_V2_RABBITMQ
        await wait_till_rabbitmq_responsive(settings.dsn)
        app.state.rabbitmq_client = RabbitMQClient(
            client_name="director-v2", settings=settings
        )

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_rabbitmq_client(app: FastAPI) -> RabbitMQClient:
    if not hasattr(app.state, "rabbitmq_client"):
        msg = "RabbitMQ client is not available. Please check the configuration."
        raise ConfigurationError(msg)
    return cast(RabbitMQClient, app.state.rabbitmq_client)
