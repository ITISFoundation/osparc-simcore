import asyncio
import logging
from dataclasses import dataclass, field
from typing import Final

import aio_pika

from ..logging_utils import log_context
from ._client_base import RabbitMQClientBase
from ._models import MessageHandler, RabbitMessage
from ._utils import declare_queue, get_rabbitmq_client_unique_name

_logger = logging.getLogger(__name__)


_DEFAULT_PREFETCH_VALUE: Final[int] = 10
_DEFAULT_RABBITMQ_EXECUTION_TIMEOUT_S: Final[int] = 5


@dataclass
class RabbitMQClient(RabbitMQClientBase):
    _connection_pool: aio_pika.pool.Pool | None = field(init=False, default=None)
    _channel_pool: aio_pika.pool.Pool | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        # recommendations are 1 connection per process
        self._connection_pool = aio_pika.pool.Pool(
            self._get_connection, self.settings.dsn, self.client_name, max_size=1
        )
        # channels are not thread safe, what about python?
        self._channel_pool = aio_pika.pool.Pool(self._get_channel, max_size=10)

    async def _get_connection(
        self, rabbit_broker: str, connection_name: str
    ) -> aio_pika.abc.AbstractRobustConnection:
        # NOTE: to show the connection name in the rabbitMQ UI see there
        # https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url
        #
        url = f"{rabbit_broker}?name={get_rabbitmq_client_unique_name(connection_name)}&heartbeat={self.heartbeat}"
        connection = await aio_pika.connect_robust(
            url,
            client_properties={"connection_name": connection_name},
            timeout=_DEFAULT_RABBITMQ_EXECUTION_TIMEOUT_S,
        )
        connection.close_callbacks.add(self._connection_close_callback)
        return connection

    async def close(self) -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg=f"{self.client_name} closing connection to RabbitMQ",
        ):
            assert self._channel_pool  # nosec
            await self._channel_pool.close()
            assert self._connection_pool  # nosec
            await self._connection_pool.close()

    async def _get_channel(self) -> aio_pika.abc.AbstractChannel:
        assert self._connection_pool  # nosec
        async with self._connection_pool.acquire() as connection:
            channel = await connection.channel()
            channel.close_callbacks.add(self._channel_close_callback)
            return channel

    async def _get_consumer_tag(self, exchange_name) -> str:
        return f"{get_rabbitmq_client_unique_name(self.client_name)}_{exchange_name}"

    async def subscribe(
        self,
        exchange_name: str,
        message_handler: MessageHandler,
        *,
        exclusive_queue: bool = True,
        topics: list[str] | None = None,
    ) -> str:
        """subscribe to exchange_name calling message_handler for every incoming message
        - exclusive_queue: True means that every instance of this application will receive the incoming messages
        - exclusive_queue: False means that only one instance of this application will reveice the incoming message

        specifying a topic will make the client declare a TOPIC type of RabbitMQ Exchange instead of FANOUT
        - a FANOUT exchange transmit messages to any connected queue regardless of the routing key
        - a TOPIC exchange transmit messages to any connected queue provided it is bound with the message routing key
          - topic = BIND_TO_ALL_TOPICS ("#") is equivalent to the FANOUT effect
          - a queue bound with topic "director-v2.*" will receive any message that uses a routing key such as "director-v2.event.service_started"
          - a queue bound with topic "director-v2.event.specific_event" will only receive messages with that exact routing key (same as DIRECT exchanges behavior)

        Raises:
            aio_pika.exceptions.ChannelPreconditionFailed: In case an existing exchange with different type is used
        Returns:
            queue name
        """

        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            qos_value = 1 if exclusive_queue is False else _DEFAULT_PREFETCH_VALUE
            await channel.set_qos(qos_value)

            exchange = await channel.declare_exchange(
                exchange_name,
                aio_pika.ExchangeType.FANOUT
                if topics is None
                else aio_pika.ExchangeType.TOPIC,
                durable=True,
                timeout=_DEFAULT_RABBITMQ_EXECUTION_TIMEOUT_S,
            )

            # NOTE: durable=True makes the queue persistent between RabbitMQ restarts/crashes
            # consumer/publisher must set the same configuration for same queue
            # exclusive means that the queue is only available for THIS very client
            # and will be deleted when the client disconnects
            queue = await declare_queue(
                channel,
                self.client_name,
                exchange_name,
                exclusive_queue=exclusive_queue,
            )
            if topics is None:
                await queue.bind(exchange, routing_key="")
            else:
                await asyncio.gather(
                    *(queue.bind(exchange, routing_key=topic) for topic in topics)
                )

            async def _on_message(
                message: aio_pika.abc.AbstractIncomingMessage,
            ) -> None:
                async with message.process(requeue=True, ignore_processed=True):
                    try:
                        with log_context(
                            _logger,
                            logging.DEBUG,
                            msg=f"Received message from {message.exchange=}, {message.routing_key=}",
                        ):
                            if not await message_handler(message.body):
                                await message.nack()
                    except Exception:  # pylint: disable=broad-exception-caught
                        _logger.exception(
                            "unhandled exception when consuming RabbitMQ message, "
                            "this is catched but should not happen. "
                            "Please check, message will be queued back!"
                        )
                        await message.nack()

            _consumer_tag = await self._get_consumer_tag(exchange_name)
            await queue.consume(
                _on_message,
                exclusive=exclusive_queue,
                consumer_tag=_consumer_tag,
            )
            output: str = queue.name
            return output

    async def add_topics(
        self,
        exchange_name: str,
        *,
        topics: list[str],
    ) -> None:
        assert self._channel_pool  # nosec

        async with self._channel_pool.acquire() as channel:
            exchange = await channel.get_exchange(exchange_name)
            queue = await declare_queue(
                channel, self.client_name, exchange_name, exclusive_queue=True
            )

            await asyncio.gather(
                *(queue.bind(exchange, routing_key=topic) for topic in topics)
            )

    async def remove_topics(
        self,
        exchange_name: str,
        *,
        topics: list[str],
    ) -> None:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            exchange = await channel.get_exchange(exchange_name)
            queue = await declare_queue(
                channel, self.client_name, exchange_name, exclusive_queue=True
            )

            await asyncio.gather(
                *(queue.unbind(exchange, routing_key=topic) for topic in topics),
            )

    async def unsubscribe(
        self,
        queue_name: str,
    ) -> None:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            queue = await channel.get_queue(queue_name)
            # NOTE: we force delete here
            await queue.delete(if_unused=False, if_empty=False)

    async def publish(self, exchange_name: str, message: RabbitMessage) -> None:
        """publish message in the exchange exchange_name.
        specifying a topic will use a TOPIC type of RabbitMQ Exchange instead of FANOUT

        NOTE: changing the type of Exchange will create issues if the name is not changed!
        """
        assert self._channel_pool  # nosec
        topic = message.routing_key()

        async with self._channel_pool.acquire() as channel:
            exchange = await channel.declare_exchange(
                exchange_name,
                aio_pika.ExchangeType.FANOUT
                if topic is None
                else aio_pika.ExchangeType.TOPIC,
                durable=True,
                timeout=_DEFAULT_RABBITMQ_EXECUTION_TIMEOUT_S,
            )
            await exchange.publish(
                aio_pika.Message(message.body()),
                routing_key=message.routing_key() or "",
            )

    async def unsubscribe_consumer(self, exchange_name: str):
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            queue_name = exchange_name
            queue = await channel.get_queue(queue_name)
            _consumer_tag = await self._get_consumer_tag(exchange_name)
            await queue.cancel(_consumer_tag)
