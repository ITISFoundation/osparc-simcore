import socket

from models_library.projects_nodes import NodeID

MAX_ALLOWED_SERVICE_NAME_LENGTH: int = 63


def unused_port() -> int:
    """Returns a port that is unused on the current host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _strip_service_name(service_name: str) -> str:
    """returns: the maximum allowed service name in docker swarm"""
    return service_name[:MAX_ALLOWED_SERVICE_NAME_LENGTH]


def assemble_service_name(service_prefix: str, node_uuid: NodeID) -> str:
    return _strip_service_name("_".join([service_prefix, str(node_uuid)]))
