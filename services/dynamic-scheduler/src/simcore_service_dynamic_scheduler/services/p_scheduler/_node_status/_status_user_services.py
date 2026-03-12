from typing import Final

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Status1 as ContainerState
from models_library.projects_nodes_io import NodeID
from servicelib.rabbitmq.rpc_interfaces.dynamic_sidecar.containers import (
    containers_docker_inspect,
)

from ...rabbitmq import get_rabbitmq_rpc_client
from ._models import ComponentPresence

_CONTAINER_STATE_TO_PRESENCE: Final[dict[ContainerState, ComponentPresence]] = {
    ContainerState.created: ComponentPresence.STARTING,
    ContainerState.restarting: ComponentPresence.STARTING,
    ContainerState.running: ComponentPresence.RUNNING,
    ContainerState.paused: ComponentPresence.FAILED,
    ContainerState.removing: ComponentPresence.STARTING,
    ContainerState.exited: ComponentPresence.FAILED,
    ContainerState.dead: ComponentPresence.FAILED,
}
assert len(_CONTAINER_STATE_TO_PRESENCE) == len(ContainerState), (
    "Not all ContainerStates are mapped to ComponentPresence"
)  # nosec

# Worst-first ordering: higher index = worse state
_PRESENCE_SEVERITY: Final[dict[ComponentPresence, int]] = {
    ComponentPresence.RUNNING: 0,
    ComponentPresence.STARTING: 1,
    ComponentPresence.ABSENT: 2,
    ComponentPresence.FAILED: 3,
}


async def get_user_services_presence(app: FastAPI, node_id: NodeID) -> ComponentPresence:
    containers_inspect = await containers_docker_inspect(
        get_rabbitmq_rpc_client(app), node_id=node_id, only_status=True
    )

    if not containers_inspect:
        return ComponentPresence.ABSENT

    containers_states = [ContainerState(x["State"]) for x in containers_inspect.values()]

    presences = [_CONTAINER_STATE_TO_PRESENCE[s] for s in containers_states]

    return max(presences, key=lambda p: _PRESENCE_SEVERITY[p])
