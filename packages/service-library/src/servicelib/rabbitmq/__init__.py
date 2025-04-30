from models_library.rabbitmq_basic_types import RPCNamespace

from ._client import RabbitMQClient
from ._client_rpc import RabbitMQRPCClient, rabbitmq_rpc_client_context
from ._constants import BIND_TO_ALL_TOPICS, RPC_REQUEST_DEFAULT_TIMEOUT_S
from ._errors import (
    RemoteMethodNotRegisteredError,
    RPCInterfaceError,
    RPCNotInitializedError,
    RPCServerError,
)
from ._models import ConsumerTag, ExchangeName, QueueName
from ._rpc_router import RPCRouter
from ._utils import is_rabbitmq_responsive, wait_till_rabbitmq_responsive

__all__: tuple[str, ...] = (
    "BIND_TO_ALL_TOPICS",
    "RPC_REQUEST_DEFAULT_TIMEOUT_S",
    "ConsumerTag",
    "ExchangeName",
    "QueueName",
    "RPCInterfaceError",
    "RPCNamespace",
    "RPCNotInitializedError",
    "RPCRouter",
    "RPCServerError",
    "RabbitMQClient",
    "RabbitMQRPCClient",
    "RemoteMethodNotRegisteredError",
    "is_rabbitmq_responsive",
    "rabbitmq_rpc_client_context",
    "wait_till_rabbitmq_responsive",
)

# nopycln: file
