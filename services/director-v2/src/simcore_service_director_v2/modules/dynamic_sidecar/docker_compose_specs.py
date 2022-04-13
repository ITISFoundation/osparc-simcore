import json
import logging
from copy import deepcopy
from typing import Any, Dict, Final, List, Optional, Union

import yaml
from fastapi.applications import FastAPI
from models_library.service_settings_labels import (
    ComposeSpecLabel,
    PathMappingsLabel,
    SimcoreServiceLabels,
    SimcoreServiceSettingLabelEntry,
)
from settings_library.docker_registry import RegistrySettings

from ...modules.director_v0 import DirectorV0Client
from ._constants import CONTAINER_NAME
from .docker_service_specs import MATCH_SERVICE_VERSION, MATCH_SIMCORE_REGISTRY
from .docker_service_specs.settings import get_labels_for_involved_services
from .scheduler.events_utils import get_director_v0_client

EnvKeyEqValueList = List[str]
EnvVarsMap = Dict[str, Optional[str]]

_NANO_UNIT: Final[int] = int(1e9)
_MB: Final[int] = 1_048_576
# defaults to use when these values are not defined or found
# TODO: ANE -> SAN, PC: let's make these are sensible for when a service does not define them
DEFAULT_RESERVATION_NANO_CPUS: Final[int] = int(0.1 * _NANO_UNIT)
DEFAULT_RESERVATION_MEMORY_BYTES: Final[int] = 100 * _MB
DEFAULT_LIMIT_NANO_CPUS: Final[int] = int(0.1 * _NANO_UNIT)
DEFAULT_LIMIT_MEMORY_BYTES: Final[int] = 100 * _MB
assert DEFAULT_RESERVATION_NANO_CPUS <= DEFAULT_LIMIT_NANO_CPUS  # nosec
assert DEFAULT_RESERVATION_MEMORY_BYTES <= DEFAULT_LIMIT_MEMORY_BYTES  # nosec

logger = logging.getLogger(__name__)


def _inject_proxy_network_configuration(
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
    target_container_spec["networks"] = container_networks


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


async def _inject_resource_limits_and_reservations(
    app: FastAPI, service_key: str, service_tag: str, service_spec: ComposeSpecLabel
) -> None:
    director_v0_client: DirectorV0Client = get_director_v0_client(app)
    labels_for_involved_services: Dict[
        str, SimcoreServiceLabels
    ] = await get_labels_for_involved_services(
        director_v0_client=director_v0_client,
        service_key=service_key,
        service_tag=service_tag,
    )

    # example: '2.3' -> 2 ; '3.7' -> 3
    docker_compose_major_version: int = int(service_spec["version"].split(".")[0])

    for spec_service_key, spec in service_spec["services"].items():
        labels = labels_for_involved_services[spec_service_key]

        settings_list: List[SimcoreServiceSettingLabelEntry] = labels.settings

        # defaults
        limit_nano_cpus = DEFAULT_LIMIT_NANO_CPUS
        limit_memory_bytes = DEFAULT_LIMIT_MEMORY_BYTES
        reservation_nano_cpus = DEFAULT_RESERVATION_NANO_CPUS
        reservation_memory_bytes = DEFAULT_RESERVATION_MEMORY_BYTES

        for entry in settings_list:
            if entry.name == "Resources" and entry.setting_type == "Resources":
                values: Dict[str, Any] = entry.value

                # fetch limits
                limits: Dict[str, Any] = values.get("Limits", {})
                limit_nano_cpus = limits.get("NanoCPUs", DEFAULT_LIMIT_NANO_CPUS)
                limit_memory_bytes = limits.get(
                    "MemoryBytes", DEFAULT_LIMIT_MEMORY_BYTES
                )

                # fetch reservations
                reservations: Dict[str, Any] = values.get("Reservations", {})
                reservation_nano_cpus = reservations.get(
                    "NanoCPUs", DEFAULT_RESERVATION_NANO_CPUS
                )

                reservation_memory_bytes = reservations.get(
                    "MemoryBytes", DEFAULT_RESERVATION_MEMORY_BYTES
                )

                break

        # ensure reservations <= limits setting up limits as the max between both
        limit_nano_cpus = max(limit_nano_cpus, reservation_nano_cpus)
        limit_memory_bytes = max(limit_memory_bytes, reservation_memory_bytes)

        if docker_compose_major_version >= 3:
            # compos spec version 3 and beyond
            deploy = spec.get("deploy", {})
            resources = deploy.get("resources", {})
            limits = resources.get("limits", {})
            reservations = resources.get("reservations", {})

            # assign limits
            limits["cpus"] = limit_nano_cpus / _NANO_UNIT
            limits["memory"] = f"{limit_memory_bytes}b"
            # assing reservations
            reservations["cpus"] = reservation_nano_cpus / _NANO_UNIT
            reservations["memory"] = f"{reservation_memory_bytes}b"

            resources["reservations"] = reservations
            resources["limits"] = limits
            deploy["resources"] = resources
            spec["deploy"] = deploy
        else:
            # compos spec version 2
            spec["mem_limit"] = limit_memory_bytes
            spec["mem_reservation"] = reservation_memory_bytes
            # NOTE: there is no distinction between limit and reservation, taking the higher value
            spec["cpus"] = max(limit_nano_cpus, reservation_nano_cpus) / _NANO_UNIT


async def assemble_spec(
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

    _inject_proxy_network_configuration(
        service_spec=service_spec,
        target_container=container_name,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
    )

    _inject_paths_mappings(service_spec, paths_mapping)

    await _inject_resource_limits_and_reservations(
        app=app,
        service_key=service_key,
        service_tag=service_tag,
        service_spec=service_spec,
    )

    stringified_service_spec = yaml.safe_dump(service_spec)
    stringified_service_spec = _replace_env_vars_in_compose_spec(
        stringified_service_spec=stringified_service_spec,
        resolved_registry_url=docker_registry_settings.resolved_registry_url,
        service_tag=service_tag,
    )

    return stringified_service_spec
