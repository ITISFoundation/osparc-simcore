import asyncio
import functools
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import aio_pika
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from pydantic import PositiveInt
from settings_library.rabbit import RabbitSettings

from ..logging_utils import log_context
from ._client_base import RabbitMQClientBase
from ._constants import RPC_REQUEST_DEFAULT_TIMEOUT_S
from ._errors import RemoteMethodNotRegisteredError, RPCNotInitializedError
from ._models import RPCNamespacedMethodName
from ._rpc_router import RPCRouter
from ._utils import get_rabbitmq_client_unique_name

_logger = logging.getLogger(__name__)


@dataclass
class RabbitMQRPCClient(RabbitMQClientBase):
    _connection: aio_pika.abc.AbstractConnection | None = None
    _channel: aio_pika.abc.AbstractChannel | None = None
    _rpc: aio_pika.patterns.RPC | None = None

    @classmethod
    async def create(
        cls, *, client_name: str, settings: RabbitSettings, **kwargs
    ) -> "RabbitMQRPCClient":
        client = cls(client_name=client_name, settings=settings, **kwargs)
        await client._rpc_initialize()
        return client

    async def _rpc_initialize(self) -> None:
        # NOTE: to show the connection name in the rabbitMQ UI see there
        # https://www.bountysource.com/issues/89342433-setting-custom-connection-name-via-client_properties-doesn-t-work-when-connecting-using-an-amqp-url
        #
        connection_name = f"{get_rabbitmq_client_unique_name(self.client_name)}.rpc"
        url = f"{self.settings.dsn}?name={connection_name}"
        self._connection = await aio_pika.connect_robust(
            url,
            client_properties={"connection_name": connection_name},
        )
        self._channel = await self._connection.channel()

        self._rpc = aio_pika.patterns.RPC(self._channel)
        await self._rpc.initialize(durable=True)

    async def close(self) -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg=f"{self.client_name} closing connection to RabbitMQ",
        ):
            # rpc is not always initialized
            if self._rpc is not None:
                await self._rpc.close()
            if self._channel is not None:
                await self._channel.close()
            if self._connection is not None:
                await self._connection.close()

    async def request(
        self,
        namespace: RPCNamespace,
        method_name: RPCMethodName,
        *,
        timeout_s: PositiveInt | None = RPC_REQUEST_DEFAULT_TIMEOUT_S,
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
            raise
        except ModuleNotFoundError as err:
            # SEE https://github.com/ITISFoundation/osparc-simcore/blob/b1aee64ae207a6ed3e965ff7869c74a312109de7/services/catalog/src/simcore_service_catalog/api/rpc/_services.py#L41-L46
            err.msg += (
                "\nTIP: All i/o rpc parameters MUST be shared by client and server sides. "
                "Careful with Generics instanciated on the server side. "
                "Use instead a TypeAlias in a common library."
            )
            raise

    async def register_handler(
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
            durable=True,
        )

    async def register_router(
        self,
        router: RPCRouter,
        namespace: RPCNamespace,
        *handler_args,
        **handler_kwargs,
    ) -> None:
        for rpc_method_name, handler in router.routes.items():
            await self.register_handler(
                namespace,
                rpc_method_name,
                functools.partial(handler, *handler_args, **handler_kwargs),
            )

    async def unregister_handler(self, handler: Callable[..., Any]) -> None:
        """Unbind a locally added `handler`"""

        if self._rpc is None:
            raise RPCNotInitializedError

        await self._rpc.unregister(handler)


@asynccontextmanager
async def rabbitmq_rpc_client_context(
    rpc_client_name: str, settings: RabbitSettings, **kwargs
) -> AsyncIterator[RabbitMQRPCClient]:
    """
    Adapter to create and close a RabbitMQRPCClient using an async context manager.
    """
    rpc_client = await RabbitMQRPCClient.create(
        client_name=rpc_client_name, settings=settings, **kwargs
    )
    try:
        yield rpc_client
    finally:
        await rpc_client.close()
