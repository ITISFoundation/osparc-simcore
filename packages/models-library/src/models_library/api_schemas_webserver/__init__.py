from typing import Final

from pydantic import TypeAdapter

from ..rabbitmq_basic_types import RPCNamespace

WEBSERVER_RPC_NAMESPACE: Final[RPCNamespace] = RPCNamespace("webserver")
