from models_library.rabbitmq_basic_types import RPCNamespace

from ._client import RabbitMQClient
from ._client_rpc import RabbitMQRPCClient
from ._constants import BIND_TO_ALL_TOPICS, RPC_REQUEST_DEFAULT_TIMEOUT_S
from ._errors import (
    RemoteMethodNotRegisteredError,
    RPCNotInitializedError,
    RPCServerError,
)
from ._models import ConsumerTag, ExchangeName, QueueName
from ._rpc_router import RPCRouter
from ._utils import is_rabbitmq_responsive, wait_till_rabbitmq_responsive

__all__: tuple[str, ...] = (
    "BIND_TO_ALL_TOPICS",
    "ConsumerTag",
    "ExchangeName",
    "is_rabbitmq_responsive",
    "QueueName",
    "RabbitMQClient",
    "RabbitMQRPCClient",
    "RemoteMethodNotRegisteredError",
    "RPC_REQUEST_DEFAULT_TIMEOUT_S",
    "RPCNamespace",
    "RPCNotInitializedError",
    "RPCRouter",
    "RPCServerError",
    "wait_till_rabbitmq_responsive",
)

# nopycln: file
