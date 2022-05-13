import json
import logging
from copy import deepcopy
from typing import Dict, List, Optional, Union

from fastapi.applications import FastAPI
from models_library.service_settings_labels import ComposeSpecLabel, PathMappingsLabel
from models_library.services_resources import Resources, ResourceValue, ServiceResources
from servicelib.docker_compose import replace_env_vars_in_compose_spec
from settings_library.docker_registry import RegistrySettings

from ._constants import CONTAINER_NAME

EnvKeyEqValueList = List[str]
EnvVarsMap = Dict[str, Optional[str]]


logger = logging.getLogger(__name__)


def _update_proxy_network_configuration(
    service_spec: ComposeSpecLabel,
    target_container: str,
    dynamic_sidecar_network_name: str,
) -> None:
    """
    Injects network configuration to allow the service
    to be accessible on `uuid.services.SERVICE_DNS`
    """

    # add external network to existing networks defined in the container
    networks = service_spec.get("networks", {})
    networks[dynamic_sidecar_network_name] = {
        "external": {"name": dynamic_sidecar_network_name},
        "driver": "overlay",
    }
    service_spec["networks"] = networks

    # attach overlay network to container
    target_container_spec = service_spec["services"][target_container]
    container_networks = target_container_spec.get("networks", [])
    container_networks.append(dynamic_sidecar_network_name)
    # avoid duplicate entries, this is important when the dynamic-sidecar
    # fails to run docker-compose up, otherwise it will
    # continue adding lots of entries to this list
    target_container_spec["networks"] = list(set(container_networks))


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


def _update_paths_mappings(
    service_spec: ComposeSpecLabel, path_mappings: PathMappingsLabel
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


def _update_resource_limits_and_reservations(
    service_resources: ServiceResources, service_spec: ComposeSpecLabel
) -> None:
    # example: '2.3' -> 2 ; '3.7' -> 3
    docker_compose_major_version: int = int(service_spec["version"].split(".")[0])

    for spec_service_key, spec in service_spec["services"].items():
        resources: Resources = service_resources[spec_service_key].resources
        logger.debug("Resources for %s: %s", spec_service_key, f"{resources=}")

        cpu: ResourceValue = resources["CPU"]
        memory: ResourceValue = resources["RAM"]

        if docker_compose_major_version >= 3:
            # compos spec version 3 and beyond
            deploy = spec.get("deploy", {})
            resources = deploy.get("resources", {})
            limits = resources.get("limits", {})
            reservations = resources.get("reservations", {})

            # assign limits
            limits["cpus"] = float(cpu.limit)
            limits["memory"] = f"{memory.limit}"
            # assing reservations
            reservations["cpus"] = float(cpu.reservation)
            reservations["memory"] = f"{memory.reservation}"

            resources["reservations"] = reservations
            resources["limits"] = limits
            deploy["resources"] = resources
            spec["deploy"] = deploy
        else:
            # compos spec version 2
            spec["mem_limit"] = f"{memory.limit}"
            spec["mem_reservation"] = f"{memory.reservation}"
            # NOTE: there is no distinction between limit and reservation, taking the higher value
            spec["cpus"] = float(max(cpu.limit, cpu.reservation))


def assemble_spec(
    app: FastAPI,
    service_key: str,
    service_tag: str,
    paths_mapping: PathMappingsLabel,
    compose_spec: Optional[ComposeSpecLabel],
    container_http_entry: Optional[str],
    dynamic_sidecar_network_name: str,
    service_resources: ServiceResources,
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
        service_spec: ComposeSpecLabel = {
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

    _update_proxy_network_configuration(
        service_spec=service_spec,
        target_container=container_name,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
    )

    _update_paths_mappings(service_spec, paths_mapping)

    _update_resource_limits_and_reservations(
        service_resources=service_resources, service_spec=service_spec
    )

    stringified_service_spec = replace_env_vars_in_compose_spec(
        service_spec=service_spec,
        replace_simcore_registry=docker_registry_settings.resolved_registry_url,
        replace_service_version=service_tag,
    )

    return stringified_service_spec
