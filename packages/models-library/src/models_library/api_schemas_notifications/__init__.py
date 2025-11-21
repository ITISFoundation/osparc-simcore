from typing import Final

from pydantic import TypeAdapter

from ..rabbitmq_basic_types import RPCNamespace
from ._notifications import NotificationRequest

NOTIFICATIONS_RPC_NAMESPACE: Final[RPCNamespace] = TypeAdapter(
    RPCNamespace
).validate_python("notifications")


__all__: tuple[str, ...] = ("NotificationRequest",)

# nopycln: file
