import asyncio
import datetime
import logging
from dataclasses import dataclass, field
from functools import partial
from typing import Annotated, Any, Final
from uuid import uuid4

import aio_pika
from aiormq import ChannelInvalidStateError
from annotated_types import doc
from common_library.async_tools import cancel_wait_task
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from pydantic import NonNegativeInt, PositiveInt

from ..background_task import create_periodic_task
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

_BACKLOG_MONITOR_INTERVAL: Final[datetime.timedelta] = datetime.timedelta(seconds=60)
_BACKLOG_MONITOR_CONSECUTIVE_GROWTH_TO_WARN: Final[int] = 3

_DEFAULT_UNEXPECTED_ERROR_RETRY_DELAY_S: Final[float] = 1
_DEFAULT_UNEXPECTED_ERROR_MAX_ATTEMPTS: Final[NonNegativeInt] = 15

_DELAYED_EXCHANGE_NAME: Final[ExchangeName] = ExchangeName("delayed_{exchange_name}")
_DELAYED_QUEUE_NAME: Final[ExchangeName] = ExchangeName("delayed_{queue_name}")


def _get_x_death_count(message: aio_pika.abc.AbstractIncomingMessage) -> int:
    count: int = 0
    if (x_death := message.headers.get(_HEADER_X_DEATH, [])) and (
        isinstance(x_death, list) and x_death and isinstance(x_death[0], dict) and "count" in x_death[0]
    ):
        assert isinstance(x_death[0]["count"], int)  # nosec
        count = x_death[0]["count"]

    return count


async def _nack_message(
    message_handler: MessageHandler,
    max_retries_upon_error: int,
    message: aio_pika.abc.AbstractIncomingMessage,
) -> None:
    count = _get_x_death_count(message)
    _logger.debug(
        "Nacking message '%s' from handler '%s', death count %s, max retries %s",
        message.message_id,
        message_handler,
        count,
        max_retries_upon_error,
    )
    if count < max_retries_upon_error:
        _logger.warning(
            ("Retry [%s/%s] for handler '%s', which raised an unexpected error caused by message_id='%s'"),
            count,
            max_retries_upon_error,
            message_handler,
            message.message_id,
        )
        # NOTE: puts message to the Dead Letter Exchange
        await message.nack(requeue=False)
    else:
        _logger.error(
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
    log_error_context = {
        "message_id": message.message_id,
        "message_body": message.body,
        "message_handler": f"{message_handler}",
    }
    try:
        async with message.process(requeue=True, ignore_processed=True):
            with log_context(
                _logger,
                logging.DEBUG,
                msg=f"Processing message {message.exchange=}, {message.routing_key=}",
            ):
                try:
                    with log_context(
                        _logger,
                        logging.DEBUG,
                        msg=f"Received message from {message.exchange=}, {message.routing_key=}",
                    ):
                        if not await message_handler(message.body):
                            with log_context(
                                _logger,
                                logging.DEBUG,
                                msg=f"Nack message {message.exchange=}, {message.routing_key=}",
                            ):
                                await _nack_message(message_handler, max_retries_upon_error, message)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    _logger.exception(
                        **create_troubleshooting_log_kwargs(
                            "Unhandled exception raised in message handler or when nacking message",
                            error=exc,
                            error_context=log_error_context,
                            tip="This could indicate an error in the message handler, "
                            "please check the message handler code",
                        )
                    )
                    with log_catch(_logger, reraise=False):
                        await _nack_message(message_handler, max_retries_upon_error, message)

    except ChannelInvalidStateError as exc:
        # NOTE: this error can happen as can be seen in aio-pika code
        # see https://github.com/mosquito/aio-pika/blob/master/aio_pika/robust_queue.py
        _logger.exception(
            **create_troubleshooting_log_kwargs(
                "Cannot process message because channel is closed. Message will be requeued by RabbitMQ",
                error=exc,
                error_context=log_error_context,
                tip="This could indicate the message handler takes > 30 minutes to complete "
                "(default time the RabbitMQ broker waits to close a channel when a "
                "message is not acknowledged) or an issue in RabbitMQ broker itself.",
            )
        )


@dataclass
class RabbitMQClient(RabbitMQClientBase):
    _connection_pool: aio_pika.pool.Pool | None = field(init=False, default=None)
    _channel_pool: aio_pika.pool.Pool | None = field(init=False, default=None)
    _backlog_monitor_tasks: list[asyncio.Task] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        # recommendations are 1 connection per process
        self._connection_pool = aio_pika.pool.Pool(
            self._get_connection, self.settings.dsn, self.client_name, max_size=1
        )
        # channels are not thread safe, what about python?
        self._channel_pool = aio_pika.pool.Pool(self._get_channel, max_size=10)

    async def _get_connection(self, rabbit_broker: str, connection_name: str) -> aio_pika.abc.AbstractRobustConnection:
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
        connection.reconnect_callbacks.add(self._connection_reconnect_callback)
        return connection

    async def close(self) -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg=f"{self.client_name} closing connection to RabbitMQ",
        ):
            with log_catch(_logger, reraise=False):
                await asyncio.gather(
                    *(
                        cancel_wait_task(task, max_delay=_DEFAULT_RABBITMQ_EXECUTION_TIMEOUT_S)
                        for task in self._backlog_monitor_tasks
                    )
                )
            self._backlog_monitor_tasks.clear()
            assert self._channel_pool  # nosec
            await self._channel_pool.close()
            assert self._connection_pool  # nosec
            await self._connection_pool.close()

    async def _get_channel(self) -> aio_pika.abc.AbstractChannel:
        assert self._connection_pool  # nosec
        async with self._connection_pool.acquire() as connection:
            assert isinstance(connection, aio_pika.RobustConnection)  # nosec
            channel: aio_pika.abc.AbstractChannel = await connection.channel()
            channel.close_callbacks.add(self._channel_close_callback)
            return channel

    def _start_backlog_monitor(self, queue_name: QueueName, exchange_name: ExchangeName) -> None:
        """Warns if a bounded queue's ready-message count keeps growing, i.e. the
        consumer cannot keep up with the publish rate (see `subscribe`'s `max_length`)."""
        previous_message_count: int | None = None
        consecutive_growth = 0

        async def _check_backlog() -> None:
            nonlocal previous_message_count, consecutive_growth
            assert self._connection_pool  # nosec
            # NOTE: uses a dedicated, short-lived channel (not the shared `_channel_pool`) since
            # that pool can hand out a channel that is concurrently in use to actively deliver
            # an unacked message to a consumer, causing protocol interleaving on that channel
            async with self._connection_pool.acquire() as connection:
                channel = await connection.channel()
                try:
                    declared = await channel.declare_queue(
                        queue_name, passive=True, timeout=_DEFAULT_RABBITMQ_EXECUTION_TIMEOUT_S
                    )
                    message_count = declared.declaration_result.message_count
                finally:
                    await channel.close()
            consecutive_growth = (
                consecutive_growth + 1
                if previous_message_count is not None and message_count and message_count > previous_message_count
                else 0
            )
            if consecutive_growth >= _BACKLOG_MONITOR_CONSECUTIVE_GROWTH_TO_WARN:
                _logger.warning(
                    "Queue '%s' (exchange '%s') backlog kept growing for %s consecutive checks "
                    "(now %s ready messages): the consumer may not be keeping up with the publish rate",
                    queue_name,
                    exchange_name,
                    consecutive_growth,
                    message_count,
                )
            previous_message_count = message_count

        self._backlog_monitor_tasks.append(
            create_periodic_task(
                _check_backlog,
                interval=_BACKLOG_MONITOR_INTERVAL,
                task_name=f"rabbitmq_backlog_monitor_{queue_name}",
            )
        )

    async def _create_consumer_tag(self, exchange_name) -> ConsumerTag:
        return ConsumerTag(f"{get_rabbitmq_client_unique_name(self.client_name)}_{exchange_name}_{uuid4()}")

    async def subscribe(  # noqa: PLR0913 # pylint: disable=too-many-arguments
        self,
        exchange_name: ExchangeName,
        message_handler: Annotated[
            MessageHandler,
            doc(
                "Called with the raw message body for every incoming message. "
                "Return `True` if the message was handled successfully (it is acked). "
                "Return `False`, or let an exception propagate, to signal a failure: "
                "the message is nacked and redelivered (via the delayed/dead-letter exchange) "
                "up to `unexpected_error_max_attempts` times, waiting `unexpected_error_retry_delay_s` "
                "between attempts, after which it is dropped. A raised exception is additionally "
                "logged as an unhandled error, whereas returning `False` is treated as an expected retry signal"
            ),
        ],
        *,
        exclusive_queue: Annotated[
            bool,
            doc(
                "True: every instance of this application receives the incoming messages. "
                "False: only one instance of this application receives each message"
            ),
        ] = True,
        non_exclusive_queue_name: Annotated[
            str | None,
            doc("Queue name used when `exclusive_queue` is False. Defaults to `exchange_name` when None"),
        ] = None,
        topics: Annotated[
            list[str] | None,
            doc(
                "Declares a TOPIC exchange instead of FANOUT when provided. FANOUT transmits messages "
                "to any bound queue regardless of routing key. TOPIC transmits messages only to queues "
                "bound with a matching routing key: BIND_TO_ALL_TOPICS ('#') behaves like FANOUT; "
                "'director-v2.*' matches routing keys such as 'director-v2.event.service_started'; "
                "'director-v2.event.specific_event' matches only that exact routing key"
            ),
        ] = None,
        message_ttl: Annotated[
            NonNegativeInt,
            doc(
                "Also acts as a soft timeout: if `message_handler` does not finish processing "
                "the message before this is reached, the message will be redelivered"
            ),
        ] = RABBIT_QUEUE_MESSAGE_DEFAULT_TTL_MS,
        max_length: Annotated[
            NonNegativeInt | None,
            doc(
                "Caps the queue depth. Once reached, the OLDEST ready messages are silently "
                "dropped (`x-overflow: drop-head`) to make room for new ones, protecting the "
                "broker from unbounded memory growth if `message_handler` ever falls behind "
                "the publish rate. None (default) leaves the queue unbounded; only set this "
                "for exchanges where losing old messages is preferable to broker instability. "
                "NOTE: RabbitMQ dead-letters messages dropped this way too (reason `maxlen`), same "
                "as nacked/expired ones; pair this with `enable_dead_letter_requeue=False`, or the "
                "dropped messages will bounce forever between this queue and its delay queue until "
                "RabbitMQ's own dead-letter-cycle detector catches it"
            ),
        ] = None,
        prefetch_count: Annotated[
            PositiveInt | None,
            doc(
                "Maximum number of messages delivered to (and awaiting ack from) `message_handler` "
                "concurrently. None (default) uses 1 for shared (`exclusive_queue=False`) queues, or "
                f"{_DEFAULT_PREFETCH_VALUE} for exclusive ones. Raise this for lightweight, I/O-bound "
                "handlers on high-throughput exchanges, where the default is otherwise the throughput "
                "ceiling regardless of how fast `message_handler` actually runs"
            ),
        ] = None,
        unexpected_error_retry_delay_s: Annotated[
            float,
            doc("Time to wait between each retry when `message_handler` raised or returned `False`"),
        ] = _DEFAULT_UNEXPECTED_ERROR_RETRY_DELAY_S,
        unexpected_error_max_attempts: Annotated[
            int,
            doc("Maximum amount of retries when `message_handler` raised or returned `False`"),
        ] = _DEFAULT_UNEXPECTED_ERROR_MAX_ATTEMPTS,
        enable_dead_letter_requeue: Annotated[
            bool,
            doc(
                "When True (default), messages that are nacked or that expire after sitting "
                "`message_ttl` in the queue are bounced through a delay queue and re-published into "
                "THIS SAME exchange for a retry, up to `unexpected_error_max_attempts` times. Set False "
                "for best-effort/fire-and-forget exchanges (e.g. live UI notifications) where a stale "
                "message has no value: expired/nacked messages are then simply dropped instead of "
                "generating more publish traffic back into an exchange that may already be backlogged"
            ),
        ] = True,
    ) -> Annotated[
        tuple[QueueName, ConsumerTag],
        doc("Returns the queue name and consumer tag of the subscription"),
    ]:
        """Subscribes to `exchange_name`, calling `message_handler` for every incoming message.

        Raises:
            aio_pika.exceptions.ChannelPreconditionFailed: In case an existing exchange with
                different type is used
        """

        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            qos_value = prefetch_count or (1 if exclusive_queue is False else _DEFAULT_PREFETCH_VALUE)
            await channel.set_qos(qos_value)

            exchange = await channel.declare_exchange(
                exchange_name,
                (aio_pika.ExchangeType.FANOUT if topics is None else aio_pika.ExchangeType.TOPIC),
                durable=True,
                timeout=_DEFAULT_RABBITMQ_EXECUTION_TIMEOUT_S,
            )

            # NOTE: durable=True makes the queue persistent between RabbitMQ restarts/crashes
            # consumer/publisher must set the same configuration for same queue
            # exclusive means that the queue is only available for THIS very client
            # and will be deleted when the client disconnects
            # NOTE what is a dead letter exchange, see https://www.rabbitmq.com/dlx.html
            queue_arguments: dict[str, Any] = {}
            if enable_dead_letter_requeue:
                delayed_exchange_name = _DELAYED_EXCHANGE_NAME.format(exchange_name=exchange_name)
                queue_arguments["x-dead-letter-exchange"] = delayed_exchange_name
            if max_length is not None:
                queue_arguments["x-max-length"] = max_length
                queue_arguments["x-overflow"] = "drop-head"
            queue = await declare_queue(
                channel,
                self.client_name,
                non_exclusive_queue_name or exchange_name,
                exclusive_queue=exclusive_queue,
                message_ttl=message_ttl,
                arguments=queue_arguments,
            )
            if topics is None:
                await queue.bind(exchange, routing_key="")
            else:
                await asyncio.gather(*(queue.bind(exchange, routing_key=topic) for topic in topics))

            if enable_dead_letter_requeue:
                delayed_exchange = await channel.declare_exchange(
                    delayed_exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
                )
                delayed_queue_name = _DELAYED_QUEUE_NAME.format(queue_name=non_exclusive_queue_name or exchange_name)

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
            if max_length is not None:
                self._start_backlog_monitor(queue.name, exchange_name)
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
                passive=True,
            )

            await asyncio.gather(*(queue.bind(exchange, routing_key=topic) for topic in topics))

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
                passive=True,
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
            _logger.warning("Connection to RabbitMQ is already closed, skipping unsubscribe from queue...")
            return
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            queue = await channel.get_queue(queue_name)
            # NOTE: we force delete here
            await queue.delete(if_unused=False, if_empty=False)

    async def publish(self, exchange_name: ExchangeName, message: RabbitMessage) -> None:
        """publish message in the exchange exchange_name.
        specifying a topic will use a TOPIC type of RabbitMQ Exchange instead of FANOUT

        NOTE: changing the type of Exchange will create issues if the name is not changed!
        """
        assert self._channel_pool  # nosec
        topic = message.routing_key()

        async with self._channel_pool.acquire() as channel:
            exchange = await channel.declare_exchange(
                exchange_name,
                (aio_pika.ExchangeType.FANOUT if topic is None else aio_pika.ExchangeType.TOPIC),
                durable=True,
                timeout=_DEFAULT_RABBITMQ_EXECUTION_TIMEOUT_S,
            )
            await exchange.publish(
                aio_pika.Message(message.body()),
                routing_key=message.routing_key() or "",
            )

    async def unsubscribe_consumer(self, queue_name: QueueName, consumer_tag: ConsumerTag) -> None:
        """This will only remove the consumers without deleting the queue"""
        assert self._connection_pool  # nosec
        if self._connection_pool.is_closed:
            _logger.warning("Connection to RabbitMQ is already closed, skipping unsubscribe consumers from queue...")
            return
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            assert isinstance(channel, aio_pika.RobustChannel)  # nosec
            queue = await channel.get_queue(queue_name)
            await queue.cancel(consumer_tag)
