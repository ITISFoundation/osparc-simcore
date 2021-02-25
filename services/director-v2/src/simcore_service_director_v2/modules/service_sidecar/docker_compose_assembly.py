from copy import deepcopy
from typing import Any, Dict, Optional

import yaml
from aiohttp.web import Application

from .config import ServiceSidecarSettings, get_settings
from ...models.domains.dynamic_sidecar import PathsMappingModel, ComposeSpecModel

CONTAINER_NAME = "container"
BASE_SERVICE_SPEC: Dict[str, Any] = {
    "version": "3.7",
    "services": {CONTAINER_NAME: {}},
}


def _inject_traefik_configuration(
    service_spec: Dict[str, Any],
    target_container: str,
    service_sidecar_network_name: str,
    simcore_traefik_zone: str,
    service_port: int,
) -> None:
    """Injects configuration to allow the service to be accessible on the uuid.services.SERVICE_DNS"""

    # add external network to existing networks defined in the container
    service_spec["networks"] = {
        service_sidecar_network_name: {
            "external": {"name": service_sidecar_network_name},
            "driver": "overlay",
        }
    }

    # Inject Traefik rules on target container
    target_container_spec = service_spec["services"][target_container]

    # attach overlay network to container
    container_networks = target_container_spec.get("networks", [])
    container_networks.append(service_sidecar_network_name)
    target_container_spec["networks"] = container_networks

    # expose spaned container to the internet
    labels = target_container_spec.get("labels", [])
    for label in [
        f"io.simcore.zone={simcore_traefik_zone}",
        "traefik.enable=true",
        f"traefik.http.services.{target_container}.loadbalancer.server.port={service_port}",
        f"traefik.http.routers.{target_container}.entrypoints=http",
        f"traefik.http.routers.{target_container}.rule=PathPrefix(`/`)",
    ]:
        labels.append(label)

    # put back updated labels
    target_container_spec["labels"] = labels


def _assemble_from_service_key_and_tag(
    app: Application,
    service_key: str,
    service_tag: str,
):
    settings: ServiceSidecarSettings = get_settings(app)

    service_spec = deepcopy(BASE_SERVICE_SPEC)
    service_spec["services"][CONTAINER_NAME] = {
        "image": f"{settings.resolved_registry_url}/{service_key}:{service_tag}"
    }

    return service_spec


async def assemble_spec(
    app: Application,
    service_key: str,
    service_tag: str,
    paths_mapping: PathsMappingModel,
    compose_spec: ComposeSpecModel,
    target_container: Optional[str],
    service_sidecar_network_name: str,
    simcore_traefik_zone: str,
    service_port: int,
) -> str:
    """returns a docker-compose spec which will be use by the service-sidecar to start the service """

    container_name = target_container
    service_spec = compose_spec

    # when no compose yaml file was provided
    if service_spec is None:
        service_spec = _assemble_from_service_key_and_tag(
            app=app, service_key=service_key, service_tag=service_tag
        )
        container_name = CONTAINER_NAME
    else:
        # TODO: need to be sorted out:
        # - inject paths mapping
        # - some escaping for service name and version?
        pass

    _inject_traefik_configuration(
        service_spec,
        target_container=container_name,
        service_sidecar_network_name=service_sidecar_network_name,
        simcore_traefik_zone=simcore_traefik_zone,
        service_port=service_port,
    )
    return yaml.safe_dump(service_spec)
