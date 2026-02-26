from typing import Final

from aiodocker import DockerError
from fastapi import FastAPI, status
from pydantic import NonNegativeInt
from servicelib.fastapi.docker import get_remote_docker_client

from simcore_service_dynamic_scheduler.services.common_interface import NodeID

from ._models import ServiceCategory, ServiceName

_PREFIX_DY_SIDECAR: Final[str] = "dy-sidecar_"
_PREFIX_DY_PROXY: Final[str] = "dy-proxy_"
_NUMBER_OF_DY_SERVICES_PER_NODE: Final[NonNegativeInt] = 2


async def get_service_category(app: FastAPI, node_id: NodeID) -> dict[ServiceCategory, ServiceName]:
    docker = get_remote_docker_client(app)
    matching_services = await docker.services.list(filters={"label": f"io.simcore.runtime.node-id={node_id}"})

    detected_services: dict[ServiceCategory, ServiceName] = {}

    if len(matching_services) == 0:
        return {}

    if len(matching_services) == 1:
        # could be a legacy service or a dynamic-sidecar where the proxy did not start yet
        service = matching_services[0]

        name = service["Spec"]["Name"]
        if name.startswith(_PREFIX_DY_SIDECAR):
            detected_services[ServiceCategory.DY_SIDECAR] = name
        else:
            detected_services[ServiceCategory.LEGACY] = name

    if len(matching_services) == _NUMBER_OF_DY_SERVICES_PER_NODE:
        # dynamic sidecar services are both up
        for service in matching_services:
            name = service["Spec"]["Name"]
            if name.startswith(_PREFIX_DY_SIDECAR):
                detected_services[ServiceCategory.DY_SIDECAR] = name
            elif name.startswith(_PREFIX_DY_PROXY):
                detected_services[ServiceCategory.DY_PROXY] = name
            else:
                msg = f"Could not categorize service with name {name} for node_id {node_id}"
                raise RuntimeError(msg)

    if len(matching_services) > _NUMBER_OF_DY_SERVICES_PER_NODE:
        msg = f"Unexpected number of services for {node_id=}: {matching_services=}"
        raise RuntimeError(msg)

    return detected_services


async def is_service_running(app: FastAPI, service_name: ServiceName) -> bool:
    docker = get_remote_docker_client(app)
    try:
        service_tasks = await docker.tasks.list(filters={"service": f"{service_name}", "desired-state": "running"})
    except DockerError as e:
        # If the service is not found, we consider it as not running
        if e.status == status.HTTP_404_NOT_FOUND:
            return False
        raise
    return len(service_tasks) == 1
