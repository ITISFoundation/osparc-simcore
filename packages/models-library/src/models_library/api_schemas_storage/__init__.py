from typing import Final

from pydantic import TypeAdapter

from ..rabbitmq_basic_types import RPCNamespace

STORAGE_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(RPCNamespace).validate_python(
    "storage"
)
