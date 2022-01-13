import json
from copy import deepcopy
from typing import Any, Dict, List, Optional, Union

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


EnvKeyEqValueList = List[str]
EnvVarsMap = Dict[str, Optional[str]]


class _environment_section:
    """the 'environment' field in a docker-compose can be either a dict (EnvVarsMap)
    or a list of "key=value" (EnvKeyEqValueList)

    These helpers can resolve parsing and exporting between these formats

    SEE https://docs.docker.com/compose/compose-file/compose-file-v3/#environment
    """

    @staticmethod
    def parse(environment: Union[EnvVarsMap, EnvKeyEqValueList]) -> EnvVarsMap:
        envs = {}
        if isinstance(environment, list):
            for key_eq_value in environment:
                assert isinstance(key_eq_value, str)  # nosec
                key, value, *_ = key_eq_value.split("=", maxsplit=1) + [
                    None,
                ]  # type: ignore
                envs[key] = value
        else:
            assert isinstance(environment, dict)  # nosec
            envs = deepcopy(environment)
        return envs

    @staticmethod
    def export_as_list(environment: EnvVarsMap) -> EnvKeyEqValueList:
        envs = []
        for key, value in environment.items():
            if value is None:
                envs.append(f"{key}")
            else:
                envs.append(f"{key}={value}")
        return envs


def _inject_paths_mappings(
    service_spec: Dict[str, Any], path_mappings: PathMappingsLabel
) -> None:
    for service_name in service_spec["services"]:
        service_content = service_spec["services"][service_name]

        env_vars: EnvVarsMap = _environment_section.parse(
            service_content.get("environment", {})
        )
        env_vars["DY_SIDECAR_PATH_INPUTS"] = f"{path_mappings.inputs_path}"
        env_vars["DY_SIDECAR_PATH_OUTPUTS"] = f"{path_mappings.outputs_path}"
        env_vars[
            "DY_SIDECAR_STATE_PATHS"
        ] = f"{json.dumps([f'{p}' for p in path_mappings.state_paths])}"

        service_content["environment"] = _environment_section.export_as_list(env_vars)


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

    docker_compose_version = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_DOCKER_COMPOSE_VERSION
    )

    # when no compose yaml file was provided
    if compose_spec is None:
        service_spec: Dict[str, Any] = {
            # NOTE: latest version does NOT require
            "version": docker_compose_version,
            "services": {
                CONTAINER_NAME: {
                    "image": f"{docker_registry_settings.resolved_registry_url}/{service_key}:{service_tag}"
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
