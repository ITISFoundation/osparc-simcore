import functools
import inspect
import logging
import pickle
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from aio_pika import IncomingMessage
from faststream import BaseMiddleware
from faststream.rabbit import RabbitBroker, RabbitMessage
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from pydantic import PositiveInt
from settings_library.rabbit import RabbitSettings

from ._client_base import RabbitMQClientBase
from ._constants import RPC_REQUEST_DEFAULT_TIMEOUT_S
from ._errors import RemoteMethodNotRegisteredError, RPCNotInitializedError
from ._models import RPCNamespacedMethodName
from ._rpc_router import RPCRouter

_logger = logging.getLogger(__name__)


def _to_bytes(obj: Any) -> bytes:
    return pickle.dumps(obj)


def _from_bytes(encoded_str: bytes) -> Any:
    return pickle.loads(encoded_str)  # noqa: S301


async def _decoding_parser(
    msg: IncomingMessage,
    original_parser: Callable[[IncomingMessage], Awaitable[RabbitMessage]],
) -> RabbitMessage:
    parsed_message = await original_parser(msg)
    parsed_message.body = _from_bytes(parsed_message.body)
    return parsed_message


class EncodingMiddleware(BaseMiddleware):
    async def on_publish(
        self,
        msg: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        _ = args, kwargs

        _logger.debug("MDLR: publish msg=%r", msg)
        return _to_bytes(msg)


@dataclass
class RabbitMQRPCClient(RabbitMQClientBase):
    _broker: RabbitBroker | None = None

    @classmethod
    def create(
        cls,
        *,
        client_name: str,
        settings: RabbitSettings,
        **kwargs,
    ) -> "RabbitMQRPCClient":
        client = cls(client_name=client_name, settings=settings, **kwargs)
        client._rpc_initialize()
        return client

    def _rpc_initialize(self) -> None:
        self._broker: RabbitBroker = RabbitBroker(
            self.settings.dsn,
            log_level=logging.DEBUG,
            # NOTE
            parser=_decoding_parser,
            middlewares=[EncodingMiddleware],
        )

    async def start(self) -> None:
        # TODO: register echo handler ? might help with detecting missing remote side

        # start after all halnder have registered the routes
        await self._broker.start()

    async def close(self) -> None:
        if self._broker is not None:
            await self._broker.close()

    async def request(
        self,
        namespace: RPCNamespace,
        method_name: RPCMethodName,
        *,
        timeout_s: PositiveInt | None = RPC_REQUEST_DEFAULT_TIMEOUT_S,
        **kwargs: Any,
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

        if self._broker is None:
            raise RPCNotInitializedError

        namespaced_method_name = RPCNamespacedMethodName.from_namespace_and_method(
            namespace, method_name
        )

        # quick check to se eif remote handler replies
        dummy_namesapce = RPCNamespacedMethodName.from_namespace_and_method(
            namespace, ""
        )
        try:
            await self._broker.request({}, queue=dummy_namesapce)
        except TimeoutError as e:
            raise RemoteMethodNotRegisteredError(
                method_name=dummy_namesapce,
                incoming_message="",
            ) from e

        try:
            message = await self._broker.request(
                kwargs, queue=namespaced_method_name, timeout=timeout_s
            )
            return _from_bytes(message.body)
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

        if self._broker is None:
            raise RPCNotInitializedError

        namespaced_method_name = RPCNamespacedMethodName.from_namespace_and_method(
            namespace, method_name
        )

        async def _warpped_handler(*args, **kwargs) -> bytes:
            result = handler(*args, **kwargs)
            if inspect.iscoroutinefunction(handler):
                await result
            return _to_bytes(result)

        self._broker.subscriber(namespaced_method_name)(_warpped_handler)
        # always subscribe an empty handler to the namespce (used for fast querying to figure out if any method is registerd)

        def _empty_handler(*args, **kwargs) -> None:
            """
            This is a dummy handler that does nothing.
            It is used to register the namespace so that we can query it later
            to see if any method is registered.
            """
            _ = args, kwargs

        self._broker.subscriber(
            RPCNamespacedMethodName.from_namespace_and_method(namespace, "")
        )(_empty_handler)

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

        if self._broker is None:
            raise RPCNotInitializedError

        _logger.debug("nothing to unsubscribe, feature not supported")
        # await self._rpc.unregister(handler)


# TODO: below needs to change, since we register and unregister handlers during tests and cannot after they are initialized
@asynccontextmanager
async def rabbitmq_rpc_client_context(
    rpc_client_name: str, settings: RabbitSettings, **kwargs
) -> AsyncIterator[RabbitMQRPCClient]:
    """
    Adapter to create and close a RabbitMQRPCClient using an async context manager.
    """
    rpc_client = RabbitMQRPCClient.create(
        client_name=rpc_client_name, settings=settings, **kwargs
    )
    try:
        yield rpc_client
    finally:
        await rpc_client.close()


@asynccontextmanager
async def rpc_server_lfespan(rpc_client: RabbitMQRPCClient) -> AsyncIterator[None]:
    try:
        await rpc_client.start()
        yield None
    finally:
        await rpc_client.close()
