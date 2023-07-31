from models_library.api_schemas_directorv2.constants import (
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from models_library.projects_nodes import NodeID


def get_compose_namespace(node_uuid: NodeID) -> str:
    # To avoid collisions for started docker resources a unique identifier is computed:
    # - avoids container level collisions on same node
    # - avoids volume level collisions on same node
    return f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_{node_uuid}"
