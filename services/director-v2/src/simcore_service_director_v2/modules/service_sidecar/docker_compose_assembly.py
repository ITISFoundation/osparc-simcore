from copy import deepcopy
from typing import Any, Dict

import yaml
from aiohttp.web import Application

from .config import ServiceSidecarSettings, get_settings

CONTAINER_NAME = "container"
BASE_SERVICE_SPEC: Dict[str, Any] = {
    "version": "3.7",
    "services": {CONTAINER_NAME: {}},
}


def inject_traefik_configuration(
    service_spec: Dict[str, Any],
    target_container: str,
    service_sidecar_network_name: str,
    simcore_traefik_zone: str,
    service_port: str = "8888",  # TODO: fetch from the service label
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


async def assemble_spec(
    app: Application,
    service_key: str,
    service_tag: str,
    service_sidecar_network_name: str,
    simcore_traefik_zone: str,
) -> str:
    """returns a docker-compose spec which will be use by the service-sidecar to start the service """
    settings: ServiceSidecarSettings = get_settings(app)

    service_spec = deepcopy(BASE_SERVICE_SPEC)
    service_spec["services"][CONTAINER_NAME] = {
        "image": f"{settings.resolved_registry_url}/{service_key}:{service_tag}"
    }

    inject_traefik_configuration(
        service_spec,
        target_container=CONTAINER_NAME,
        service_sidecar_network_name=service_sidecar_network_name,
        simcore_traefik_zone=simcore_traefik_zone,
    )

    return yaml.safe_dump(service_spec)
