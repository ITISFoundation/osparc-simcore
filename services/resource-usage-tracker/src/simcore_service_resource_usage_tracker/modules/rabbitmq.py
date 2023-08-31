import logging
from typing import cast

from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQClient, wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings

from ..core.errors import ConfigurationError

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.rabbitmq_client = None
        settings: RabbitSettings | None = (
            app.state.settings.RESOURCE_USAGE_TRACKER_RABBITMQ
        )
        if not settings:
            raise ConfigurationError(
                msg="Rabbit MQ client is de-activated in the settings"
            )
        await wait_till_rabbitmq_responsive(settings.dsn)
        app.state.rabbitmq_client = RabbitMQClient(
            client_name="resource-usage-tracker", settings=settings
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
