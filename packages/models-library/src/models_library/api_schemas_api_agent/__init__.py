from typing import Final

from pydantic import parse_obj_as

from ..rabbitmq_basic_types import RPCNamespace

AGENT_RPC_NAMESPACE: Final[RPCNamespace] = parse_obj_as(RPCNamespace, "agent")
