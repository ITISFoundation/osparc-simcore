import logging
from collections import deque
from typing import Any, Dict, List

from aiohttp.web import Application

from ..docker_compose_assembly import assemble_spec
from .handlers_base import BaseEventHandler
from .models import (
    DockerContainerInspect,
    DockerStatus,
    MonitorData,
    DynamicSidecarStatus,
)
from .dynamic_sidecar_api import get_api_client

logger = logging.getLogger(__name__)


def parse_containers_inspect(
    containers_inspect: Dict[str, Any]
) -> List[DockerContainerInspect]:
    results = deque()

    for container_id in containers_inspect:
        container_inspect_data = containers_inspect[container_id]
        docker_container_inspect = DockerContainerInspect(
            status=DockerStatus(container_inspect_data["State"]["Status"]),
            name=container_inspect_data["Name"],
            id=container_inspect_data["Id"],
        )
        results.append(docker_container_inspect)
    return list(results)


class RunDockerComposeUp(BaseEventHandler):
    """Runs the docker-compose up command when and composes the spec if a service requires it"""

    @classmethod
    async def will_trigger(cls, previous: MonitorData, current: MonitorData) -> bool:
        return (
            current.dynamic_sidecar.overall_status.status == DynamicSidecarStatus.OK
            and current.dynamic_sidecar.is_available == True
            and current.dynamic_sidecar.compose_spec_submitted == False
        )

    @classmethod
    async def action(
        cls, app: Application, previous: MonitorData, current: MonitorData
    ) -> None:
        logger.debug("Getting docker compose spec for service %s", current.service_name)

        api_client = get_api_client(app)
        dynamic_sidecar_endpoint = current.dynamic_sidecar.endpoint

        # creates a docker compose spec given the service key and tag
        compose_spec = await assemble_spec(
            app=app,
            service_key=current.service_key,
            service_tag=current.service_tag,
            paths_mapping=current.paths_mapping,
            compose_spec=current.compose_spec,
            target_container=current.target_container,
            dynamic_sidecar_network_name=current.dynamic_sidecar_network_name,
            simcore_traefik_zone=current.simcore_traefik_zone,
            service_port=current.service_port,
        )

        compose_spec_accepted = await api_client.run_docker_compose_up(
            dynamic_sidecar_endpoint, compose_spec
        )

        # singal there is a problem with the dynamic-sidecar
        if not compose_spec_accepted:
            current.dynamic_sidecar.overall_status.update_failing_status(
                "Could not run docker-compose up. Ask an admin to check director logs for details."
            )


class ServicesInspect(BaseEventHandler):
    """Inspects all spawned containers for the sidecar-service"""

    @classmethod
    async def will_trigger(cls, previous: MonitorData, current: MonitorData) -> bool:
        return (
            current.dynamic_sidecar.overall_status.status == DynamicSidecarStatus.OK
            and current.dynamic_sidecar.is_available == True
            and current.dynamic_sidecar.compose_spec_submitted == True
        )

    @classmethod
    async def action(
        cls, app: Application, previous: MonitorData, current: MonitorData
    ) -> None:
        api_client = get_api_client(app)
        dynamic_sidecar_endpoint = current.dynamic_sidecar.endpoint

        containers_inspect = await api_client.containers_inspect(
            dynamic_sidecar_endpoint
        )
        if containers_inspect is None:
            # this means that the service was degrated and we need to do something?
            current.dynamic_sidecar.overall_status.update_failing_status(
                f"Could not get containers_inspect for {current.service_name}. "
                "Ask and admin to check director logs for details."
            )

        # parse and store data from container
        current.dynamic_sidecar.containers_inspect = parse_containers_inspect(
            containers_inspect
        )


# register all handlers defined in this module here
# A list is essential to guarantee execution order
REGISTERED_HANDLERS: List[BaseEventHandler] = [
    RunDockerComposeUp,
    ServicesInspect,
]
