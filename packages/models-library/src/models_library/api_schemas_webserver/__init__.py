from typing import Final

from pydantic import TypeAdapter

from ..rabbitmq_basic_types import RPCNamespace

WEBSERVER_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(
    RPCNamespace
).validate_python("webserver")


def get_webserver_rpc_namespace(webserver_host: str) -> RPCNamespace:
    """
    Returns the RPC namespace to select among the different webserver services

    e.g. webserver, wb-api-server, wb-garbage-collector, etc.

    On the service side, this is defined in settings.WEBSERVER_HOST
    """
    return TypeAdapter(RPCNamespace).validate_python(webserver_host)
