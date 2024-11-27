import asyncio
import logging
from dataclasses import dataclass, field
from functools import partial
from typing import Final
from uuid import uuid4

import aio_pika
from pydantic import NonNegativeInt

from ..logging_utils import log_catch, log_context
from ._client_base import RabbitMQClientBase
from ._models import (
    ConsumerTag,
    ExchangeName,
    MessageHandler,
    QueueName,
    RabbitMessage,
    TopicName,
)
from ._utils import (
    RABBIT_QUEUE_MESSAGE_DEFAULT_TTL_MS,
    declare_queue,
    get_rabbitmq_client_unique_name,
)

_logger = logging.getLogger(__name__)


_DEFAULT_PREFETCH_VALUE: Final[int] = 10
_DEFAULT_RABBITMQ_EXECUTION_TIMEOUT_S: Final[int] = 5
_HEADER_X_DEATH: Final[str] = "x-death"

_DEFAULT_UNEXPECTED_ERROR_RETRY_DELAY_S: Final[float] = 1
_DEFAULT_UNEXPECTED_ERROR_MAX_ATTEMPTS: Final[NonNegativeInt] = 15

_DELAYED_EXCHANGE_NAME: Final[ExchangeName] = ExchangeName("delayed_{exchange_name}")
_DELAYED_QUEUE_NAME: Final[ExchangeName] = ExchangeName("delayed_{queue_name}")


def _get_x_death_count(message: aio_pika.abc.AbstractIncomingMessage) -> int:
    count: int = 0
    if (x_death := message.headers.get(_HEADER_X_DEATH, [])) and (
        isinstance(x_death, list)
        and x_death
        and isinstance(x_death[0], dict)
        and "count" in x_death[0]
    ):

        assert isinstance(x_death[0]["count"], int)  # nosec
        count = x_death[0]["count"]

    return count


async def _safe_nack(
    message_handler: MessageHandler,
    max_retries_upon_error: int,
    message: aio_pika.abc.AbstractIncomingMessage,
) -> None:
    count = _get_x_death_count(message)
    if count < max_retries_upon_error:
        _logger.warning(
            (
                "Retry [%s/%s] for handler '%s', which raised "
                "an unexpected error caused by message_id='%s'"
            ),
            count,
            max_retries_upon_error,
            message_handler,
            message.message_id,
        )
        # NOTE: puts message to the Dead Letter Exchange
        await message.nack(requeue=False)
    else:
        _logger.exception(
            "Handler '%s' is giving up on message '%s' with body '%s'",
            message_handler,
            message,
            message.body,
        )


async def _on_message(
    message_handler: MessageHandler,
    max_retries_upon_error: int,
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
                    await _safe_nack(message_handler, max_retries_upon_error, message)
        except Exception:  # pylint: disable=broad-exception-caught
            _logger.exception("Exception raised when handling message")
            with log_catch(_logger, reraise=False):
                await _safe_nack(message_handler, max_retries_upon_error, message)


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
            channel: aio_pika.abc.AbstractChannel = await connection.channel()
            channel.close_callbacks.add(self._channel_close_callback)
            return channel

    async def _create_consumer_tag(self, exchange_name) -> ConsumerTag:
        return ConsumerTag(
            f"{get_rabbitmq_client_unique_name(self.client_name)}_{exchange_name}_{uuid4()}"
        )

    async def subscribe(
        self,
        exchange_name: ExchangeName,
        message_handler: MessageHandler,
        *,
        exclusive_queue: bool = True,
        non_exclusive_queue_name: str | None = None,
        topics: list[str] | None = None,
        message_ttl: NonNegativeInt = RABBIT_QUEUE_MESSAGE_DEFAULT_TTL_MS,
        unexpected_error_retry_delay_s: float = _DEFAULT_UNEXPECTED_ERROR_RETRY_DELAY_S,
        unexpected_error_max_attempts: int = _DEFAULT_UNEXPECTED_ERROR_MAX_ATTEMPTS,
    ) -> tuple[QueueName, ConsumerTag]:
        """subscribe to exchange_name calling ``message_handler`` for every incoming message
        - exclusive_queue: True means that every instance of this application will
            receive the incoming messages
        - exclusive_queue: False means that only one instance of this application will
            reveice the incoming message
        - non_exclusive_queue_name: if exclusive_queue is False, then this name will be used. If None
            it will use the exchange_name.

        NOTE: ``message_ttl` is also a soft timeout: if the handler does not finish processing
        the message before this is reached the message will be redelivered!

        specifying a topic will make the client declare a TOPIC type of RabbitMQ Exchange
        instead of FANOUT
        - a FANOUT exchange transmit messages to any connected queue regardless of
            the routing key
        - a TOPIC exchange transmit messages to any connected queue provided it is
            bound with the message routing key
          - topic = BIND_TO_ALL_TOPICS ("#") is equivalent to the FANOUT effect
          - a queue bound with topic "director-v2.*" will receive any message that
            uses a routing key such as "director-v2.event.service_started"
          - a queue bound with topic "director-v2.event.specific_event" will only
            receive messages with that exact routing key (same as DIRECT exchanges behavior)

        ``unexpected_error_max_attempts`` is the maximum amount of retries when the ``message_handler``
            raised an unexpected error or it returns `False`
        ``unexpected_error_retry_delay_s`` time to wait between each retry when the ``message_handler``
            raised an unexpected error or it returns `False`

        Raises:
            aio_pika.exceptions.ChannelPreconditionFailed: In case an existing exchange with
            different type is used
        Returns:
            tuple of queue name and consumer tag mapping
        """

        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            qos_value = 1 if exclusive_queue is False else _DEFAULT_PREFETCH_VALUE
            await channel.set_qos(qos_value)

            exchange = await channel.declare_exchange(
                exchange_name,
                (
                    aio_pika.ExchangeType.FANOUT
                    if topics is None
                    else aio_pika.ExchangeType.TOPIC
                ),
                durable=True,
                timeout=_DEFAULT_RABBITMQ_EXECUTION_TIMEOUT_S,
            )

            # NOTE: durable=True makes the queue persistent between RabbitMQ restarts/crashes
            # consumer/publisher must set the same configuration for same queue
            # exclusive means that the queue is only available for THIS very client
            # and will be deleted when the client disconnects
            # NOTE what is a dead letter exchange, see https://www.rabbitmq.com/dlx.html
            delayed_exchange_name = _DELAYED_EXCHANGE_NAME.format(
                exchange_name=exchange_name
            )
            queue = await declare_queue(
                channel,
                self.client_name,
                non_exclusive_queue_name or exchange_name,
                exclusive_queue=exclusive_queue,
                message_ttl=message_ttl,
                arguments={"x-dead-letter-exchange": delayed_exchange_name},
            )
            if topics is None:
                await queue.bind(exchange, routing_key="")
            else:
                await asyncio.gather(
                    *(queue.bind(exchange, routing_key=topic) for topic in topics)
                )

            delayed_exchange = await channel.declare_exchange(
                delayed_exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
            )
            delayed_queue_name = _DELAYED_QUEUE_NAME.format(
                queue_name=non_exclusive_queue_name or exchange_name
            )

            delayed_queue = await declare_queue(
                channel,
                self.client_name,
                delayed_queue_name,
                exclusive_queue=exclusive_queue,
                message_ttl=int(unexpected_error_retry_delay_s * 1000),
                arguments={"x-dead-letter-exchange": exchange.name},
            )
            await delayed_queue.bind(delayed_exchange)

            consumer_tag = await self._create_consumer_tag(exchange_name)
            await queue.consume(
                partial(_on_message, message_handler, unexpected_error_max_attempts),
                exclusive=exclusive_queue,
                consumer_tag=consumer_tag,
            )
            return queue.name, consumer_tag

    async def add_topics(
        self,
        exchange_name: ExchangeName,
        *,
        topics: list[TopicName],
    ) -> None:
        assert self._channel_pool  # nosec

        async with self._channel_pool.acquire() as channel:
            exchange = await channel.get_exchange(exchange_name)
            queue = await declare_queue(
                channel,
                self.client_name,
                exchange_name,
                exclusive_queue=True,
                arguments={
                    "x-dead-letter-exchange": _DELAYED_EXCHANGE_NAME.format(
                        exchange_name=exchange_name
                    )
                },
            )

            await asyncio.gather(
                *(queue.bind(exchange, routing_key=topic) for topic in topics)
            )

    async def remove_topics(
        self,
        exchange_name: ExchangeName,
        *,
        topics: list[TopicName],
    ) -> None:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            exchange = await channel.get_exchange(exchange_name)
            queue = await declare_queue(
                channel,
                self.client_name,
                exchange_name,
                exclusive_queue=True,
                arguments={
                    "x-dead-letter-exchange": _DELAYED_EXCHANGE_NAME.format(
                        exchange_name=exchange_name
                    )
                },
            )

            await asyncio.gather(
                *(queue.unbind(exchange, routing_key=topic) for topic in topics),
            )

    async def unsubscribe(
        self,
        queue_name: QueueName,
    ) -> None:
        """This will delete the queue if there are no consumers left"""
        assert self._connection_pool  # nosec
        if self._connection_pool.is_closed:
            _logger.warning(
                "Connection to RabbitMQ is already closed, skipping unsubscribe from queue..."
            )
            return
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            queue = await channel.get_queue(queue_name)
            # NOTE: we force delete here
            await queue.delete(if_unused=False, if_empty=False)

    async def publish(
        self, exchange_name: ExchangeName, message: RabbitMessage
    ) -> None:
        """publish message in the exchange exchange_name.
        specifying a topic will use a TOPIC type of RabbitMQ Exchange instead of FANOUT

        NOTE: changing the type of Exchange will create issues if the name is not changed!
        """
        assert self._channel_pool  # nosec
        topic = message.routing_key()

        async with self._channel_pool.acquire() as channel:
            exchange = await channel.declare_exchange(
                exchange_name,
                (
                    aio_pika.ExchangeType.FANOUT
                    if topic is None
                    else aio_pika.ExchangeType.TOPIC
                ),
                durable=True,
                timeout=_DEFAULT_RABBITMQ_EXECUTION_TIMEOUT_S,
            )
            await exchange.publish(
                aio_pika.Message(message.body()),
                routing_key=message.routing_key() or "",
            )

    async def unsubscribe_consumer(
        self, queue_name: QueueName, consumer_tag: ConsumerTag
    ) -> None:
        """This will only remove the consumers without deleting the queue"""
        assert self._connection_pool  # nosec
        if self._connection_pool.is_closed:
            _logger.warning(
                "Connection to RabbitMQ is already closed, skipping unsubscribe consumers from queue..."
            )
            return
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            assert isinstance(channel, aio_pika.RobustChannel)  # nosec
            queue = await channel.get_queue(queue_name)
            await queue.cancel(consumer_tag)
