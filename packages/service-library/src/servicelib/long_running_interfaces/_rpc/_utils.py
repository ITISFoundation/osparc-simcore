from typing import Final

from models_library.rabbitmq_basic_types import RPCNamespace
from servicelib.long_running_interfaces._models import LongRunningNamespace

_RPC_NAME: Final[str] = "long_running_interface"


def get_rpc_namespace(long_running_namepsace: LongRunningNamespace) -> RPCNamespace:
    return RPCNamespace.from_entries(
        {"name": _RPC_NAME, "long_running_namepsace": long_running_namepsace}
    )
