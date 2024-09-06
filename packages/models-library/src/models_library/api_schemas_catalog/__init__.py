from typing import Final

from ..rabbitmq_basic_types import RPCNamespace

CATALOG_RPC_NAMESPACE: Final[RPCNamespace] = RPCNamespace.model_validate("catalog")
