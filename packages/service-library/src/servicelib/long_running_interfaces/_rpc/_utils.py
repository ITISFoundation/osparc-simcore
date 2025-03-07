from typing import Final

from models_library.rabbitmq_basic_types import RPCNamespace
from servicelib.long_running_interfaces._models import UniqueRPCID

_RPC_NAME: Final[str] = "long_running_interface"


def get_rpc_namespace(unique_rpc_id: UniqueRPCID) -> RPCNamespace:
    return RPCNamespace.from_entries(
        {"name": _RPC_NAME, "unique_rpc_id": unique_rpc_id}
    )
