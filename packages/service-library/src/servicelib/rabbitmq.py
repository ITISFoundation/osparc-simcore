import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Final, Protocol

import aio_pika
import aiormq
from aio_pika.patterns import RPC
from pydantic import PositiveInt
from servicelib.logging_utils import log_catch, log_context
from settings_library.rabbit import RabbitSettings

from .rabbitmq_errors import RemoteMethodNotRegisteredError, RPCNotInitializedError
from .rabbitmq_utils import (
    RPCMethodName,
    RPCNamespace,
    RPCNamespacedMethodName,
    declare_queue,
    get_rabbitmq_client_unique_name,
)

_logger = logging.getLogger(__name__)


MessageHandler = Callable[[Any], Awaitable[bool]]

BIND_TO_ALL_TOPICS: Final[str] = "#"


class RabbitMessage(Protocol):
    def body(self) -> bytes:
        ...

    def routing_key(self) -> str | None:
        ...


_DEFAULT_RABBITMQ_SERVER_HEARTBEAT_S = 60
_DEFAULT_PREFETCH_VALUE = 10


@dataclass
class RabbitMQClient:
    client_name: str
    settings: RabbitSettings
    heartbeat: int = _DEFAULT_RABBITMQ_SERVER_HEARTBEAT_S
    _connection_pool: aio_pika.pool.Pool | None = field(init=False, default=None)
    _channel_pool: aio_pika.pool.Pool | None = field(init=False, default=None)

    _rpc_connection: aio_pika.abc.AbstractConnection | None = None
    _rpc_channel: aio_pika.abc.AbstractChannel | None = None
    _rpc: RPC | None = None

    _healthy_state: bool = True

    def __post_init__(self) -> None:
        # recommendations are 1 connection per process
        self._connection_pool = aio_pika.pool.Pool(
            self._get_connection, self.settings.dsn, self.client_name, max_size=1
        )
        # channels are not thread safe, what about python?
        self._channel_pool = aio_pika.pool.Pool(self._get_channel, max_size=10)

    def _connection_close_callback(
        self,
        sender: Any,  # pylint: disable=unused-argument
        exc: BaseException | None,
    ) -> None:
        if exc:
            if isinstance(exc, asyncio.CancelledError):
                _logger.info("Rabbit connection cancelled")
            elif isinstance(exc, aiormq.exceptions.ConnectionClosed):
                _logger.info("Rabbit connection closed: %s", exc)
            else:
                _logger.error(
                    "Rabbit connection closed with exception from %s:%s",
                    type(exc),
                    exc,
                )
                self._healthy_state = False

    def _channel_close_callback(
        self,
        sender: Any,  # pylint: disable=unused-argument
        exc: BaseException | None,
    ) -> None:
        if exc:
            if isinstance(exc, asyncio.CancelledError):
                _logger.info("Rabbit channel cancelled")
            elif isinstance(exc, aiormq.exceptions.ChannelClosed):
                _logger.info("Rabbit channel closed")
            else:
                _logger.error(
                    "Rabbit channel closed with exception from %s:%s",
                    type(exc),
                    exc,
                )
                self._healthy_state = False

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
        )
        connection.close_callbacks.add(self._connection_close_callback)
        return connection

    @property
    def healthy(self) -> bool:
        return self._healthy_state

    async def rpc_initialize(self) -> None:
        self._rpc_connection = await aio_pika.connect_robust(
            self.settings.dsn,
            client_properties={
                "connection_name": f"{get_rabbitmq_client_unique_name(self.client_name)}.rpc"
            },
        )
        self._rpc_channel = await self._rpc_connection.channel()

        self._rpc = RPC(self._rpc_channel)
        await self._rpc.initialize()

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

            # rpc is not always initialized
            if self._rpc is not None:
                await self._rpc.close()
            if self._rpc_channel is not None:
                await self._rpc_channel.close()
            if self._rpc_connection is not None:
                await self._rpc_connection.close()

    async def _get_channel(self) -> aio_pika.abc.AbstractChannel:
        assert self._connection_pool  # nosec
        async with self._connection_pool.acquire() as connection:
            channel = await connection.channel()
            channel.close_callbacks.add(self._channel_close_callback)
            return channel

    async def ping(self) -> bool:
        with log_catch(_logger, reraise=False):
            async with await aio_pika.connect(self.settings.dsn, timeout=1):
                ...
            return True
        return False

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
                            _logger, logging.DEBUG, msg=f"Message received {message}"
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

            await queue.consume(
                _on_message,
                exclusive=exclusive_queue,
                consumer_tag=f"{get_rabbitmq_client_unique_name(self.client_name)}_{exchange_name}",
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
            )
            await exchange.publish(
                aio_pika.Message(message.body()),
                routing_key=message.routing_key() or "",
            )

    async def rpc_request(
        self,
        namespace: RPCNamespace,
        method_name: RPCMethodName,
        *,
        timeout_s: PositiveInt | None = 5,
        **kwargs,
    ) -> Any:
        """
        Call a remote registered `handler` by providing it's `namespace`, `method_name`
        and `kwargs` containing the key value arguments expected by the remote `handler`.

        :raises asyncio.TimeoutError: when message expired
        :raises CancelledError: when called :func:`RPC.cancel`
        :raises RuntimeError: internal error
        :raises RemoteMethodNotRegisteredError: when no handler was registered to the
            `namespaced_method_name`
        """

        if not self._rpc:
            raise RPCNotInitializedError

        namespaced_method_name = RPCNamespacedMethodName.from_namespace_and_method(
            namespace, method_name
        )
        try:
            queue_expiration_timeout = timeout_s
            awaitable = self._rpc.call(
                namespaced_method_name,
                expiration=queue_expiration_timeout,
                kwargs=kwargs,
            )
            return await asyncio.wait_for(awaitable, timeout=timeout_s)
        except aio_pika.MessageProcessError as e:
            if e.args[0] == "Message has been returned":
                raise RemoteMethodNotRegisteredError(
                    method_name=namespaced_method_name, incoming_message=e.args[1]
                ) from e
            raise e

    async def rpc_register_handler(
        self,
        namespace: RPCNamespace,
        method_name: RPCMethodName,
        handler: Callable[..., Any],
    ) -> None:
        """
        Bind a local `handler` to a `namespace` and `method_name`.
        The handler can be remotely called by providing the `namespace` and `method_name`

        NOTE: method_name could be computed from the handler, but by design, it is
        left to the caller to do so.
        """

        if self._rpc is None:
            raise RPCNotInitializedError

        await self._rpc.register(
            RPCNamespacedMethodName.from_namespace_and_method(namespace, method_name),
            handler,
            auto_delete=True,
        )

    async def rpc_unregister_handler(self, handler: Callable[..., Any]) -> None:
        """Unbind a locally added `handler`"""

        if self._rpc is None:
            raise RPCNotInitializedError

        await self._rpc.unregister(handler)
