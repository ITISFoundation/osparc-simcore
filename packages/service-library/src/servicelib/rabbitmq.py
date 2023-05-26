import asyncio
import logging
import os
import socket
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Final, Protocol

import aio_pika
from aio_pika.exceptions import ChannelClosed
from aio_pika.patterns import RPC
from pydantic import PositiveInt
from servicelib.logging_utils import log_context
from settings_library.rabbit import RabbitSettings

from .rabbitmq_errors import RemoteMethodNotRegisteredError, RPCNotInitializedError
from .rabbitmq_utils import RPCMethodName, RPCNamespace, RPCNamespacedMethodName

_logger = logging.getLogger(__name__)


def _connection_close_callback(sender: Any, exc: BaseException | None) -> None:
    if exc:
        if isinstance(exc, asyncio.CancelledError):
            _logger.info("Rabbit connection was cancelled")
        else:
            _logger.error(
                "Rabbit connection closed with exception from %s:%s",
                sender,
                exc,
            )


def _channel_close_callback(sender: Any, exc: BaseException | None) -> None:
    if exc:
        if isinstance(exc, asyncio.CancelledError):
            _logger.info("Rabbit channel was cancelled")
        elif isinstance(exc, ChannelClosed):
            _logger.info("%s", exc)
        else:
            _logger.error(
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

BIND_TO_ALL_TOPICS: Final[str] = "#"


class RabbitMessage(Protocol):
    def body(self) -> bytes:
        ...

    def routing_key(self) -> str | None:
        ...


_MINUTE: Final[int] = 60
_RABBIT_QUEUE_MESSAGE_DEFAULT_TTL_S: Final[int] = 15 * _MINUTE


@dataclass
class RabbitMQClient:
    client_name: str
    settings: RabbitSettings
    _connection_pool: aio_pika.pool.Pool | None = field(init=False, default=None)
    _channel_pool: aio_pika.pool.Pool | None = field(init=False, default=None)

    _rpc_connection: aio_pika.abc.AbstractConnection | None = None
    _rpc_channel: aio_pika.abc.AbstractChannel | None = None
    _rpc: RPC | None = None

    def __post_init__(self):
        # recommendations are 1 connection per process
        self._connection_pool = aio_pika.pool.Pool(
            _get_connection, self.settings.dsn, self.client_name, max_size=1
        )
        # channels are not thread safe, what about python?
        self._channel_pool = aio_pika.pool.Pool(self._get_channel, max_size=10)

    async def rpc_initialize(self) -> None:
        self._rpc_connection = await aio_pika.connect_robust(
            self.settings.dsn,
            client_properties={
                "connection_name": f"{self.client_name}.rpc.{socket.gethostname()}"
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
            connection: aio_pika.RobustConnection
            channel = await connection.channel()
            channel.close_callbacks.add(_channel_close_callback)
            return channel

    async def ping(self) -> bool:
        assert self._connection_pool  # nosec
        async with self._connection_pool.acquire() as connection:
            connection: aio_pika.RobustConnection
            return connection.connected.is_set()

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
        """

        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel
            _DEFAULT_PREFETCH_VALUE = 10  # this value is set to the default for now
            await channel.set_qos(_DEFAULT_PREFETCH_VALUE)

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
            queue_parameters = {
                "durable": True,
                "exclusive": exclusive_queue,
                "arguments": {"x-message-ttl": _RABBIT_QUEUE_MESSAGE_DEFAULT_TTL_S},
            }
            if not exclusive_queue:
                # NOTE: setting a name will ensure multiple instance will take their data here
                queue_parameters |= {"name": exchange_name}
            queue = await channel.declare_queue(**queue_parameters)
            if topics is None:
                await queue.bind(exchange, routing_key="")
            else:
                await asyncio.gather(
                    *(queue.bind(exchange, routing_key=topic) for topic in topics)
                )

            async def _on_message(
                message: aio_pika.abc.AbstractIncomingMessage,
            ) -> None:
                async with message.process(requeue=True):
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

            await queue.consume(_on_message)
            return queue.name

    async def add_topics(
        self,
        exchange_name: str,
        queue_name: str,
        *,
        topics: list[str],
    ) -> None:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel
            exchange = await channel.get_exchange(exchange_name)
            queue = await channel.get_queue(queue_name)

            await asyncio.gather(
                *(queue.bind(exchange, routing_key=topic) for topic in topics)
            )

    async def remove_topics(
        self,
        exchange_name: str,
        queue_name: str,
        *,
        topics: list[str],
    ) -> None:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel
            exchange = await channel.get_exchange(exchange_name)
            queue = await channel.get_queue(queue_name)

            await asyncio.gather(
                *(queue.unbind(exchange, routing_key=topic) for topic in topics)
            )

    async def unsubscribe(
        self,
        queue_name: str,
    ) -> None:
        assert self._channel_pool  # nosec
        async with self._channel_pool.acquire() as channel:
            channel: aio_pika.RobustChannel
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
            channel: aio_pika.RobustChannel
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
        **kwargs: dict[str, Any],
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
            raise RPCNotInitializedError()

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
            raise RPCNotInitializedError()

        await self._rpc.register(
            RPCNamespacedMethodName.from_namespace_and_method(namespace, method_name),
            handler,
            auto_delete=True,
        )

    async def rpc_unregister_handler(self, handler: Callable[..., Any]) -> None:
        """Unbind a locally added `handler`"""

        if self._rpc is None:
            raise RPCNotInitializedError()

        await self._rpc.unregister(handler)
