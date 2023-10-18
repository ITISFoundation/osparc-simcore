from typing import Final

from pydantic import parse_obj_as
from servicelib.rabbitmq import RPCNamespace

PAYMENTS_RPC_NAMESPACE: Final[RPCNamespace] = parse_obj_as(RPCNamespace, "payments")
