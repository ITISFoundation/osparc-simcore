"""Base classes and shared functionality for RPC subclients."""

from typing import Any

from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from models_library.users import UserID
from servicelib.rabbitmq import RabbitMQRPCClient


class BaseRpcApi:
    """Base class for all RPC API subclients."""

    def __init__(
        self,
        rpc_client: RabbitMQRPCClient,
        namespace: RPCNamespace,
        *,
        rpc_request_kwargs: dict[str, Any] | None = None,
    ):
        self._rpc_client = rpc_client
        self._namespace = namespace
        # extra kwargs to be passed to every rpc request
        self._rpc_request_kwargs = rpc_request_kwargs or {}

    async def _request(
        self,
        method_name: RPCMethodName,
        *,
        product_name: ProductName,
        user_id: UserID,
        **optional_kwargs: Any,
    ) -> Any:

        return await self._request_without_authentication(
            method_name,
            product_name=product_name,
            user_id=user_id,
            **optional_kwargs,
        )

    async def _request_without_authentication(
        self, method_name: RPCMethodName, *, product_name: ProductName, **kwargs: Any
    ) -> Any:

        assert self._rpc_request_kwargs.keys().isdisjoint(kwargs.keys()), (
            "Conflict between request extras and kwargs"
            "Please rename the conflicting keys."
        )

        return await self._rpc_client.request(
            self._namespace,
            method_name,
            product_name=product_name,
            **kwargs,
            **self._rpc_request_kwargs,
        )
