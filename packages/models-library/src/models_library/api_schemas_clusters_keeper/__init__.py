from typing import Final

from ..rabbitmq_basic_types import RPCNamespace

CLUSTERS_KEEPER_RPC_NAMESPACE: Final[RPCNamespace] = RPCNamespace.model_validate(
    "clusters-keeper"
)
