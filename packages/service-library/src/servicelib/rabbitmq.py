import asyncio
import logging
import os
import socket
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

import aio_pika
from servicelib.logging_utils import log_context
from settings_library.rabbit import RabbitSettings

log = logging.getLogger(__name__)


def _connection_close_callback(sender: Any, exc: Optional[BaseException]) -> None:
    if exc:
        if isinstance(exc, asyncio.CancelledError):
            log.info("Rabbit connection was cancelled")
        else:
            log.error(
                "Rabbit connection closed with exception from %s:%s",
                sender,
                exc,
            )


def _channel_close_callback(sender: Any, exc: Optional[BaseException]) -> None:
    if exc:
        if isinstance(exc, asyncio.CancelledError):
            log.info("Rabbit channel was cancelled")
        else:
            log.error(
                "Rabbit channel closed with exception from %s:%s",
                sender,
                exc,
            )


async def _get_connection(
    rabbit_broker: str, connection_name: str
) -> aio_pika.abc.AbstractRobustConnection:
    # NOTE: to show the connection name in the rabbitMQ UI see there
    # https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url
    #
    url = f"{rabbit_broker}?name={connection_name}_{socket.gethostname()}_{os.getpid()}"
    connection = await aio_pika.connect_robust(
        url, client_properties={"connection_name": connection_name}
    )
    connection.close_callbacks.add(_connection_close_callback)
    return connection


MessageHandler = Callable[[Any], Awaitable[bool]]
Message = str


@dataclass
class RabbitMQClient:
    client_name: str
    settings: RabbitSettings
    _connection_pool: Optional[aio_pika.pool.Pool] = field(init=False, default=None)
    _channel_pool: Optional[aio_pika.pool.Pool] = field(init=False, default=None)

    def __post_init__(self):
        self._connection_pool = aio_pika.pool.Pool(
            _get_connection, self.settings.dsn, self.client_name, max_size=2
        )
        self._channel_pool = aio_pika.pool.Pool(self.get_channel, max_size=10)

    async def close(self) -> None:
        with log_context(log, logging.INFO, msg="Closing connection to RabbitMQ"):
            assert self._channel_pool  # nosec
            await self._channel_pool.close()
            assert self._connection_pool  # nosec
            await self._connection_pool.close()

    async def get_channel(self) -> aio_pika.abc.AbstractChannel:
        assert self._connection_pool  # nosec
        async with self._connection_pool.acquire() as connection:
            connection: aio_pika.RobustConnection
            channel = await connection.channel()
            channel.close_callbacks.add(_channel_close_callback)
            return channel

    async def consume(
        self, exchange_name: str, message_handler: MessageHandler
    ) -> aio_pika.abc.ConsumerTag:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel
            await channel.set_qos(10)

            exchange = await channel.declare_exchange(
                exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
            )

            # NOTE: durable=True makes the queue persistent between RabbitMQ restarts/crashes
            # consumer/publisher must set the same configuration for same queue
            # exclusive means that the queue is only available for THIS very client
            queue = await channel.declare_queue(durable=True, exclusive=True)
            # TODO: do we need this? arguments={"x-message-ttl": 60000},
            await queue.bind(exchange)

            async def _on_message(
                message: aio_pika.abc.AbstractIncomingMessage,
            ) -> None:
                async with message.process(requeue=True):
                    with log_context(
                        log, logging.DEBUG, msg=f"Message received {message}"
                    ):
                        if not await message_handler(message.body):
                            await message.nack()

            tag = await queue.consume(_on_message)
        return tag

    async def publish(self, exchange_name: str, message: Message) -> None:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel

            exchange = await channel.declare_exchange(
                exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
            )

            await exchange.publish(
                aio_pika.Message(message.encode()),
                routing_key="info",
            )
