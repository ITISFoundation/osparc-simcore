from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_basic_types import RPCNamespace


def get_rpc_namespace(node_id: NodeID) -> RPCNamespace:
    return RPCNamespace.from_entries({"service": "dy-sidecar", "node_id": f"{node_id}"})
