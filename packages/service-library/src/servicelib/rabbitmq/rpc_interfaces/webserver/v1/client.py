"""Main WebServer RPC Client."""

from models_library.rabbitmq_basic_types import RPCNamespace
from servicelib.rabbitmq import RabbitMQRPCClient

from .api_keys import ApiKeysRpcApi
from .functions import FunctionsRpcApi
from .licenses import LicensesRpcApi
from .projects import ProjectsRpcApi


class WebServerRpcClient:
    """Main RPC client for webserver services."""

    def __init__(
        self,
        rpc_client: RabbitMQRPCClient,
        namespace: RPCNamespace,
    ):
        self._rpc_client = rpc_client
        self._namespace = namespace

        # Initialize subclients
        self.projects = ProjectsRpcApi(rpc_client, namespace)
        self.licenses = LicensesRpcApi(rpc_client, namespace)
        self.functions = FunctionsRpcApi(rpc_client, namespace)
        self.api_keys = ApiKeysRpcApi(rpc_client, namespace)

    @property
    def namespace(self) -> RPCNamespace:
        return self._namespace

    async def close(self) -> None:
        """Close the underlying RPC client connection."""
        # Delegate to the underlying client if it has a close method
        if hasattr(self._rpc_client, "close"):
            await self._rpc_client.close()
