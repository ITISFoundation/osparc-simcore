import asyncio
import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import aio_pika
from pydantic import PositiveInt

from ..logging_utils import log_context
from ._client_base import RabbitMQClientBase
from ._errors import RemoteMethodNotRegisteredError, RPCNotInitializedError
from ._models import RPCMethodName, RPCNamespace, RPCNamespacedMethodName
from ._rpc_router import RPCRouter
from ._utils import get_rabbitmq_client_unique_name

_logger = logging.getLogger(__name__)


@dataclass
class RabbitMQClient(RabbitMQClientBase):
    _rpc_connection: aio_pika.abc.AbstractConnection | None = None
    _rpc_channel: aio_pika.abc.AbstractChannel | None = None
    _rpc: aio_pika.patterns.RPC | None = None

    async def rpc_initialize(self) -> None:
        self._rpc_connection = await aio_pika.connect_robust(
            self.settings.dsn,
            client_properties={
                "connection_name": f"{get_rabbitmq_client_unique_name(self.client_name)}.rpc"
            },
        )
        self._rpc_channel = await self._rpc_connection.channel()

        self._rpc = aio_pika.patterns.RPC(self._rpc_channel)
        await self._rpc.initialize()

    async def close(self) -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg=f"{self.client_name} closing connection to RabbitMQ",
        ):
            # rpc is not always initialized
            if self._rpc is not None:
                await self._rpc.close()
            if self._rpc_channel is not None:
                await self._rpc_channel.close()
            if self._rpc_connection is not None:
                await self._rpc_connection.close()

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
            raise

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

    async def rpc_register_router(
        self,
        router: RPCRouter,
        namespace: RPCNamespace,
        *handler_args,
        **handler_kwargs,
    ) -> None:
        for rpc_method_name, handler in router.routes.items():
            await self.rpc_register_handler(
                namespace,
                rpc_method_name,
                functools.partial(handler, *handler_args, **handler_kwargs),
            )

    async def rpc_unregister_handler(self, handler: Callable[..., Any]) -> None:
        """Unbind a locally added `handler`"""

        if self._rpc is None:
            raise RPCNotInitializedError

        await self._rpc.unregister(handler)
