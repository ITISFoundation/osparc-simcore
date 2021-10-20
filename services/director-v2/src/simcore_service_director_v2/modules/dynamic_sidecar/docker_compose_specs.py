from copy import deepcopy
from typing import Any, Dict, Optional

import yaml
from fastapi.applications import FastAPI
from models_library.service_settings_labels import ComposeSpecLabel

from ...core.settings import DynamicSidecarSettings
from .docker_service_specs import MATCH_SERVICE_VERSION, MATCH_SIMCORE_REGISTRY

CONTAINER_NAME = "container"
BASE_SERVICE_SPEC: Dict[str, Any] = {
    "version": "3.8",
    "services": {CONTAINER_NAME: {}},
}


def _inject_proxy_configuration(
    service_spec: Dict[str, Any],
    target_container: str,
    dynamic_sidecar_network_name: str,
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
    stringified_service_spec = stringified_service_spec.replace(
        MATCH_SIMCORE_REGISTRY, resolved_registry_url
    )
    stringified_service_spec = stringified_service_spec.replace(
        MATCH_SERVICE_VERSION, service_tag
    )
    return stringified_service_spec


async def assemble_spec(
    app: FastAPI,
    service_key: str,
    service_tag: str,
    compose_spec: ComposeSpecLabel,
    container_http_entry: Optional[str],
    dynamic_sidecar_network_name: str,
) -> str:
    """
    returns a docker-compose spec used by
    the dynamic-sidecar to start the service
    """
    settings: DynamicSidecarSettings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR
    )

    container_name = container_http_entry
    service_spec = compose_spec

    # when no compose yaml file was provided
    if service_spec is None:
        service_spec = _assemble_from_service_key_and_tag(
            resolved_registry_url=settings.REGISTRY.resolved_registry_url,
            service_key=service_key,
            service_tag=service_tag,
        )
        container_name = CONTAINER_NAME

    assert container_name is not None  # nosec

    _inject_proxy_configuration(
        service_spec,
        target_container=container_name,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
    )

    stringified_service_spec = yaml.safe_dump(service_spec)
    stringified_service_spec = _replace_env_vars_in_compose_spec(
        stringified_service_spec=stringified_service_spec,
        resolved_registry_url=settings.REGISTRY.resolved_registry_url,
        service_tag=service_tag,
    )

    return stringified_service_spec
