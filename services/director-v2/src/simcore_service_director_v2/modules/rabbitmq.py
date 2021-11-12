import logging
from dataclasses import dataclass
from typing import Dict

import aio_pika
from fastapi import FastAPI
from models_library.rabbitmq_messages import (
    InstrumentationRabbitMessage,
    LoggerRabbitMessage,
    ProgressRabbitMessage,
    RabbitMessageTypes,
)
from settings_library.rabbit import RabbitSettings
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.wait import wait_random

from ..core.errors import ConfigurationError

logger = logging.getLogger(__name__)


rabbitmq_retry_policy = dict(
    wait=wait_random(5, 10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def setup(app: FastAPI) -> None:
    @retry(**rabbitmq_retry_policy)
    async def on_startup() -> None:
        app.state.rabbitmq_client = await RabbitMQClient.create(app)

    async def on_shutdown() -> None:
        if app.state.rabbitmq_client:
            await app.state.rabbitmq_client.delete()
            del app.state.rabbitmq_client  # type: ignore

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


_MESSAGE_TO_EXCHANGE_MAP = {
    LoggerRabbitMessage: "log",
    ProgressRabbitMessage: "progress",
    InstrumentationRabbitMessage: "instrumentation",
}


@dataclass
class RabbitMQClient:
    app: FastAPI
    connection: aio_pika.RobustConnection
    channel: aio_pika.RobustChannel
    exchanges: Dict[str, aio_pika.RobustExchange]

    @classmethod
    async def create(cls, app: FastAPI) -> "RabbitMQClient":
        settings: RabbitSettings = app.state.settings.CELERY.CELERY_RABBIT
        connection: aio_pika.RobustConnection = await aio_pika.connect_robust(
            settings.dsn + f"?name={__name__}_{id(app)}",
            client_properties={"connection_name": f"director-v2_{id(app)}"},
        )
        channel = await connection.channel()
        exchanges = {}
        for exchange_name in ["log", "progress", "instrumentation"]:
            exchanges[exchange_name] = await channel.declare_exchange(
                settings.RABBIT_CHANNELS[exchange_name], aio_pika.ExchangeType.FANOUT
            )

        return cls(app=app, connection=connection, channel=channel, exchanges=exchanges)

    @classmethod
    def instance(cls, app: FastAPI) -> "RabbitMQClient":
        if not hasattr(app.state, "rabbitmq_client"):
            raise ConfigurationError(
                "RabbitMQ client is not available. Please check the configuration."
            )
        return app.state.rabbitmq_client

    async def delete(self) -> None:
        await self.connection.close()

    async def publish_message(
        self,
        message: RabbitMessageTypes,
    ) -> None:
        def get_exchange(message) -> aio_pika.Exchange:
            for message_type, exchange_name in _MESSAGE_TO_EXCHANGE_MAP.items():
                if isinstance(message, message_type):
                    assert exchange_name in self.exchanges  # nosec
                    return self.exchanges[exchange_name]

            raise ValueError(f"message '{message}' type is of incorrect type")

        try:
            await get_exchange(message).publish(
                aio_pika.Message(message.json().encode(encoding="utf-8")),
                routing_key="",
            )
        except ValueError:
            logger.warning("Unsupported rabbit message sent:", exc_info=True)
