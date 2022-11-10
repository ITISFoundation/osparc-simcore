import logging
from dataclasses import dataclass

from fastapi import FastAPI
from models_library.rabbitmq_messages import (
    InstrumentationRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessage,
    RabbitMessageTypes,
)
from servicelib.rabbitmq import RabbitMQClient as BaseRabbitMQClient
from servicelib.rabbitmq_utils import wait_till_rabbitmq_responsive
from settings_library.rabbit import RabbitSettings

from ..core.errors import ConfigurationError

logger = logging.getLogger(__name__)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.rabbitmq_client = await RabbitMQClient.create(app)

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


_MESSAGE_TO_EXCHANGE_MAP = [
    (LoggerRabbitMessage, "log"),
    (ProgressRabbitMessage, "progress"),
    (InstrumentationRabbitMessage, "instrumentation"),
]


@dataclass
class RabbitMQClient(BaseRabbitMQClient):
    app: FastAPI

    @classmethod
    async def create(cls, app: FastAPI) -> "RabbitMQClient":
        settings: RabbitSettings = app.state.settings.DIRECTOR_V2_RABBITMQ
        await wait_till_rabbitmq_responsive(settings.dsn)

        return cls(app=app, client_name="director-v2", settings=settings)

    @classmethod
    def instance(cls, app: FastAPI) -> "RabbitMQClient":
        if not hasattr(app.state, "rabbitmq_client"):
            raise ConfigurationError(
                "RabbitMQ client is not available. Please check the configuration."
            )
        return app.state.rabbitmq_client

    async def publish_message(
        self,
        message: RabbitMessageTypes,
    ) -> None:
        def _get_exchange(message) -> str:
            for message_type, exchange_name in _MESSAGE_TO_EXCHANGE_MAP:
                if isinstance(message, message_type):
                    return exchange_name

            raise ValueError(f"message '{message}' type is of incorrect type")

        exchange = _get_exchange(message)
        await self.publish(self.settings.RABBIT_CHANNELS[exchange], message.json())
