from pathlib import Path
from typing import Final

from models_library.projects_nodes_io import NodeID


def get_source(run_id: str, node_id: NodeID, full_volume_path: Path) -> str:
    # NOTE: volume name is not trimmed here, but it's ok for the tests
    reversed_path = f"{full_volume_path}"[::-1].replace("/", "_")
    return f"dyv_{run_id}_{node_id}_{reversed_path}"


VOLUMES_TO_CREATE: Final[list[str]] = [
    "inputs",
    "outputs",
    "workspace",
    "work",
    "shared-store",
]
