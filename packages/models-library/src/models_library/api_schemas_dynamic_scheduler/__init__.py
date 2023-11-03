from typing import Final

from pydantic import parse_obj_as

from ..rabbitmq_basic_types import RPCNamespace

DYNAMIC_SCHEDULER_RPC_NAMESPACE: Final[RPCNamespace] = parse_obj_as(
    RPCNamespace, "dynamic-scheduler"
)
