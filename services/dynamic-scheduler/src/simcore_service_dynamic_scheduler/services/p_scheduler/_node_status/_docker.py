import asyncio
from typing import Final

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import TaskState
from pydantic import NonNegativeInt
from servicelib.fastapi.docker import get_remote_docker_client

from simcore_service_dynamic_scheduler.services.common_interface import NodeID

from ._models import ComponentPresence, ServiceName, ServicesPresence

_PREFIX_DY_SIDECAR: Final[str] = "dy-sidecar_"
_PREFIX_DY_PROXY: Final[str] = "dy-proxy_"
_NUMBER_OF_DOCKER_DY_SERVICES_PER_NODE: Final[NonNegativeInt] = 2


_DOCKER_TASK_STATE_TO_SERVICE_STATE: Final[dict[str, ComponentPresence]] = {
    TaskState.new: ComponentPresence.STARTING,
    TaskState.allocated: ComponentPresence.STARTING,
    TaskState.pending: ComponentPresence.STARTING,
    TaskState.assigned: ComponentPresence.STARTING,
    TaskState.accepted: ComponentPresence.STARTING,
    TaskState.preparing: ComponentPresence.STARTING,
    TaskState.ready: ComponentPresence.STARTING,
    TaskState.starting: ComponentPresence.STARTING,
    TaskState.running: ComponentPresence.RUNNING,
    TaskState.complete: ComponentPresence.ABSENT,
    TaskState.shutdown: ComponentPresence.ABSENT,
    TaskState.failed: ComponentPresence.FAILED,
    TaskState.rejected: ComponentPresence.FAILED,
    TaskState.remove: ComponentPresence.ABSENT,
    TaskState.orphaned: ComponentPresence.FAILED,
}
assert len(_DOCKER_TASK_STATE_TO_SERVICE_STATE) == len(TaskState), (
    "Not all Docker TaskStates are mapped to ComponentPresence"
)  # nosec


async def _get_service_presence(app: FastAPI, service_name: ServiceName) -> ComponentPresence:
    docker = get_remote_docker_client(app)

    tasks = await docker.tasks.list(filters={"service": service_name})

    if not tasks:
        return ComponentPresence.ABSENT

    last_task = sorted(tasks, key=lambda task: task["UpdatedAt"])[-1]
    task_state: str = last_task["Status"]["State"]

    return _DOCKER_TASK_STATE_TO_SERVICE_STATE[task_state]


async def get_services_presence(app: FastAPI, node_id: NodeID) -> ServicesPresence | None:
    docker = get_remote_docker_client(app)
    matching_services: list[dict] = [
        dict(x) for x in await docker.services.list(filters={"label": f"io.simcore.runtime.node-id={node_id}"})
    ]

    if len(matching_services) == 0:
        return None

    if len(matching_services) == 1:
        # could be a legacy service or a dynamic-sidecar where the proxy did not start yet
        service_inspect = matching_services[0]

        name = service_inspect["Spec"]["Name"]
        if name.startswith(_PREFIX_DY_SIDECAR):
            return ServicesPresence(
                dy_sidecar=await _get_service_presence(app, name),
                dy_proxy=ComponentPresence.ABSENT,
            )

        return ServicesPresence(legacy=await _get_service_presence(app, name))

    if len(matching_services) == _NUMBER_OF_DOCKER_DY_SERVICES_PER_NODE:
        # dynamic sidecar services are both up
        proxy_name = None
        sidecar_name = None

        for service_inspect in matching_services:
            name = service_inspect["Spec"]["Name"]
            if name.startswith(_PREFIX_DY_SIDECAR):
                sidecar_name = name
            elif name.startswith(_PREFIX_DY_PROXY):
                proxy_name = name
            else:
                msg = f"Unexpected: could not categorize service with name {name} for node_id {node_id}"
                raise RuntimeError(msg)

        if not sidecar_name or not proxy_name:
            msg = f"Unexpected: could not find both sidecar and proxy services for node_id {node_id}"
            raise RuntimeError(msg)

        sidecar_presence, proxy_presence = await asyncio.gather(
            _get_service_presence(app, sidecar_name), _get_service_presence(app, proxy_name)
        )
        return ServicesPresence(dy_sidecar=sidecar_presence, dy_proxy=proxy_presence)

    msg = f"Unexpected: state for {node_id=}: {matching_services=}"
    raise RuntimeError(msg)
