from typing import Final

from pydantic import TypeAdapter

from ..rabbitmq_basic_types import RPCNamespace

WEBSERVER_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(
    # NOTE: deprecated! Use app.state.settings.WEBSERVER_RPC_NAMESPACE
    RPCNamespace
).validate_python("webserver")
