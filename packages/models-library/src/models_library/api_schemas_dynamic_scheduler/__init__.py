from typing import Final

from pydantic import TypeAdapter

from ..rabbitmq_basic_types import RPCNamespace

DYNAMIC_SCHEDULER_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(
    RPCNamespace
).validate_python("dynamic-scheduler")
