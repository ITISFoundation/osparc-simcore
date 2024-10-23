from typing import Final

from pydantic import TypeAdapter

from ..rabbitmq_basic_types import RPCNamespace

CLUSTERS_KEEPER_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(
    RPCNamespace
).validate_python("clusters-keeper")
