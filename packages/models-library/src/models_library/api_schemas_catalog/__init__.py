from typing import Final

from pydantic.v1 import parse_obj_as

from ..rabbitmq_basic_types import RPCNamespace

CATALOG_RPC_NAMESPACE: Final[RPCNamespace] = parse_obj_as(RPCNamespace, "catalog")
