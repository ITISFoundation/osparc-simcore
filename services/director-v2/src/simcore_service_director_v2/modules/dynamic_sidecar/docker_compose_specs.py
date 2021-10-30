import json
from typing import Any, Dict, List, Optional

import yaml
from fastapi.applications import FastAPI
from models_library.service_settings_labels import ComposeSpecLabel, PathMappingsLabel
from settings_library.docker_registry import RegistrySettings

from .docker_service_specs import MATCH_SERVICE_VERSION, MATCH_SIMCORE_REGISTRY

CONTAINER_NAME = "container"


def _inject_proxy_network_configuration(
    service_spec: Dict[str, Any],
    target_container: str,
    dynamic_sidecar_network_name: str,
) -> None:
    """
    Injects network configuration to allow the service
    to be accessible on `uuid.services.SERVICE_DNS`
    """

    # add external network to existing networks defined in the container
    service_spec["networks"] = {
        dynamic_sidecar_network_name: {
            "external": {"name": dynamic_sidecar_network_name},
            "driver": "overlay",
        }
    }

    # attach overlay network to container
    target_container_spec = service_spec["services"][target_container]
    container_networks = target_container_spec.get("networks", [])
    container_networks.append(dynamic_sidecar_network_name)
    target_container_spec["networks"] = container_networks


def _inject_paths_mappings(
    service_spec: Dict[str, Any], path_mappings: PathMappingsLabel
) -> None:
    """Updates services.${service_name}.environment list in a compose specs"""
    for service_name in service_spec["services"]:
        service_content = service_spec["services"][service_name]

        # FIXME: is it guaranteed that these env vars are not already defined?
        # which overrides which? Suggest to: load as dict[str, str],
        # set new env and dump back
        environment_vars: List[str] = service_content.get("environment", [])
        environment_vars.append(f"DY_SIDECAR_PATH_INPUTS={path_mappings.inputs_path}")
        environment_vars.append(f"DY_SIDECAR_PATH_OUTPUTS={path_mappings.outputs_path}")
        environment_vars.append(
            f"DY_SIDECAR_STATE_PATHS={json.dumps([str(x) for x in path_mappings.state_paths])}"
        )
        service_content["environment"] = environment_vars


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


def assemble_spec(
    app: FastAPI,
    service_key: str,
    service_tag: str,
    paths_mapping: PathMappingsLabel,
    compose_spec: Optional[ComposeSpecLabel],
    container_http_entry: Optional[str],
    dynamic_sidecar_network_name: str,
) -> str:
    """
    returns a docker-compose spec used by
    the dynamic-sidecar to start the service
    """

    docker_registry_settings: RegistrySettings = (
        app.state.settings.DIRECTOR_V2_DOCKER_REGISTRY
    )

    # when no compose yaml file was provided
    if compose_spec is None:
        service_spec: Dict[str, Any] = {
            "version": "3.8",
            "services": {
                CONTAINER_NAME: {
                    "image": f"{settings.REGISTRY.resolved_registry_url}/{service_key}:{service_tag}"
                }
            },
        }
        container_name = CONTAINER_NAME
    else:
        service_spec = compose_spec
        container_name = container_http_entry

    assert service_spec is not None  # nosec
    assert container_name is not None  # nosec

    _inject_proxy_network_configuration(
        service_spec,
        target_container=container_name,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
    )

    _inject_paths_mappings(service_spec, paths_mapping)

    stringified_service_spec = yaml.safe_dump(service_spec)
    stringified_service_spec = _replace_env_vars_in_compose_spec(
        stringified_service_spec=stringified_service_spec,
        resolved_registry_url=docker_registry_settings.resolved_registry_url,
        service_tag=service_tag,
    )

    return stringified_service_spec
