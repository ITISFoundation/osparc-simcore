from typing import Final

from pydantic import TypeAdapter

from ..rabbitmq_basic_types import RPCNamespace
from . import clusters, dynamic_services

assert clusters  # nosec
assert dynamic_services  # nosec


DIRECTOR_V2_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(
    RPCNamespace
).validate_python("director-v2")


__all__: tuple[str, ...] = (
    "clusters",
    "dynamic_services",
)
