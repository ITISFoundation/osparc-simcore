"""Base classes and shared functionality for RPC subclients."""

from typing import Any

from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from models_library.users import UserID
from servicelib.rabbitmq import RabbitMQRPCClient


class BaseRpcApi:
    """Base class for all RPC API subclients."""

    def __init__(self, rpc_client: RabbitMQRPCClient, namespace: RPCNamespace):
        self._rpc_client = rpc_client
        self._namespace = namespace

    async def _request(
        self,
        method_name: RPCMethodName,
        *,
        product_name: ProductName,
        user_id: UserID,
        **kwargs: Any
    ) -> Any:
        return await self._rpc_client.request(
            self._namespace,
            method_name,
            product_name=product_name,
            user_id=user_id,
            **kwargs
        )
