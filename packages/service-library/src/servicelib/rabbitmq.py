import logging
import os
import socket
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

import aio_pika
from servicelib.logging_utils import log_context
from settings_library.rabbit import RabbitSettings

log = logging.getLogger(__name__)


async def _get_connection(
    rabbit_broker: str, connection_name: str
) -> aio_pika.abc.AbstractRobustConnection:
    url = f"{rabbit_broker}?name={__name__}_{socket.gethostname()}_{os.getpid()}"
    return await aio_pika.connect_robust(
        url, client_properties={"connection_name": connection_name}
    )


MessageHandler = Callable[[Any], Awaitable[bool]]


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
        assert self._channel_pool  # nosec
        await self._channel_pool.close()
        assert self._connection_pool  # nosec
        await self._connection_pool.close()

    async def get_channel(self) -> aio_pika.abc.AbstractChannel:
        assert self._connection_pool  # nosec
        async with self._connection_pool.acquire() as connection:
            connection: aio_pika.RobustConnection
            return await connection.channel()

    async def consume(self, queue_name: str, message_handler: MessageHandler) -> None:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel
            await channel.set_qos(10)

            # NOTE: durable=True makes the queue persistent between RabbitMQ restarts/crashes
            # consumer/publisher must set the same configuration for same queue
            queue = await channel.declare_queue(
                queue_name,
                durable=False,
            )

            async def _on_message(
                message: aio_pika.abc.AbstractIncomingMessage,
            ) -> None:
                async with message.process(requeue=True):
                    with log_context(
                        log, logging.DEBUG, msg=f"Message received {message}"
                    ):
                        if not await message_handler(message.body.decode()):
                            await message.nack()

            await queue.consume(_on_message)

    async def publish(self, queue_name: str, message: str) -> None:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel

            queue = await channel.declare_queue(
                queue_name,
                durable=False,
            )

            await channel.default_exchange.publish(
                aio_pika.Message(message.encode()),
                routing_key=queue.name,
            )
