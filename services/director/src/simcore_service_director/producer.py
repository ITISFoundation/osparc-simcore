import asyncio
import contextlib
import json
import logging
import re
from datetime import timedelta
from enum import Enum
from pprint import pformat
from typing import Any, Final, cast

import aiodocker
import aiodocker.networks
import arrow
import httpx
import tenacity
from fastapi import FastAPI, status
from packaging.version import Version
from servicelib.async_utils import run_sequentially_in_context
from servicelib.docker_utils import to_datetime
from settings_library.docker_registry import RegistrySettings
from tenacity import retry, wait_random_exponential
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt

from . import docker_utils, registry_proxy
from .client_session import get_client_session
from .constants import (
    CPU_RESOURCE_LIMIT_KEY,
    MEM_RESOURCE_LIMIT_KEY,
    SERVICE_REVERSE_PROXY_SETTINGS,
    SERVICE_RUNTIME_BOOTSETTINGS,
    SERVICE_RUNTIME_SETTINGS,
)
from .core.errors import (
    DirectorRuntimeError,
    GenericDockerError,
    ServiceNotAvailableError,
    ServiceStartTimeoutError,
    ServiceStateSaveError,
    ServiceUUIDInUseError,
    ServiceUUIDNotFoundError,
)
from .core.settings import ApplicationSettings, get_application_settings
from .instrumentation import get_instrumentation
from .services_common import ServicesCommonSettings

_logger = logging.getLogger(__name__)


class ServiceState(Enum):
    PENDING = "pending"
    PULLING = "pulling"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


async def _create_auth(registry_settings: RegistrySettings) -> dict[str, str]:
    return {
        "username": registry_settings.REGISTRY_USER,
        "password": registry_settings.REGISTRY_PW.get_secret_value(),
    }


async def _check_node_uuid_available(
    client: aiodocker.docker.Docker, node_uuid: str
) -> None:
    _logger.debug("Checked if UUID %s is already in use", node_uuid)
    # check if service with same uuid already exists
    try:
        # not filtering by "swarm_stack_name" label because it's safer
        list_of_running_services_w_uuid = await client.services.list(
            filters={
                "label": f"{_to_simcore_runtime_docker_label_key('node_id')}={node_uuid}"
            }
        )
    except aiodocker.DockerError as err:
        msg = "Error while retrieving services"
        raise GenericDockerError(err=msg) from err
    if list_of_running_services_w_uuid:
        raise ServiceUUIDInUseError(service_uuid=node_uuid)
    _logger.debug("UUID %s is free", node_uuid)


def _check_setting_correctness(setting: dict) -> None:
    if "name" not in setting or "type" not in setting or "value" not in setting:
        msg = f"Invalid setting in {setting}"
        raise DirectorRuntimeError(msg=msg)


def _parse_mount_settings(settings: list[dict]) -> list[dict]:
    mounts = []
    for s in settings:
        _logger.debug("Retrieved mount settings %s", s)
        mount = {}
        mount["ReadOnly"] = True
        if "ReadOnly" in s and s["ReadOnly"] in ["false", "False", False]:
            mount["ReadOnly"] = False

        for field in ["Source", "Target", "Type"]:
            if field in s:
                mount[field] = s[field]
            else:
                _logger.warning(
                    "Mount settings have wrong format. Required keys [Source, Target, Type]"
                )
                continue

        _logger.debug("Append mount settings %s", mount)
        mounts.append(mount)

    return mounts


_ENV_NUM_ELEMENTS: Final[int] = 2


def _parse_env_settings(settings: list[str]) -> dict:
    envs = {}
    for s in settings:
        _logger.debug("Retrieved env settings %s", s)
        if "=" in s:
            parts = s.split("=")
            if len(parts) == _ENV_NUM_ELEMENTS:
                envs.update({parts[0]: parts[1]})

        _logger.debug("Parsed env settings %s", s)

    return envs


async def _read_service_settings(
    app: FastAPI, key: str, tag: str, settings_name: str
) -> dict[str, Any] | list[Any] | None:
    image_labels, _ = await registry_proxy.get_image_labels(app, key, tag)
    settings: dict[str, Any] | list[Any] | None = (
        json.loads(image_labels[settings_name])
        if settings_name in image_labels
        else None
    )

    _logger.debug("Retrieved %s settings: %s", settings_name, pformat(settings))
    return settings


_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX: str = "io.simcore.runtime."


def _to_simcore_runtime_docker_label_key(key: str) -> str:
    return f"{_SIMCORE_RUNTIME_DOCKER_LABEL_PREFIX}{key.replace('_', '-').lower()}"


# pylint: disable=too-many-branches
async def _create_docker_service_params(
    app: FastAPI,
    *,
    client: aiodocker.docker.Docker,
    service_key: str,
    service_tag: str,
    main_service: bool,
    user_id: str,
    node_uuid: str,
    project_id: str,
    node_base_path: str,
    internal_network_id: str | None,
    request_simcore_user_agent: str,
) -> dict:
    # pylint: disable=too-many-statements
    app_settings = get_application_settings(app)

    service_parameters_labels = await _read_service_settings(
        app, service_key, service_tag, SERVICE_RUNTIME_SETTINGS
    )
    reverse_proxy_settings = await _read_service_settings(
        app, service_key, service_tag, SERVICE_REVERSE_PROXY_SETTINGS
    )
    service_name = registry_proxy.get_service_last_names(service_key) + "_" + node_uuid
    _logger.debug("Converting labels to docker runtime parameters")
    service_default_envs = {
        # old services expect POSTGRES_ENDPOINT as hostname:port
        "POSTGRES_ENDPOINT": f"{app_settings.DIRECTOR_POSTGRES.POSTGRES_HOST}:{app_settings.DIRECTOR_POSTGRES.POSTGRES_PORT}",
        "POSTGRES_USER": app_settings.DIRECTOR_POSTGRES.POSTGRES_USER,
        "POSTGRES_PASSWORD": app_settings.DIRECTOR_POSTGRES.POSTGRES_PASSWORD.get_secret_value(),
        "POSTGRES_DB": app_settings.DIRECTOR_POSTGRES.POSTGRES_DB,
        "STORAGE_ENDPOINT": app_settings.STORAGE_ENDPOINT,
    }
    container_spec: dict[str, Any] = {
        "Image": f"{app_settings.DIRECTOR_REGISTRY.resolved_registry_url}/{service_key}:{service_tag}",
        "Env": {
            **service_default_envs,
            "SIMCORE_USER_ID": user_id,
            "SIMCORE_NODE_UUID": node_uuid,
            "SIMCORE_PROJECT_ID": project_id,
            "SIMCORE_NODE_BASEPATH": node_base_path or "",
            "SIMCORE_HOST_NAME": service_name,
        },
        "Init": True,
        "Labels": {
            _to_simcore_runtime_docker_label_key("user_id"): user_id,
            _to_simcore_runtime_docker_label_key("project_id"): project_id,
            _to_simcore_runtime_docker_label_key("node_id"): node_uuid,
            _to_simcore_runtime_docker_label_key(
                "swarm_stack_name"
            ): app_settings.DIRECTOR_SWARM_STACK_NAME,
            _to_simcore_runtime_docker_label_key(
                "simcore_user_agent"
            ): request_simcore_user_agent,
            _to_simcore_runtime_docker_label_key(
                "product_name"
            ): "osparc",  # fixed no legacy available in other products
            _to_simcore_runtime_docker_label_key("cpu_limit"): "0",
            _to_simcore_runtime_docker_label_key("memory_limit"): "0",
        },
        "Mounts": [],
    }

    # SEE https://docs.docker.com/engine/api/v1.41/#operation/ServiceCreate
    docker_params: dict[str, Any] = {
        "auth": (
            await _create_auth(app_settings.DIRECTOR_REGISTRY)
            if app_settings.DIRECTOR_REGISTRY.REGISTRY_AUTH
            else {}
        ),
        "registry": (
            app_settings.DIRECTOR_REGISTRY.resolved_registry_url
            if app_settings.DIRECTOR_REGISTRY.REGISTRY_AUTH
            else ""
        ),
        "name": service_name,
        "task_template": {
            "ContainerSpec": container_spec,
            "Placement": {
                "Constraints": (
                    ["node.role==worker"]
                    if await docker_utils.swarm_has_worker_nodes()
                    else []
                )
            },
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": app_settings.DIRECTOR_SERVICES_RESTART_POLICY_DELAY_S
                * pow(10, 6),
                "MaxAttempts": app_settings.DIRECTOR_SERVICES_RESTART_POLICY_MAX_ATTEMPTS,
            },
            "Resources": {
                "Limits": {
                    "NanoCPUs": app_settings.DIRECTOR_DEFAULT_MAX_NANO_CPUS,
                    "MemoryBytes": app_settings.DIRECTOR_DEFAULT_MAX_MEMORY,
                },
                "Reservations": {
                    "NanoCPUs": app_settings.DIRECTOR_DEFAULT_MAX_NANO_CPUS,
                    "MemoryBytes": app_settings.DIRECTOR_DEFAULT_MAX_MEMORY,
                },
            },
        },
        "endpoint_spec": {"Mode": "dnsrr"},
        "labels": {
            _to_simcore_runtime_docker_label_key("user_id"): user_id,
            _to_simcore_runtime_docker_label_key("project_id"): project_id,
            _to_simcore_runtime_docker_label_key("node_id"): node_uuid,
            _to_simcore_runtime_docker_label_key(
                "swarm_stack_name"
            ): app_settings.DIRECTOR_SWARM_STACK_NAME,
            _to_simcore_runtime_docker_label_key(
                "simcore_user_agent"
            ): request_simcore_user_agent,
            _to_simcore_runtime_docker_label_key(
                "product_name"
            ): "osparc",  # fixed no legacy available in other products
            _to_simcore_runtime_docker_label_key("cpu_limit"): "0",
            _to_simcore_runtime_docker_label_key("memory_limit"): "0",
            _to_simcore_runtime_docker_label_key("type"): (
                "main" if main_service else "dependency"
            ),
            "io.simcore.zone": f"{app_settings.DIRECTOR_TRAEFIK_SIMCORE_ZONE}",
            "traefik.enable": "true" if main_service else "false",
            f"traefik.http.services.{service_name}.loadbalancer.server.port": "8080",
            f"traefik.http.routers.{service_name}.rule": f"PathPrefix(`/x/{node_uuid}`)",
            f"traefik.http.routers.{service_name}.entrypoints": "http",
            f"traefik.http.routers.{service_name}.priority": "10",
            f"traefik.http.routers.{service_name}.middlewares": f"{app_settings.DIRECTOR_SWARM_STACK_NAME}_gzip@swarm",
        },
        "networks": [internal_network_id] if internal_network_id else [],
    }
    if app_settings.DIRECTOR_SERVICES_CUSTOM_CONSTRAINTS:
        _logger.debug(
            "adding custom constraints %s ",
            app_settings.DIRECTOR_SERVICES_CUSTOM_CONSTRAINTS,
        )
        docker_params["task_template"]["Placement"]["Constraints"] += [
            app_settings.DIRECTOR_SERVICES_CUSTOM_CONSTRAINTS
        ]

    # some services define strip_path:true if they need the path to be stripped away
    if (
        isinstance(reverse_proxy_settings, dict)
        and reverse_proxy_settings
        and reverse_proxy_settings.get("strip_path")
    ):
        docker_params["labels"][
            f"traefik.http.middlewares.{service_name}_stripprefixregex.stripprefixregex.regex"
        ] = f"^/x/{node_uuid}"
        docker_params["labels"][
            f"traefik.http.routers.{service_name}.middlewares"
        ] += f", {service_name}_stripprefixregex"

    placement_constraints_to_substitute: list[str] = []
    placement_substitutions: dict[
        str, str
    ] = app_settings.DIRECTOR_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS
    assert isinstance(service_parameters_labels, list)  # nosec
    for param in service_parameters_labels:
        _check_setting_correctness(param)
        # replace %service_uuid% by the given uuid
        if str(param["value"]).find("%service_uuid%") != -1:
            dummy_string = json.dumps(param["value"])
            dummy_string = dummy_string.replace("%service_uuid%", node_uuid)
            param["value"] = json.loads(dummy_string)

        if param["type"] == "Resources":
            # python-API compatible for backward compatibility
            if "mem_limit" in param["value"]:
                docker_params["task_template"]["Resources"]["Limits"][
                    "MemoryBytes"
                ] = param["value"]["mem_limit"]
            if "cpu_limit" in param["value"]:
                docker_params["task_template"]["Resources"]["Limits"][
                    "NanoCPUs"
                ] = param["value"]["cpu_limit"]
            if "mem_reservation" in param["value"]:
                docker_params["task_template"]["Resources"]["Reservations"][
                    "MemoryBytes"
                ] = param["value"]["mem_reservation"]
            if "cpu_reservation" in param["value"]:
                docker_params["task_template"]["Resources"]["Reservations"][
                    "NanoCPUs"
                ] = param["value"]["cpu_reservation"]
            # REST-API compatible
            if (
                placement_substitutions
                and "Reservations" in param["value"]
                and "GenericResources" in param["value"]["Reservations"]
            ):
                # Use placement constraints in place of generic resources, for details
                # see https://github.com/ITISFoundation/osparc-simcore/issues/5250
                # removing them form here
                generic_resources: list = param["value"]["Reservations"][
                    "GenericResources"
                ]

                to_remove: set[str] = set()
                for generic_resource in generic_resources:
                    kind = generic_resource["DiscreteResourceSpec"]["Kind"]
                    if kind in placement_substitutions:
                        placement_constraints_to_substitute.append(kind)
                        to_remove.add(kind)

                # only include generic resources which must not be substituted
                param["value"]["Reservations"]["GenericResources"] = [
                    x
                    for x in generic_resources
                    if x["DiscreteResourceSpec"]["Kind"] not in to_remove
                ]

            if "Limits" in param["value"] or "Reservations" in param["value"]:
                docker_params["task_template"]["Resources"].update(param["value"])

            # ensure strictness of reservations/limits (e.g. reservations = limits)
            for resource_key in ["NanoCPUs", "MemoryBytes"]:
                resources = docker_params["task_template"]["Resources"]
                max_value = max(
                    resources["Reservations"][resource_key],
                    resources["Limits"][resource_key],
                )
                resources["Reservations"][resource_key] = resources["Limits"][
                    resource_key
                ] = max_value

        # publishing port on the ingress network.
        elif param["name"] == "ports" and param["type"] == "int":  # backward comp
            docker_params["labels"][
                _to_simcore_runtime_docker_label_key("port")
            ] = docker_params["labels"][
                f"traefik.http.services.{service_name}.loadbalancer.server.port"
            ] = str(
                param["value"]
            )
        # REST-API compatible
        elif param["type"] == "EndpointSpec":
            if "Ports" in param["value"] and (
                isinstance(param["value"]["Ports"], list)
                and "TargetPort" in param["value"]["Ports"][0]
            ):
                docker_params["labels"][
                    _to_simcore_runtime_docker_label_key("port")
                ] = docker_params["labels"][
                    f"traefik.http.services.{service_name}.loadbalancer.server.port"
                ] = str(
                    param["value"]["Ports"][0]["TargetPort"]
                )

        # placement constraints
        elif (
            param["name"] == "constraints" or param["type"] == "Constraints"
        ):  # python-API compatible
            docker_params["task_template"]["Placement"]["Constraints"] += param["value"]
        elif param["name"] == "env":
            _logger.debug("Found env parameter %s", param["value"])
            env_settings = _parse_env_settings(param["value"])
            if env_settings:
                docker_params["task_template"]["ContainerSpec"]["Env"].update(
                    env_settings
                )
        elif param["name"] == "mount":
            _logger.debug("Found mount parameter %s", param["value"])
            mount_settings: list[dict] = _parse_mount_settings(param["value"])
            if mount_settings:
                docker_params["task_template"]["ContainerSpec"]["Mounts"].extend(
                    mount_settings
                )

    # add placement constraints based on what was found
    for generic_resource_kind in placement_constraints_to_substitute:
        docker_params["task_template"]["Placement"]["Constraints"] += [
            placement_substitutions[generic_resource_kind]
        ]

    # attach the service to the swarm network dedicated to services
    swarm_network = await _get_swarm_network(client, app_settings=app_settings)
    swarm_network_id = swarm_network["Id"]
    swarm_network_name = swarm_network["Name"]
    docker_params["networks"].append(swarm_network_id)
    docker_params["labels"]["traefik.docker.network"] = swarm_network_name

    # set labels for CPU and Memory limits
    nano_cpus_limit = str(
        docker_params["task_template"]["Resources"]["Limits"]["NanoCPUs"]
    )
    mem_limit = str(
        docker_params["task_template"]["Resources"]["Limits"]["MemoryBytes"]
    )
    docker_params["labels"][
        _to_simcore_runtime_docker_label_key("cpu_limit")
    ] = container_spec["Labels"][
        _to_simcore_runtime_docker_label_key("cpu_limit")
    ] = f"{float(nano_cpus_limit) / 1e9}"
    docker_params["labels"][
        _to_simcore_runtime_docker_label_key("memory_limit")
    ] = container_spec["Labels"][
        _to_simcore_runtime_docker_label_key("memory_limit")
    ] = mem_limit

    # and make the container aware of them via env variables
    resource_limits = {
        CPU_RESOURCE_LIMIT_KEY: nano_cpus_limit,
        MEM_RESOURCE_LIMIT_KEY: mem_limit,
    }
    docker_params["task_template"]["ContainerSpec"]["Env"].update(resource_limits)

    _logger.debug(
        "Converted labels to docker runtime parameters: %s", pformat(docker_params)
    )
    return docker_params


def _get_service_entrypoint(
    service_boot_parameters_labels: list[dict[str, Any]]
) -> str:
    _logger.debug("Getting service entrypoint")
    for param in service_boot_parameters_labels:
        _check_setting_correctness(param)
        if param["name"] == "entry_point":
            _logger.debug("Service entrypoint is %s", param["value"])
            assert isinstance(param["value"], str)  # nosec
            return param["value"]
    return ""


async def _get_swarm_network(
    client: aiodocker.docker.Docker, app_settings: ApplicationSettings
) -> dict:
    network_name = "_default"
    if app_settings.DIRECTOR_SIMCORE_SERVICES_NETWORK_NAME:
        network_name = f"{app_settings.DIRECTOR_SIMCORE_SERVICES_NETWORK_NAME}"
    # try to find the network name (usually named STACKNAME_default)
    networks = [
        x
        for x in (await client.networks.list())
        if "swarm" in x["Scope"] and network_name in x["Name"]
    ]
    if not networks or len(networks) > 1:
        raise DirectorRuntimeError(
            msg=(
                "Swarm network name is not configured, found following networks "
                "(if there is more then 1 network, remove the one which has no "
                f"containers attached and all is fixed): {networks if networks else 'no swarm network!'}"
            )
        )
    return networks[0]


async def _get_docker_image_port_mapping(
    service: dict,
) -> tuple[str | None, int | None]:
    _logger.debug("getting port published by service: %s", service["Spec"]["Name"])

    published_ports = []
    target_ports = []
    if "Endpoint" in service:
        service_endpoints = service["Endpoint"]
        if "Ports" in service_endpoints:
            ports_info_json = service_endpoints["Ports"]
            for port in ports_info_json:
                published_ports.append(port["PublishedPort"])
                target_ports.append(port["TargetPort"])

    _logger.debug("Service %s publishes: %s ports", service["ID"], published_ports)
    published_port = None
    target_port = None
    if published_ports:
        published_port = published_ports[0]
    if target_ports:
        target_port = target_ports[0]
    # if empty no port is published but there might still be an internal port defined
    elif _to_simcore_runtime_docker_label_key("port") in service["Spec"]["Labels"]:
        target_port = int(
            service["Spec"]["Labels"][_to_simcore_runtime_docker_label_key("port")]
        )
    return published_port, target_port


@tenacity.retry(
    wait=tenacity.wait_fixed(2),
    stop=tenacity.stop_after_attempt(3) or tenacity.stop_after_delay(10),
)
async def _pass_port_to_service(
    service_name: str,
    port: str,
    service_boot_parameters_labels: list[Any],
    session: httpx.AsyncClient,
    app_settings: ApplicationSettings,
) -> None:
    for param in service_boot_parameters_labels:
        _check_setting_correctness(param)
        if param["name"] == "published_host":
            route = param["value"]
            _logger.debug(
                "Service needs to get published host %s:%s using route %s",
                app_settings.DIRECTOR_PUBLISHED_HOST_NAME,
                port,
                route,
            )
            service_url = "http://" + service_name + "/" + route  # NOSONAR
            query_string = {
                "hostname": app_settings.DIRECTOR_PUBLISHED_HOST_NAME,
                "port": str(port),
            }
            _logger.debug("creating request %s and query %s", service_url, query_string)
            response = await session.post(service_url, data=query_string)
            _logger.debug("query response: %s", response.text)
            return
    _logger.debug("service %s does not need to know its external port", service_name)


async def _create_network_name(service_name: str, node_uuid: str) -> str:
    return service_name + "_" + node_uuid


async def _create_overlay_network_in_swarm(
    client: aiodocker.docker.Docker, service_name: str, node_uuid: str
) -> str:
    _logger.debug(
        "Creating overlay network for service %s with uuid %s", service_name, node_uuid
    )
    network_name = await _create_network_name(service_name, node_uuid)
    try:
        network_config = {
            "Name": network_name,
            "Driver": "overlay",
            "Labels": {_to_simcore_runtime_docker_label_key("node_id"): node_uuid},
        }
        docker_network = await client.networks.create(network_config)
        _logger.debug(
            "Network %s created for service %s with uuid %s",
            network_name,
            service_name,
            node_uuid,
        )
        return cast(str, docker_network.id)
    except aiodocker.DockerError as err:
        msg = "Error while creating network"
        raise GenericDockerError(err=msg) from err


async def _remove_overlay_network_of_swarm(
    client: aiodocker.docker.Docker, node_uuid: str
) -> None:
    _logger.debug("Removing overlay network for service with uuid %s", node_uuid)
    try:
        networks = await client.networks.list()
        networks = [
            x
            for x in (await client.networks.list())
            if x["Labels"]
            and _to_simcore_runtime_docker_label_key("node_id") in x["Labels"]
            and x["Labels"][_to_simcore_runtime_docker_label_key("node_id")]
            == node_uuid
        ]
        _logger.debug("Found %s networks with uuid %s", len(networks), node_uuid)
        # remove any network in the list (should be only one)
        for network in networks:
            docker_network = aiodocker.networks.DockerNetwork(client, network["Id"])
            await docker_network.delete()
        _logger.debug("Removed %s networks with uuid %s", len(networks), node_uuid)
    except aiodocker.DockerError as err:
        msg = "Error while removing networks"
        raise GenericDockerError(err=msg) from err


async def _get_service_state(
    client: aiodocker.docker.Docker, service: dict, app_settings: ApplicationSettings
) -> tuple[ServiceState, str]:
    # some times one has to wait until the task info is filled
    service_name = service["Spec"]["Name"]
    _logger.debug("Getting service %s state", service_name)
    tasks = await client.tasks.list(filters={"service": service_name})

    # wait for tasks
    task_started_time = arrow.utcnow().datetime
    while (arrow.utcnow().datetime - task_started_time) < timedelta(seconds=20):
        tasks = await client.tasks.list(filters={"service": service_name})
        # only keep the ones with the right service ID (we're being a bit picky maybe)
        tasks = [x for x in tasks if x["ServiceID"] == service["ID"]]
        if tasks:
            break
        await asyncio.sleep(1)  # let other events happen too

    if not tasks:
        return (ServiceState.FAILED, "getting state timed out")

    # we are only interested in the last task which has been created last
    last_task = sorted(tasks, key=lambda task: task["UpdatedAt"])[-1]
    task_state = last_task["Status"]["State"]

    _logger.debug("%s %s", service["ID"], task_state)

    last_task_state = ServiceState.STARTING  # default
    last_task_error_msg = last_task["Status"].get("Err", "")
    if task_state in ("failed"):
        # check if it failed already the max number of attempts we allow for
        if len(tasks) < app_settings.DIRECTOR_SERVICES_RESTART_POLICY_MAX_ATTEMPTS:
            _logger.debug("number of tasks: %s", len(tasks))
            last_task_state = ServiceState.STARTING
        else:
            _logger.error(
                "service %s failed with %s after %s trials",
                service_name,
                last_task["Status"],
                len(tasks),
            )
            last_task_state = ServiceState.FAILED
    elif task_state in ("rejected"):
        _logger.error("service %s failed with %s", service_name, last_task["Status"])
        last_task_state = ServiceState.FAILED
    elif task_state in ("pending"):
        last_task_state = ServiceState.PENDING
    elif task_state in ("assigned", "accepted", "preparing"):
        last_task_state = ServiceState.PULLING
    elif task_state in ("ready", "starting"):
        last_task_state = ServiceState.STARTING
    elif task_state in ("running"):
        now = arrow.utcnow().datetime
        # NOTE: task_state_update_time is only used to discrimitate between 'starting' and 'running'
        task_state_update_time = to_datetime(last_task["Status"]["Timestamp"])
        time_since_running = now - task_state_update_time

        _logger.debug(
            "Now is %s, time since running mode is %s", now, time_since_running
        )
        if time_since_running > timedelta(
            seconds=app_settings.DIRECTOR_SERVICES_STATE_MONITOR_S
        ):
            last_task_state = ServiceState.RUNNING
        else:
            last_task_state = ServiceState.STARTING

    elif task_state in ("complete", "shutdown"):
        last_task_state = ServiceState.COMPLETE
    _logger.debug("service running state is %s", last_task_state)
    return (last_task_state, last_task_error_msg)


async def _wait_until_service_running_or_failed(
    client: aiodocker.docker.Docker, service: dict, node_uuid: str
) -> None:
    # some times one has to wait until the task info is filled
    service_name = service["Spec"]["Name"]
    _logger.debug("Waiting for service %s to start", service_name)
    while True:
        tasks = await client.tasks.list(filters={"service": service_name})
        # only keep the ones with the right service ID (we're being a bit picky maybe)
        tasks = [x for x in tasks if x["ServiceID"] == service["ID"]]
        # we are only interested in the last task which has index 0
        if tasks:
            last_task = tasks[0]
            task_state = last_task["Status"]["State"]
            _logger.debug("%s %s", service["ID"], task_state)
            if task_state in ("failed", "rejected"):
                _logger.error(
                    "Error while waiting for service with %s", last_task["Status"]
                )
                raise ServiceStartTimeoutError(
                    service_name=service_name, service_uuid=node_uuid
                )
            if task_state in ("running", "complete"):
                break
        # allows dealing with other events instead of wasting time here
        await asyncio.sleep(1)  # 1s
    _logger.debug("Waited for service %s to start", service_name)


async def _get_repos_from_key(app: FastAPI, service_key: str) -> dict[str, list[str]]:
    # get the available image for the main service (syntax is image:tag)
    list_of_images = {
        service_key: await registry_proxy.list_image_tags(app, service_key)
    }
    _logger.debug("entries %s", list_of_images)
    if not list_of_images[service_key]:
        raise ServiceNotAvailableError(service_name=service_key)

    _logger.debug(
        "Service %s has the following list of images available: %s",
        service_key,
        list_of_images,
    )

    return list_of_images


async def _get_dependant_repos(
    app: FastAPI, service_key: str, service_tag: str
) -> list[dict]:
    list_of_images = await _get_repos_from_key(app, service_key)
    tag = await _find_service_tag(list_of_images, service_key, service_tag)
    # look for dependencies
    return await registry_proxy.list_interactive_service_dependencies(
        app, service_key, tag
    )


_TAG_REGEX = re.compile(r"^\d+\.\d+\.\d+$")
_SERVICE_KEY_REGEX = re.compile(
    r"^(?P<key>simcore/services/"
    r"(?P<type>(comp|dynamic|frontend))/"
    r"(?P<subdir>[a-z0-9][a-z0-9_.-]*/)*"
    r"(?P<name>[a-z0-9-_]+[a-z0-9]))"
    r"(?::(?P<version>[\w][\w.-]{0,127}))?"
    r"(?P<docker_digest>\@sha256:[a-fA-F0-9]{32,64})?$"
)


async def _find_service_tag(
    list_of_images: dict, service_key: str, service_tag: str | None
) -> str:
    if service_key not in list_of_images:
        raise ServiceNotAvailableError(
            service_name=service_key, service_tag=service_tag
        )
    # filter incorrect chars
    filtered_tags_list = filter(_TAG_REGEX.search, list_of_images[service_key])
    # sort them now
    available_tags_list = sorted(filtered_tags_list, key=Version)
    # not tags available... probably an undefined service there...
    if not available_tags_list:
        raise ServiceNotAvailableError(
            service_name=service_key, service_tag=service_tag
        )
    tag = service_tag
    if not service_tag or service_tag == "latest":
        # get latest tag
        tag = available_tags_list[len(available_tags_list) - 1]
    elif available_tags_list.count(service_tag) != 1:
        raise ServiceNotAvailableError(
            service_name=service_key, service_tag=service_tag
        )

    _logger.debug("Service tag found is %s ", service_tag)
    assert tag is not None  # nosec
    return tag


async def _start_docker_service(
    app: FastAPI,
    *,
    client: aiodocker.docker.Docker,
    user_id: str,
    project_id: str,
    service_key: str,
    service_tag: str,
    main_service: bool,
    node_uuid: str,
    node_base_path: str,
    internal_network_id: str | None,
    request_simcore_user_agent: str,
) -> dict:  # pylint: disable=R0913
    app_settings = get_application_settings(app)
    service_parameters = await _create_docker_service_params(
        app,
        client=client,
        service_key=service_key,
        service_tag=service_tag,
        main_service=main_service,
        user_id=user_id,
        node_uuid=node_uuid,
        project_id=project_id,
        node_base_path=node_base_path,
        internal_network_id=internal_network_id,
        request_simcore_user_agent=request_simcore_user_agent,
    )
    _logger.debug(
        "Starting docker service %s:%s using parameters %s",
        service_key,
        service_tag,
        service_parameters,
    )
    # lets start the service
    try:
        service = await client.services.create(**service_parameters)
        if "ID" not in service:
            # error while starting service
            msg = f"Error while starting service: {service!s}"
            raise DirectorRuntimeError(msg=msg)
        _logger.debug("Service started now waiting for it to run")

        # get the full info from docker
        service = await client.services.inspect(service["ID"])
        service_name = service["Spec"]["Name"]
        service_state, service_msg = await _get_service_state(
            client, dict(service), app_settings=app_settings
        )

        # wait for service to start
        _logger.debug("Service %s successfully started", service_name)
        # the docker swarm maybe opened some random port to access the service, get the latest version of the service
        service = await client.services.inspect(service["ID"])
        published_port, target_port = await _get_docker_image_port_mapping(
            dict(service)
        )
        # now pass boot parameters
        service_boot_parameters_labels = await _read_service_settings(
            app, service_key, service_tag, SERVICE_RUNTIME_BOOTSETTINGS
        )
        service_entrypoint = ""
        if isinstance(service_boot_parameters_labels, list):
            service_entrypoint = _get_service_entrypoint(service_boot_parameters_labels)
            if published_port:
                session = get_client_session(app)
                await _pass_port_to_service(
                    service_name,
                    published_port,
                    service_boot_parameters_labels,
                    session,
                    app_settings=app_settings,
                )

        return {
            "published_port": published_port,
            "entry_point": service_entrypoint,
            "service_uuid": node_uuid,
            "service_key": service_key,
            "service_version": service_tag,
            "service_host": service_name,
            "service_port": target_port,
            "service_basepath": node_base_path,
            "service_state": service_state.value,
            "service_message": service_msg,
            "user_id": user_id,
            "project_id": project_id,
        }

    except ServiceStartTimeoutError:
        _logger.exception("Service failed to start")
        await _silent_service_cleanup(app, node_uuid)
        raise
    except aiodocker.DockerError as err:
        _logger.exception("Unexpected error")
        await _silent_service_cleanup(app, node_uuid)
        raise ServiceNotAvailableError(
            service_name=service_key, service_tag=service_tag
        ) from err


async def _silent_service_cleanup(app: FastAPI, node_uuid: str) -> None:
    with contextlib.suppress(DirectorRuntimeError):
        await stop_service(app, node_uuid=node_uuid, save_state=False)


async def _create_node(
    app: FastAPI,
    client: aiodocker.docker.Docker,
    user_id: str,
    project_id: str,
    list_of_services: list[dict],
    node_uuid: str,
    node_base_path: str,
    request_simcore_user_agent: str,
) -> list[dict]:  # pylint: disable=R0913, R0915
    _logger.debug(
        "Creating %s docker services for node %s and base path %s for user %s",
        len(list_of_services),
        node_uuid,
        node_base_path,
        user_id,
    )
    _logger.debug("Services %s will be started", list_of_services)

    # if the service uses several docker images, a network needs to be setup to connect them together
    inter_docker_network_id = None
    if len(list_of_services) > 1:
        service_name = registry_proxy.get_service_first_name(list_of_services[0]["key"])
        inter_docker_network_id = await _create_overlay_network_in_swarm(
            client, service_name, node_uuid
        )
        _logger.debug("Created docker network in swarm for service %s", service_name)

    containers_meta_data = []
    for service in list_of_services:
        service_meta_data = await _start_docker_service(
            app,
            client=client,
            user_id=user_id,
            project_id=project_id,
            service_key=service["key"],
            service_tag=service["tag"],
            main_service=list_of_services.index(service) == 0,
            node_uuid=node_uuid,
            node_base_path=node_base_path,
            internal_network_id=inter_docker_network_id,
            request_simcore_user_agent=request_simcore_user_agent,
        )
        containers_meta_data.append(service_meta_data)

    return containers_meta_data


async def _get_service_key_version_from_docker_service(
    service: dict, registry_settings: RegistrySettings
) -> tuple[str, str]:
    service_full_name = str(service["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"])
    if not service_full_name.startswith(registry_settings.resolved_registry_url):
        raise DirectorRuntimeError(
            msg=f"Invalid service '{service_full_name}', it is missing {registry_settings.resolved_registry_url}"
        )

    service_full_name = service_full_name[
        len(registry_settings.resolved_registry_url) :
    ].strip("/")
    service_re_match = _SERVICE_KEY_REGEX.match(service_full_name)
    if not service_re_match:
        raise DirectorRuntimeError(
            msg=f"Invalid service '{service_full_name}', it does not follow pattern '{_SERVICE_KEY_REGEX.pattern}'"
        )
    service_key = service_re_match.group("key")
    service_tag = service_re_match.group("version")
    return service_key, service_tag


async def _get_service_basepath_from_docker_service(service: dict[str, Any]) -> str:
    envs_list: list[str] = service["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"]
    envs_dict = dict(x.split("=") for x in envs_list)
    return envs_dict["SIMCORE_NODE_BASEPATH"]


async def start_service(
    app: FastAPI,
    user_id: str,
    project_id: str,
    service_key: str,
    service_tag: str | None,
    node_uuid: str,
    node_base_path: str,
    request_simcore_user_agent: str,
) -> dict:
    app_settings = get_application_settings(app)
    _logger.debug(
        "starting service %s:%s using uuid %s, basepath %s",
        service_key,
        service_tag,
        node_uuid,
        node_base_path,
    )
    # first check the uuid is available
    async with docker_utils.docker_client() as client:  # pylint: disable=not-async-context-manager
        await _check_node_uuid_available(client, node_uuid)
        list_of_images = await _get_repos_from_key(app, service_key)
        service_tag = await _find_service_tag(list_of_images, service_key, service_tag)
        _logger.debug("Found service to start %s:%s", service_key, service_tag)
        list_of_services_to_start = [{"key": service_key, "tag": service_tag}]
        # find the service dependencies
        list_of_dependencies = await _get_dependant_repos(app, service_key, service_tag)
        _logger.debug("Found service dependencies: %s", list_of_dependencies)
        if list_of_dependencies:
            list_of_services_to_start.extend(list_of_dependencies)

        containers_meta_data = await _create_node(
            app,
            client,
            user_id,
            project_id,
            list_of_services_to_start,
            node_uuid,
            node_base_path,
            request_simcore_user_agent,
        )
        node_details = containers_meta_data[0]
        if app_settings.DIRECTOR_MONITORING_ENABLED:
            get_instrumentation(app).services_started.labels(
                service_key=service_key,
                service_tag=service_tag,
                simcore_user_agent="undefined_user",
            ).inc()

        # we return only the info of the main service
        return node_details


async def _get_node_details(
    app: FastAPI, client: aiodocker.docker.Docker, service: dict
) -> dict:
    app_settings = get_application_settings(app)
    service_key, service_tag = await _get_service_key_version_from_docker_service(
        service, registry_settings=app_settings.DIRECTOR_REGISTRY
    )

    # get boot parameters
    results = await asyncio.gather(
        _read_service_settings(
            app, service_key, service_tag, SERVICE_RUNTIME_BOOTSETTINGS
        ),
        _get_service_basepath_from_docker_service(service),
        _get_service_state(client, service, app_settings=app_settings),
    )

    service_boot_parameters_labels = results[0]
    service_entrypoint = ""
    if service_boot_parameters_labels and isinstance(
        service_boot_parameters_labels, list
    ):
        service_entrypoint = _get_service_entrypoint(service_boot_parameters_labels)
    service_basepath = results[1]
    service_state, service_msg = results[2]
    service_name = service["Spec"]["Name"]
    service_uuid = service["Spec"]["Labels"][
        _to_simcore_runtime_docker_label_key("node_id")
    ]
    user_id = service["Spec"]["Labels"][_to_simcore_runtime_docker_label_key("user_id")]
    project_id = service["Spec"]["Labels"][
        _to_simcore_runtime_docker_label_key("project_id")
    ]

    # get the published port
    published_port, target_port = await _get_docker_image_port_mapping(service)
    return {
        "published_port": published_port,
        "entry_point": service_entrypoint,
        "service_uuid": service_uuid,
        "service_key": service_key,
        "service_version": service_tag,
        "service_host": service_name,
        "service_port": target_port,
        "service_basepath": service_basepath,
        "service_state": service_state.value,
        "service_message": service_msg,
        "user_id": user_id,
        "project_id": project_id,
    }


async def get_services_details(
    app: FastAPI, user_id: str | None, study_id: str | None
) -> list[dict]:
    app_settings = get_application_settings(app)
    async with docker_utils.docker_client() as client:  # pylint: disable=not-async-context-manager
        try:
            filters = [
                f"{_to_simcore_runtime_docker_label_key('type')}=main",
                f"{_to_simcore_runtime_docker_label_key('swarm_stack_name')}={app_settings.DIRECTOR_SWARM_STACK_NAME}",
            ]
            if user_id:
                filters.append(
                    f"{_to_simcore_runtime_docker_label_key('user_id')}=" + user_id
                )
            if study_id:
                filters.append(
                    f"{_to_simcore_runtime_docker_label_key('project_id')}=" + study_id
                )
            list_running_services = await client.services.list(
                filters={"label": filters}
            )

            return [
                await _get_node_details(app, client, dict(service))
                for service in list_running_services
            ]
        except aiodocker.DockerError as err:
            msg = f"Error while accessing container for {user_id=}, {study_id=}"
            raise GenericDockerError(err=msg) from err


async def get_service_details(app: FastAPI, node_uuid: str) -> dict:
    app_settings = get_application_settings(app)
    async with docker_utils.docker_client() as client:
        try:
            list_running_services_with_uuid = await client.services.list(
                filters={
                    "label": [
                        f"{_to_simcore_runtime_docker_label_key('node_id')}={node_uuid}",
                        f"{_to_simcore_runtime_docker_label_key('type')}=main",
                        f"{_to_simcore_runtime_docker_label_key('swarm_stack_name')}={app_settings.DIRECTOR_SWARM_STACK_NAME}",
                    ]
                }
            )
            # error if no service with such an id exists
            if not list_running_services_with_uuid:
                raise ServiceUUIDNotFoundError(service_uuid=node_uuid)

            if len(list_running_services_with_uuid) > 1:
                # someone did something fishy here
                raise DirectorRuntimeError(
                    msg="More than one docker service is labeled as main service"
                )

            return await _get_node_details(
                app, client, dict(list_running_services_with_uuid[0])
            )
        except aiodocker.DockerError as err:
            msg = f"Error while accessing container {node_uuid=}"
            raise GenericDockerError(err=msg) from err


@retry(
    wait=wait_random_exponential(min=1, max=5),
    stop=stop_after_attempt(3),
    reraise=True,
    retry=retry_if_exception_type(httpx.RequestError),
)
async def _save_service_state(
    service_host_name: str, session: httpx.AsyncClient
) -> None:
    try:
        response = await session.post(
            url=f"http://{service_host_name}/state",  # NOSONAR
            timeout=ServicesCommonSettings().director_dynamic_service_save_timeout,
        )
        response.raise_for_status()

    except httpx.HTTPStatusError as err:

        if err.response.status_code in (
            status.HTTP_405_METHOD_NOT_ALLOWED,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_501_NOT_IMPLEMENTED,
        ):
            # NOTE: Legacy Override. Some old services do not have a state entrypoint defined
            # therefore we assume there is nothing to be saved and do not raise exception
            # Responses found so far:
            #   METHOD NOT ALLOWED https://httpstatuses.com/405
            #   NOT FOUND https://httpstatuses.com/404
            #
            _logger.warning(
                "Service '%s' does not seem to implement save state functionality: %s. Skipping save",
                service_host_name,
                err,
            )
        else:
            # upss ... could service had troubles saving, reraise
            raise
    else:
        _logger.info(
            "Service '%s' successfully saved its state: %s",
            service_host_name,
            f"{response}",
        )


@run_sequentially_in_context(target_args=["node_uuid"])
async def stop_service(app: FastAPI, *, node_uuid: str, save_state: bool) -> None:
    app_settings = get_application_settings(app)
    _logger.debug(
        "stopping service with node_uuid=%s, save_state=%s", node_uuid, save_state
    )

    # get the docker client
    async with docker_utils.docker_client() as client:  # pylint: disable=not-async-context-manager
        try:
            list_running_services_with_uuid = await client.services.list(
                filters={
                    "label": [
                        f"{_to_simcore_runtime_docker_label_key('node_id')}={node_uuid}",
                        f"{_to_simcore_runtime_docker_label_key('swarm_stack_name')}={app_settings.DIRECTOR_SWARM_STACK_NAME}",
                    ]
                }
            )
        except aiodocker.DockerError as err:
            msg = f"Error while stopping container {node_uuid=}"
            raise GenericDockerError(err=msg) from err

        # error if no service with such an id exists
        if not list_running_services_with_uuid:
            raise ServiceUUIDNotFoundError(service_uuid=node_uuid)

        _logger.debug("found service(s) with uuid %s", list_running_services_with_uuid)

        # save the state of the main service if it can
        service_details = await get_service_details(app, node_uuid)
        service_host_name = "{}:{}{}".format(
            service_details["service_host"],
            (
                service_details["service_port"]
                if service_details["service_port"]
                else "80"
            ),
            (
                service_details["service_basepath"]
                if "3d-viewer" not in service_details["service_host"]
                else ""
            ),
        )

        # If state save is enforced
        if save_state:
            _logger.debug("saving state of service %s...", service_host_name)
            try:
                await _save_service_state(
                    service_host_name, session=get_client_session(app)
                )
            except httpx.HTTPStatusError as err:

                raise ServiceStateSaveError(
                    service_uuid=node_uuid,
                    reason=f"service {service_host_name} rejected to save state, "
                    f"responded {err.response.text} (status {err.response.status_code})."
                    "Aborting stop service to prevent data loss.",
                ) from err

            except httpx.RequestError as err:
                _logger.warning(
                    "Could not save state because %s is unreachable [%s]."
                    "Resuming stop_service.",
                    service_host_name,
                    err.request,
                )

        # remove the services
        try:
            _logger.debug("removing services ...")
            for service in list_running_services_with_uuid:
                _logger.debug("removing %s", service["Spec"]["Name"])
                await client.services.delete(service["Spec"]["Name"])

        except aiodocker.DockerError as err:
            msg = f"Error while removing services {node_uuid=}"
            raise GenericDockerError(err=msg) from err

        # remove network(s)
        _logger.debug("removed services, now removing network...")
        await _remove_overlay_network_of_swarm(client, node_uuid)
        _logger.debug("removed network")

        if app_settings.DIRECTOR_MONITORING_ENABLED:
            get_instrumentation(app).services_stopped.labels(
                service_key=service_details["service_key"],
                service_tag=service_details["service_version"],
                simcore_user_agent="undefined_user",
                result="SUCCESS",
            ).inc()
