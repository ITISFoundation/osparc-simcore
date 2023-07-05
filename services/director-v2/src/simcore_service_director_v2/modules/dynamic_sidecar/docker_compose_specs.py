import logging
from copy import deepcopy
from typing import Any, Optional, TypedDict

from fastapi.applications import FastAPI
from models_library.docker import DockerGenericTag, SimcoreServiceDockerLabelKeys
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import (
    ComposeSpecLabelDict,
    PathMappingsLabel,
    SimcoreServiceLabels,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    ResourcesDict,
    ResourceValue,
    ServiceResourcesDict,
)
from models_library.users import UserID
from models_library.utils.docker_compose import replace_env_vars_in_compose_spec
from pydantic import ByteSize
from servicelib.json_serialization import json_dumps
from servicelib.resources import CPU_RESOURCE_LIMIT_KEY, MEM_RESOURCE_LIMIT_KEY
from settings_library.docker_registry import RegistrySettings

from .docker_compose_egress_config import add_egress_configuration

EnvKeyEqValueList = list[str]
EnvVarsMap = dict[str, Optional[str]]


logger = logging.getLogger(__name__)


def _update_networking_configuration(
    service_spec: ComposeSpecLabelDict,
    target_http_entrypoint_container: str,
    dynamic_sidecar_network_name: str,
    swarm_network_name: str,
) -> None:
    """
    1. Adds network configuration to allow the service
    to be accessible on `uuid.services.SERVICE_DNS`
    2. Adds networking configuration allowing egress
    proxies to access the internet.
    """

    networks = service_spec.get("networks", {})
    # used by the proxy to contact the service http entrypoint
    networks[dynamic_sidecar_network_name] = {
        "external": {"name": dynamic_sidecar_network_name},
        "driver": "overlay",
    }
    # used by egress proxies to gain access to the internet
    networks[swarm_network_name] = {
        "external": {"name": swarm_network_name},
        "driver": "overlay",
    }
    service_spec["networks"] = networks

    # attach proxy network to target http entrypoint container
    target_container_spec = service_spec["services"][target_http_entrypoint_container]
    container_networks = target_container_spec.get("networks", {})
    container_networks[dynamic_sidecar_network_name] = None
    target_container_spec["networks"] = container_networks


class _environment_section:
    """the 'environment' field in a docker-compose can be either a dict (EnvVarsMap)
    or a list of "key=value" (EnvKeyEqValueList)

    These helpers can resolve parsing and exporting between these formats

    SEE https://docs.docker.com/compose/compose-file/compose-file-v3/#environment
    """

    @staticmethod
    def parse(environment: EnvVarsMap | EnvKeyEqValueList) -> EnvVarsMap:
        envs = {}
        if isinstance(environment, list):
            for key_eq_value in environment:
                assert isinstance(key_eq_value, str)  # nosec
                key, value, *_ = key_eq_value.split("=", maxsplit=1) + [None]
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
    service_spec: ComposeSpecLabelDict, path_mappings: PathMappingsLabel
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
        ] = f"{json_dumps( { f'{p}' for p in path_mappings.state_paths } )}"

        service_content["environment"] = _environment_section.export_as_list(env_vars)


class _AssignedLimits(TypedDict):
    cpu: float
    memory: int


def _update_resource_limits_and_reservations(
    service_resources: ServiceResourcesDict, service_spec: ComposeSpecLabelDict
) -> dict[DockerGenericTag, _AssignedLimits]:
    # example: '2.3' -> 2 ; '3.7' -> 3
    assigned_limits = {}
    docker_compose_major_version: int = int(service_spec["version"].split(".")[0])
    for spec_service_key, spec in service_spec["services"].items():
        if spec_service_key not in service_resources:
            continue

        resources: ResourcesDict = service_resources[spec_service_key].resources
        logger.debug("Resources for %s: %s", spec_service_key, f"{resources=}")

        cpu: ResourceValue = resources["CPU"]
        memory: ResourceValue = resources["RAM"]

        nano_cpu_limits: float = 0.0
        mem_limits: str = "0"
        _NANO = 10**9  #  cpu's in nano-cpu's

        if docker_compose_major_version >= 3:
            # compos spec version 3 and beyond
            deploy: dict[str, Any] = spec.get("deploy", {})
            resources_v3: dict[str, Any] = deploy.get("resources", {})
            limits: dict[str, Any] = resources_v3.get("limits", {})
            reservations: dict[str, Any] = resources_v3.get("reservations", {})

            # assign limits
            limits["cpus"] = float(cpu.limit)
            limits["memory"] = f"{memory.limit}"
            # assing reservations
            reservations["cpus"] = float(cpu.reservation)
            reservations["memory"] = f"{memory.reservation}"

            resources_v3["reservations"] = reservations
            resources_v3["limits"] = limits
            deploy["resources"] = resources_v3
            spec["deploy"] = deploy

            nano_cpu_limits = limits["cpus"]
            mem_limits = limits["memory"]
        else:
            # compos spec version 2
            spec["mem_limit"] = f"{memory.limit}"
            spec["mem_reservation"] = f"{memory.reservation}"
            # NOTE: there is no distinction between limit and reservation, taking the higher value
            spec["cpus"] = float(max(cpu.limit, cpu.reservation))

            nano_cpu_limits = spec["cpus"]
            mem_limits = spec["mem_limit"]

        # Update env vars for services that need to know the current resources specs
        environment = spec.get("environment", [])

        # remove any already existing env var
        environment = [
            e
            for e in environment
            if all(i not in e for i in [CPU_RESOURCE_LIMIT_KEY, MEM_RESOURCE_LIMIT_KEY])
        ]

        resource_limits = [
            f"{CPU_RESOURCE_LIMIT_KEY}={int(nano_cpu_limits*_NANO)}",
            f"{MEM_RESOURCE_LIMIT_KEY}={mem_limits}",
        ]

        environment.extend(resource_limits)
        spec["environment"] = environment

        assigned_limits[spec_service_key] = _AssignedLimits(
            cpu=nano_cpu_limits, memory=int(memory.limit)
        )
    return assigned_limits


def _strip_service_quotas(service_spec: ComposeSpecLabelDict):
    """
    When disk quotas are not supported by the node, it is required to remove
    any reference from the docker-compose spec.
    """
    for spec in service_spec["services"].values():
        spec.pop("storage_opt", None)


def _update_container_labels(
    service_spec: ComposeSpecLabelDict,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    simcore_user_agent: str,
    product_name: ProductName,
    swarm_stack_name: str,
    assigned_limits: dict[DockerGenericTag, _AssignedLimits],
) -> None:
    default_limits = _AssignedLimits(memory=0, cpu=0)
    for spec_service_key, spec in service_spec["services"].items():
        labels: list[str] = spec.setdefault("labels", [])
        container_limits: _AssignedLimits = assigned_limits.get(
            spec_service_key, default_limits
        )

        label_keys = SimcoreServiceDockerLabelKeys.construct(
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            simcore_user_agent=simcore_user_agent,
            product_name=product_name,
            swarm_stack_name=swarm_stack_name,
            memory_limit=ByteSize(container_limits["memory"]),
            cpu_limit=container_limits["cpu"],
        )
        docker_labels = [
            f"{k}={v}" for k, v in label_keys.to_simcore_runtime_docker_labels().items()
        ]

        for docker_label in docker_labels:
            if docker_label not in labels:
                labels.append(docker_label)


def assemble_spec(
    *,
    app: FastAPI,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    paths_mapping: PathMappingsLabel,
    compose_spec: ComposeSpecLabelDict | None,
    container_http_entry: str | None,
    dynamic_sidecar_network_name: str,
    swarm_network_name: str,
    service_resources: ServiceResourcesDict,
    has_quota_support: bool,
    simcore_service_labels: SimcoreServiceLabels,
    allow_internet_access: bool,
    product_name: ProductName,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    simcore_user_agent: str,
    swarm_stack_name: str,
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

    egress_proxy_settings = (
        app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_EGRESS_PROXY_SETTINGS
    )

    # when no compose yaml file was provided
    if compose_spec is None:
        service_spec: ComposeSpecLabelDict = {
            "version": docker_compose_version,
            "services": {
                DEFAULT_SINGLE_SERVICE_NAME: {
                    "image": f"{docker_registry_settings.resolved_registry_url}/{service_key}:{service_version}"
                }
            },
        }
        container_name = DEFAULT_SINGLE_SERVICE_NAME
    else:
        service_spec = deepcopy(compose_spec)
        container_name = container_http_entry

    assert service_spec is not None  # nosec
    assert container_name is not None  # nosec

    _update_networking_configuration(
        service_spec=service_spec,
        target_http_entrypoint_container=container_name,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
        swarm_network_name=swarm_network_name,
    )

    _update_paths_mappings(service_spec, paths_mapping)

    assigned_limits = _update_resource_limits_and_reservations(
        service_resources=service_resources, service_spec=service_spec
    )

    if not has_quota_support:
        _strip_service_quotas(service_spec)

    if not allow_internet_access:
        # NOTE: when service has no access to the internet,
        # there could be some components that still require access
        add_egress_configuration(
            service_spec=service_spec,
            simcore_service_labels=simcore_service_labels,
            egress_proxy_settings=egress_proxy_settings,
        )

    _update_container_labels(
        service_spec=service_spec,
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        product_name=product_name,
        simcore_user_agent=simcore_user_agent,
        swarm_stack_name=swarm_stack_name,
        assigned_limits=assigned_limits,
    )

    stringified_service_spec: str = replace_env_vars_in_compose_spec(
        service_spec=service_spec,
        replace_simcore_registry=docker_registry_settings.resolved_registry_url,
        replace_service_version=service_version,
    )

    return stringified_service_spec
