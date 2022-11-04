import logging
import os
import socket
from dataclasses import dataclass, field
from typing import Optional

import aio_pika
from settings_library.rabbit import RabbitSettings

log = logging.getLogger(__name__)


async def _get_connection(
    rabbit_broker: str, connection_name: str
) -> aio_pika.abc.AbstractRobustConnection:
    url = f"{rabbit_broker}?name={__name__}_{socket.gethostname()}_{os.getpid()}"
    return await aio_pika.connect_robust(
        url, client_properties={"connection_name": connection_name}
    )


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

    async def consume(self, queue_name: str) -> None:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel
            await channel.set_qos(10)

            queue = await channel.declare_queue(
                queue_name,
                durable=False,
                auto_delete=False,
            )

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    log.debug("Message received: %s", message)
                    await message.ack()

    async def publish(self, queue_name: str) -> None:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel

            queue = await channel.declare_queue(
                queue_name,
                durable=False,
                auto_delete=False,
            )

            await channel.default_exchange.publish(
                aio_pika.Message(("Channel: %r" % channel).encode()),
                routing_key=queue.name,
            )
