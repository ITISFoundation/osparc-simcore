from copy import deepcopy
from typing import Any, Dict, Optional

import yaml
from fastapi.applications import FastAPI
from pydantic import PositiveInt

from ...models.domains.dynamic_sidecar import ComposeSpecModel, PathsMappingModel
from .config import DynamicSidecarSettings

CONTAINER_NAME = "container"
BASE_SERVICE_SPEC: Dict[str, Any] = {
    "version": "3.8",
    "services": {CONTAINER_NAME: {}},
}


def _inject_traefik_configuration(
    service_spec: Dict[str, Any],
    target_container: str,
    dynamic_sidecar_network_name: str,
    simcore_traefik_zone: str,
    service_port: PositiveInt,
) -> None:
    """Injects configuration to allow the service to be accessible on the uuid.services.SERVICE_DNS"""

    # add external network to existing networks defined in the container
    service_spec["networks"] = {
        dynamic_sidecar_network_name: {
            "external": {"name": dynamic_sidecar_network_name},
            "driver": "overlay",
        }
    }

    # Inject Traefik rules on target container
    target_container_spec = service_spec["services"][target_container]

    # attach overlay network to container
    container_networks = target_container_spec.get("networks", [])
    container_networks.append(dynamic_sidecar_network_name)
    target_container_spec["networks"] = container_networks

    # expose spaned container to the internet
    labels = target_container_spec.get("labels", [])
    labels.extend(
        [
            f"io.simcore.zone={simcore_traefik_zone}",
            "traefik.enable=true",
            f"traefik.http.services.{target_container}.loadbalancer.server.port={service_port}",
            f"traefik.http.routers.{target_container}.entrypoints=http",
            f"traefik.http.routers.{target_container}.rule=PathPrefix(`/`)",
        ]
    )

    # put back updated labels
    target_container_spec["labels"] = labels


def _assemble_from_service_key_and_tag(
    resolved_registry_url: str,
    service_key: str,
    service_tag: str,
):
    service_spec = deepcopy(BASE_SERVICE_SPEC)
    service_spec["services"][CONTAINER_NAME] = {
        "image": f"{resolved_registry_url}/{service_key}:{service_tag}"
    }

    return service_spec


def _replace_env_vars_in_compose_spec(
    stringified_service_spec: str, resolved_registry_url: str, service_tag: str
) -> str:
    """
    There are a few special environment variables which get replaced before
    forwarding the spec to the dynamic-sidecar:
    - REGISTRY_URL
    - SERVICE_TAG
    """
    stringified_service_spec = stringified_service_spec.replace(
        "${REGISTRY_URL}", resolved_registry_url
    )
    stringified_service_spec = stringified_service_spec.replace(
        "${SERVICE_TAG}", service_tag
    )
    return stringified_service_spec


async def assemble_spec(
    # pylint: disable=too-many-arguments
    app: FastAPI,
    service_key: str,
    service_tag: str,
    paths_mapping: PathsMappingModel,  # pylint: disable=unused-argument
    compose_spec: ComposeSpecModel,
    target_container: Optional[str],
    dynamic_sidecar_network_name: str,
    simcore_traefik_zone: str,
    service_port: PositiveInt,
) -> str:
    """returns a docker-compose spec which will be use by the dynamic-sidecar to start the service """

    container_name = target_container
    service_spec = compose_spec

    settings: DynamicSidecarSettings = app.state.dynamic_sidecar_settings

    # when no compose yaml file was provided
    if service_spec is None:
        service_spec = _assemble_from_service_key_and_tag(
            resolved_registry_url=settings.resolved_registry_url,
            service_key=service_key,
            service_tag=service_tag,
        )
        container_name = CONTAINER_NAME
    else:
        # TODO: need to be sorted out:
        # - inject paths mapping
        # - remove above # pylint: disable=unused-argument
        pass

    _inject_traefik_configuration(
        service_spec,
        target_container=container_name,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
        simcore_traefik_zone=simcore_traefik_zone,
        service_port=service_port,
    )

    stringified_service_spec = yaml.safe_dump(service_spec)
    stringified_service_spec = _replace_env_vars_in_compose_spec(
        stringified_service_spec=stringified_service_spec,
        resolved_registry_url=settings.resolved_registry_url,
        service_tag=service_tag,
    )

    return stringified_service_spec
