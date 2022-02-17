from models_library.projects_nodes import NodeID

from ...models.schemas.constants import DYNAMIC_SIDECAR_SERVICE_PREFIX


def get_compose_namespace(node_uuid: NodeID, swarm_stack_name: str) -> str:
    # To avoid collisions for started docker resources a unique identifier is computed:
    # - avoids container level collisions on same node
    # - avoids volume level collisions on same node
    # - avoids collisions with multiple deployments of osparc on same swarm
    return f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_{node_uuid}_{swarm_stack_name}"
