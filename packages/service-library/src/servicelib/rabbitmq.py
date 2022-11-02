import os
import socket
from dataclasses import dataclass

import aio_pika
from settings_library.rabbit import RabbitSettings


async def _get_connection(
    rabbit_broker: str, connection_name: str
) -> aio_pika.abc.AbstractRobustConnection:
    url = f"{rabbit_broker}?name={__name__}_{socket.gethostname()}_{os.getpid()}"
    return await aio_pika.connect_robust(
        url, client_properties={"connection_name": connection_name}
    )


@dataclass
class RabbitMQClient:
    settings: RabbitSettings
    _connection_pool: aio_pika.pool.Pool
    _channel_pool: aio_pika.pool.Pool

    def __post_init__(self):
        self._connection_pool = aio_pika.pool.Pool(_get_connection, max_size=2)
        self._channel_pool = aio_pika.pool.Pool(self.get_channel, max_size=10)

    async def get_channel(self) -> aio_pika.abc.AbstractChannel:
        async with self._connection_pool.acquire() as connection:
            connection: aio_pika.RobustConnection
            return await connection.channel()

    async def consume(self, queue_name: str) -> None:
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
                    print(message)
                    await message.ack()

    async def publish(self, queue_name: str) -> None:
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel
            await channel.default_exchange.publish(
                aio_pika.Message(("Channel: %r" % channel).encode()),
                queue_name,
            )
