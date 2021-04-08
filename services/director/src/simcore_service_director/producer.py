# pylint: disable=C0111, R0913

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from distutils.version import StrictVersion
from enum import Enum
from pprint import pformat
from typing import Dict, List, Optional, Tuple, Union, Any, Deque
from collections import deque

import aiodocker
import tenacity
from aiohttp import ClientConnectionError, ClientSession, web
from servicelib.async_utils import run_sequentially_in_context
from servicelib.monitor_services import service_started, service_stopped

from . import config, docker_utils, exceptions, registry_proxy
from .config import APP_CLIENT_SESSION_KEY
from .services_common import ServicesCommonSettings
from .system_utils import get_system_extra_hosts_raw
from .utils import get_swarm_network
from .directorv2_proxy import (
    start_service_sidecar_stack,
    stop_service_sidecar_stack,
    get_service_sidecar_stack_status,
)

log = logging.getLogger(__name__)


class ServiceState(Enum):
    PENDING = "pending"
    PULLING = "pulling"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


async def _create_auth() -> Dict[str, str]:
    return {"username": config.REGISTRY_USER, "password": config.REGISTRY_PW}


async def _check_node_uuid_available(
    client: aiodocker.docker.Docker, node_uuid: str
) -> None:
    log.debug("Checked if UUID %s is already in use", node_uuid)
    # check if service with same uuid already exists
    try:
        # not filtering by "swarm_stack_name" label because it's safer
        list_of_running_services_w_uuid = await client.services.list(
            filters={"label": "uuid=" + node_uuid}
        )
    except aiodocker.exceptions.DockerError as err:
        log.exception("Error while retrieving services list")
        raise exceptions.GenericDockerError(
            "Error while retrieving services", err
        ) from err
    if list_of_running_services_w_uuid:
        raise exceptions.ServiceUUIDInUseError(node_uuid)
    log.debug("UUID %s is free", node_uuid)


def _check_setting_correctness(setting: Dict) -> None:
    if "name" not in setting or "type" not in setting or "value" not in setting:
        raise exceptions.DirectorException("Invalid setting in %s" % setting)


def _parse_mount_settings(settings: List[Dict]) -> List[Dict]:
    mounts = list()
    for s in settings:
        log.debug("Retrieved mount settings %s", s)
        mount = dict()
        mount["ReadOnly"] = True
        if "ReadOnly" in s and s["ReadOnly"] in ["false", "False", False]:
            mount["ReadOnly"] = False

        for field in ["Source", "Target", "Type"]:
            if field in s:
                mount[field] = s[field]
            else:
                log.warning(
                    "Mount settings have wrong format. Required keys [Source, Target, Type]"
                )
                continue

        log.debug("Append mount settings %s", mount)
        mounts.append(mount)

    return mounts


def _parse_env_settings(settings: List[str]) -> Dict:
    envs = dict()
    for s in settings:
        log.debug("Retrieved env settings %s", s)
        if "=" in s:
            parts = s.split("=")
            if len(parts) == 2:
                envs.update({parts[0]: parts[1]})

        log.debug("Parsed env settings %s", s)

    return envs


async def _read_service_settings(
    app: web.Application, key: str, tag: str, settings_name: str
) -> Dict:
    image_labels = await registry_proxy.get_image_labels(app, key, tag)
    settings = (
        json.loads(image_labels[settings_name]) if settings_name in image_labels else {}
    )

    log.debug("Retrieved %s settings: %s", settings_name, pformat(settings))
    return settings


# pylint: disable=too-many-branches
async def _create_docker_service_params(
    app: web.Application,
    client: aiodocker.docker.Docker,
    service_key: str,
    service_tag: str,
    main_service: bool,
    user_id: str,
    node_uuid: str,
    project_id: str,
    node_base_path: str,
    internal_network_id: Optional[str],
) -> Dict:
    # pylint: disable=too-many-statements
    service_parameters_labels = await _read_service_settings(
        app, service_key, service_tag, config.SERVICE_RUNTIME_SETTINGS
    )
    reverse_proxy_settings = await _read_service_settings(
        app, service_key, service_tag, config.SERVICE_REVERSE_PROXY_SETTINGS
    )
    service_name = registry_proxy.get_service_last_names(service_key) + "_" + node_uuid
    log.debug("Converting labels to docker runtime parameters")
    container_spec = {
        "Image": f"{config.REGISTRY_PATH}/{service_key}:{service_tag}",
        "Env": {
            **config.SERVICES_DEFAULT_ENVS,
            "SIMCORE_USER_ID": user_id,
            "SIMCORE_NODE_UUID": node_uuid,
            "SIMCORE_PROJECT_ID": project_id,
            "SIMCORE_NODE_BASEPATH": node_base_path or "",
            "SIMCORE_HOST_NAME": service_name,
        },
        "Hosts": get_system_extra_hosts_raw(config.EXTRA_HOSTS_SUFFIX),
        "Init": True,
        "Labels": {
            "user_id": user_id,
            "study_id": project_id,
            "node_id": node_uuid,
            "swarm_stack_name": config.SWARM_STACK_NAME,
        },
        "Mounts": [],
    }

    if (
        config.DIRECTOR_SELF_SIGNED_SSL_FILENAME
        and config.DIRECTOR_SELF_SIGNED_SSL_SECRET_ID
        and config.DIRECTOR_SELF_SIGNED_SSL_SECRET_NAME
    ):
        # Note: this is useful for S3 client in case of self signed certificate
        container_spec["Env"][
            "SSL_CERT_FILE"
        ] = config.DIRECTOR_SELF_SIGNED_SSL_FILENAME
        container_spec["Secrets"] = [
            {
                "SecretID": config.DIRECTOR_SELF_SIGNED_SSL_SECRET_ID,
                "SecretName": config.DIRECTOR_SELF_SIGNED_SSL_SECRET_NAME,
                "File": {
                    "Name": config.DIRECTOR_SELF_SIGNED_SSL_FILENAME,
                    "Mode": 444,
                    "UID": "0",
                    "GID": "0",
                },
            }
        ]

    docker_params = {
        "auth": await _create_auth() if config.REGISTRY_AUTH else {},
        "registry": config.REGISTRY_PATH if config.REGISTRY_AUTH else "",
        "name": service_name,
        "task_template": {
            "ContainerSpec": container_spec,
            "Placement": {
                "Constraints": ["node.role==worker"]
                if await docker_utils.swarm_has_worker_nodes()
                else []
            },
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": config.DIRECTOR_SERVICES_RESTART_POLICY_DELAY_S * pow(10, 6),
                "MaxAttempts": config.DIRECTOR_SERVICES_RESTART_POLICY_MAX_ATTEMPTS,
            },
            "Resources": {
                "Limits": {"NanoCPUs": 2 * pow(10, 9), "MemoryBytes": 1 * pow(1024, 3)},
                "Reservations": {
                    "NanoCPUs": 1 * pow(10, 8),
                    "MemoryBytes": 500 * pow(1024, 2),
                },
            },
        },
        "endpoint_spec": {"Mode": "dnsrr"},
        "labels": {
            "uuid": node_uuid,
            "study_id": project_id,
            "user_id": user_id,
            "type": "main" if main_service else "dependency",
            "swarm_stack_name": config.SWARM_STACK_NAME,
            "io.simcore.zone": f"{config.TRAEFIK_SIMCORE_ZONE}",
            "traefik.enable": "true" if main_service else "false",
            f"traefik.http.services.{service_name}.loadbalancer.server.port": "8080",
            f"traefik.http.routers.{service_name}.rule": f"PathPrefix(`/x/{node_uuid}`)",
            f"traefik.http.routers.{service_name}.entrypoints": "http",
            f"traefik.http.routers.{service_name}.priority": "10",
            f"traefik.http.routers.{service_name}.middlewares": f"{config.SWARM_STACK_NAME}_gzip@docker",
        },
        "networks": [internal_network_id] if internal_network_id else [],
    }

    if config.DIRECTOR_SERVICES_CUSTOM_CONSTRAINTS:
        log.debug(
            "adding custom constraints %s ", config.DIRECTOR_SERVICES_CUSTOM_CONSTRAINTS
        )
        docker_params["task_template"]["Placement"]["Constraints"] += [
            config.DIRECTOR_SERVICES_CUSTOM_CONSTRAINTS
        ]

    if reverse_proxy_settings:
        # some services define strip_path:true if they need the path to be stripped away
        if (
            "strip_path" in reverse_proxy_settings
            and reverse_proxy_settings["strip_path"]
        ):
            docker_params["labels"][
                f"traefik.http.middlewares.{service_name}_stripprefixregex.stripprefixregex.regex"
            ] = f"^/x/{node_uuid}"
            docker_params["labels"][
                f"traefik.http.routers.{service_name}.middlewares"
            ] += f", {service_name}_stripprefixregex"

    for param in service_parameters_labels:
        _check_setting_correctness(param)
        # replace %service_uuid% by the given uuid
        if str(param["value"]).find("%service_uuid%") != -1:
            dummy_string = json.dumps(param["value"])
            dummy_string = dummy_string.replace("%service_uuid%", node_uuid)
            param["value"] = json.loads(dummy_string)

        # NOTE: the below capitalize addresses a bug in a lot of already in use services
        # where Resources was written in lower case
        if param["type"].capitalize() == "Resources":
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
            if "Limits" in param["value"] or "Reservations" in param["value"]:
                docker_params["task_template"]["Resources"].update(param["value"])

        # publishing port on the ingress network.
        elif param["name"] == "ports" and param["type"] == "int":  # backward comp
            docker_params["labels"]["port"] = docker_params["labels"][
                f"traefik.http.services.{service_name}.loadbalancer.server.port"
            ] = str(param["value"])
        # REST-API compatible
        elif param["type"] == "EndpointSpec":
            if "Ports" in param["value"]:
                if (
                    isinstance(param["value"]["Ports"], list)
                    and "TargetPort" in param["value"]["Ports"][0]
                ):
                    docker_params["labels"]["port"] = docker_params["labels"][
                        f"traefik.http.services.{service_name}.loadbalancer.server.port"
                    ] = str(param["value"]["Ports"][0]["TargetPort"])

        # placement constraints
        elif param["name"] == "constraints":  # python-API compatible
            docker_params["task_template"]["Placement"]["Constraints"] += param["value"]
        elif param["type"] == "Constraints":  # REST-API compatible
            docker_params["task_template"]["Placement"]["Constraints"] += param["value"]
        elif param["name"] == "env":
            log.debug("Found env parameter %s", param["value"])
            env_settings = _parse_env_settings(param["value"])
            if env_settings:
                docker_params["task_template"]["ContainerSpec"]["Env"].update(
                    env_settings
                )
        elif param["name"] == "mount":
            log.debug("Found mount parameter %s", param["value"])
            mount_settings: List[Dict] = _parse_mount_settings(param["value"])
            if mount_settings:
                docker_params["task_template"]["ContainerSpec"]["Mounts"].extend(
                    mount_settings
                )

    # attach the service to the swarm network dedicated to services
    try:
        swarm_network = await get_swarm_network(client)
        swarm_network_id = swarm_network["Id"]
        swarm_network_name = swarm_network["Name"]
        docker_params["networks"].append(swarm_network_id)
        docker_params["labels"]["traefik.docker.network"] = swarm_network_name

    except exceptions.DirectorException:
        log.exception("Could not find swarm network")

    # set labels for CPU and Memory limits
    container_spec["Labels"]["nano_cpus_limit"] = str(
        docker_params["task_template"]["Resources"]["Limits"]["NanoCPUs"]
    )
    container_spec["Labels"]["mem_limit"] = str(
        docker_params["task_template"]["Resources"]["Limits"]["MemoryBytes"]
    )

    log.debug(
        "Converted labels to docker runtime parameters: %s", pformat(docker_params)
    )
    return docker_params


def _get_service_entrypoint(service_boot_parameters_labels: Dict) -> str:
    log.debug("Getting service entrypoint")
    for param in service_boot_parameters_labels:
        _check_setting_correctness(param)
        if param["name"] == "entry_point":
            log.debug("Service entrypoint is %s", param["value"])
            return param["value"]
    return ""


async def _get_swarm_network(client: aiodocker.docker.Docker) -> Dict:
    network_name = "_default"
    if config.SIMCORE_SERVICES_NETWORK_NAME:
        network_name = "{}".format(config.SIMCORE_SERVICES_NETWORK_NAME)
    # try to find the network name (usually named STACKNAME_default)
    networks = [
        x
        for x in (await client.networks.list())
        if "swarm" in x["Scope"] and network_name in x["Name"]
    ]
    if not networks or len(networks) > 1:
        raise exceptions.DirectorException(
            msg=(
                "Swarm network name is not configured, found following networks "
                "(if there is more then 1 network, remove the one which has no "
                f"containers attached and all is fixed): {networks}"
            )
        )
    return networks[0]


async def _get_docker_image_port_mapping(
    service: Dict,
) -> Tuple[Optional[str], Optional[int]]:
    log.debug("getting port published by service: %s", service["Spec"]["Name"])

    published_ports = list()
    target_ports = list()
    if "Endpoint" in service:
        service_endpoints = service["Endpoint"]
        if "Ports" in service_endpoints:
            ports_info_json = service_endpoints["Ports"]
            for port in ports_info_json:
                published_ports.append(port["PublishedPort"])
                target_ports.append(port["TargetPort"])

    log.debug("Service %s publishes: %s ports", service["ID"], published_ports)
    published_port = None
    target_port = None
    if published_ports:
        published_port = published_ports[0]
    if target_ports:
        target_port = target_ports[0]
    else:
        # if empty no port is published but there might still be an internal port defined
        if "port" in service["Spec"]["Labels"]:
            target_port = int(service["Spec"]["Labels"]["port"])
    return published_port, target_port


@tenacity.retry(
    wait=tenacity.wait_fixed(2),
    stop=tenacity.stop_after_attempt(3) or tenacity.stop_after_delay(10),
)
async def _pass_port_to_service(
    service_name: str,
    port: str,
    service_boot_parameters_labels: Dict,
    session: ClientSession,
) -> None:
    for param in service_boot_parameters_labels:
        _check_setting_correctness(param)
        if param["name"] == "published_host":
            # time.sleep(5)
            route = param["value"]
            log.debug(
                "Service needs to get published host %s:%s using route %s",
                config.PUBLISHED_HOST_NAME,
                port,
                route,
            )
            service_url = "http://" + service_name + "/" + route
            query_string = {
                "hostname": str(config.PUBLISHED_HOST_NAME),
                "port": str(port),
            }
            log.debug("creating request %s and query %s", service_url, query_string)
            async with session.post(service_url, data=query_string) as response:
                log.debug("query response: %s", await response.text())
            return
    log.debug("service %s does not need to know its external port", service_name)


async def _create_network_name(service_name: str, node_uuid: str) -> str:
    return service_name + "_" + node_uuid


async def _create_overlay_network_in_swarm(
    client: aiodocker.docker.Docker, service_name: str, node_uuid: str
) -> str:
    log.debug(
        "Creating overlay network for service %s with uuid %s", service_name, node_uuid
    )
    network_name = await _create_network_name(service_name, node_uuid)
    try:
        network_config = {
            "Name": network_name,
            "Driver": "overlay",
            "Labels": {
                "uuid": node_uuid,
                "io.simcore.zone": f"{config.TRAEFIK_SIMCORE_ZONE}",
            },
        }
        docker_network = await client.networks.create(network_config)
        log.debug(
            "Network %s created for service %s with uuid %s",
            network_name,
            service_name,
            node_uuid,
        )
        return docker_network.id
    except aiodocker.exceptions.DockerError as err:
        log.exception("Error while creating network for service %s", service_name)
        raise exceptions.GenericDockerError(
            "Error while creating network", err
        ) from err


def _filter_remove_network(network: Dict, node_uuid: str) -> bool:
    """Retruns True if network should be removed"""
    labels = network["Labels"]
    return (
        labels
        and labels.get("uuid") == node_uuid
        and labels.get("io.simcore.zone") == f"{config.TRAEFIK_SIMCORE_ZONE}"
    )


async def _remove_overlay_network_of_swarm(
    client: aiodocker.docker.Docker, node_uuid: str
) -> None:
    log.debug("Removing overlay network for service with uuid %s", node_uuid)
    try:
        networks = [
            x
            for x in (await client.networks.list())
            if _filter_remove_network(x, node_uuid)
        ]
        log.debug("Found %s networks with uuid %s", len(networks), node_uuid)
        # remove any network in the list (should be only one)
        for network in networks:
            docker_network = aiodocker.networks.DockerNetwork(client, network["Id"])
            await docker_network.delete()
        log.debug("Removed %s networks with uuid %s", len(networks), node_uuid)
    except aiodocker.exceptions.DockerError as err:
        log.exception(
            "Error while removing networks for service with uuid: %s", node_uuid
        )
        raise exceptions.GenericDockerError(
            "Error while removing networks", err
        ) from err


DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


async def _get_service_state(
    client: aiodocker.docker.Docker, service: Dict
) -> Tuple[ServiceState, str]:
    # some times one has to wait until the task info is filled
    service_name = service["Spec"]["Name"]
    log.debug("Getting service %s state", service_name)
    tasks = await client.tasks.list(filters={"service": service_name})

    async def _wait_for_tasks(tasks):
        task_started_time = datetime.utcnow()
        while (datetime.utcnow() - task_started_time) < timedelta(seconds=20):
            tasks = await client.tasks.list(filters={"service": service_name})
            # only keep the ones with the right service ID (we're being a bit picky maybe)
            tasks = [x for x in tasks if x["ServiceID"] == service["ID"]]
            if tasks:
                return
            await asyncio.sleep(1)  # let other events happen too

    await _wait_for_tasks(tasks)
    if not tasks:
        return (ServiceState.FAILED, "getting state timed out")

    # we are only interested in the last task which has been created last
    last_task = sorted(tasks, key=lambda task: task["UpdatedAt"])[-1]
    task_state = last_task["Status"]["State"]

    def _to_datetime(datetime_str: str) -> datetime:
        # datetime_str is typically '2020-10-09T12:28:14.771034099Z'
        #  - The T separates the date portion from the time-of-day portion
        #  - The Z on the end means UTC, that is, an offset-from-UTC
        # The 099 before the Z is not clear, therefore we will truncate the last part
        N = len("2020-10-09T12:28:14.7710")
        if len(datetime_str) > N:
            datetime_str = datetime_str[:N]
        return datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S.%f")

    task_state_update_time = _to_datetime(last_task["Status"]["Timestamp"])
    log.debug("%s %s: time %s", service["ID"], task_state, task_state_update_time)

    last_task_state = ServiceState.STARTING  # default
    last_task_error_msg = (
        last_task["Status"]["Err"] if "Err" in last_task["Status"] else ""
    )
    if task_state in ("failed"):
        # check if it failed already the max number of attempts we allow for
        if len(tasks) < config.DIRECTOR_SERVICES_RESTART_POLICY_MAX_ATTEMPTS:
            log.debug("number of tasks: %s", len(tasks))
            last_task_state = ServiceState.STARTING
        else:
            log.error(
                "service %s failed with %s after %s trials",
                service_name,
                last_task["Status"],
                len(tasks),
            )
            last_task_state = ServiceState.FAILED
    elif task_state in ("rejected"):
        log.error("service %s failed with %s", service_name, last_task["Status"])
        last_task_state = ServiceState.FAILED
    elif task_state in ("pending"):
        last_task_state = ServiceState.PENDING
    elif task_state in ("assigned", "accepted", "preparing"):
        last_task_state = ServiceState.PULLING
    elif task_state in ("ready", "starting"):
        last_task_state = ServiceState.STARTING
    elif task_state in ("running"):
        now = datetime.utcnow()
        time_since_running = now - task_state_update_time
        log.debug("Now is %s, time since running mode is %s", now, time_since_running)
        if time_since_running > timedelta(
            seconds=config.DIRECTOR_SERVICES_STATE_MONITOR_S
        ):
            last_task_state = ServiceState.RUNNING
        else:
            last_task_state = ServiceState.STARTING
    elif task_state in ("complete", "shutdown"):
        last_task_state = ServiceState.COMPLETE
    log.debug("service running state is %s", last_task_state)
    return (last_task_state, last_task_error_msg)


async def _wait_until_service_running_or_failed(
    client: aiodocker.docker.Docker, service: Dict, node_uuid: str
) -> None:
    # some times one has to wait until the task info is filled
    service_name = service["Spec"]["Name"]
    log.debug("Waiting for service %s to start", service_name)
    while True:
        tasks = await client.tasks.list(filters={"service": service_name})
        # only keep the ones with the right service ID (we're being a bit picky maybe)
        tasks = [x for x in tasks if x["ServiceID"] == service["ID"]]
        # we are only interested in the last task which has index 0
        if tasks:
            last_task = tasks[0]
            task_state = last_task["Status"]["State"]
            log.debug("%s %s", service["ID"], task_state)
            if task_state in ("failed", "rejected"):
                log.error(
                    "Error while waiting for service with %s", last_task["Status"]
                )
                raise exceptions.ServiceStartTimeoutError(service_name, node_uuid)
            if task_state in ("running", "complete"):
                break
        # allows dealing with other events instead of wasting time here
        await asyncio.sleep(1)  # 1s
    log.debug("Waited for service %s to start", service_name)


async def _get_repos_from_key(
    app: web.Application, service_key: str
) -> Dict[str, List[Dict]]:
    # get the available image for the main service (syntax is image:tag)
    list_of_images = {
        service_key: await registry_proxy.list_image_tags(app, service_key)
    }
    log.debug("entries %s", list_of_images)
    if not list_of_images[service_key]:
        raise exceptions.ServiceNotAvailableError(service_key)

    log.debug(
        "Service %s has the following list of images available: %s",
        service_key,
        list_of_images,
    )

    return list_of_images


async def _get_dependant_repos(
    app: web.Application, service_key: str, service_tag: str
) -> List[Dict]:
    list_of_images = await _get_repos_from_key(app, service_key)
    tag = await _find_service_tag(list_of_images, service_key, service_tag)
    # look for dependencies
    dependent_repositories = await registry_proxy.list_interactive_service_dependencies(
        app, service_key, tag
    )
    return dependent_repositories


async def _find_service_tag(
    list_of_images: Dict, service_key: str, service_tag: str
) -> str:
    if not service_key in list_of_images:
        raise exceptions.ServiceNotAvailableError(
            service_name=service_key, service_tag=service_tag
        )
    # filter incorrect chars
    regex = re.compile(r"^\d+\.\d+\.\d+$")
    filtered_tags_list = filter(regex.search, list_of_images[service_key])
    # sort them now
    available_tags_list = sorted(filtered_tags_list, key=StrictVersion)
    # not tags available... probably an undefined service there...
    if not available_tags_list:
        raise exceptions.ServiceNotAvailableError(service_key, service_tag)
    tag = service_tag
    if not service_tag or service_tag == "latest":
        # get latest tag
        tag = available_tags_list[len(available_tags_list) - 1]
    elif available_tags_list.count(service_tag) != 1:
        raise exceptions.ServiceNotAvailableError(
            service_name=service_key, service_tag=service_tag
        )

    log.debug("Service tag found is %s ", service_tag)
    return tag


async def _start_docker_service(
    app: web.Application,
    client: aiodocker.docker.Docker,
    user_id: str,
    project_id: str,
    service_key: str,
    service_tag: str,
    main_service: bool,
    node_uuid: str,
    node_base_path: str,
    internal_network_id: Optional[str],
) -> Dict:  # pylint: disable=R0913
    service_parameters = await _create_docker_service_params(
        app,
        client,
        service_key,
        service_tag,
        main_service,
        user_id,
        node_uuid,
        project_id,
        node_base_path,
        internal_network_id,
    )
    log.debug(
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
            raise exceptions.DirectorException(
                "Error while starting service: {}".format(str(service))
            )
        log.debug("Service started now waiting for it to run")

        # get the full info from docker
        service = await client.services.inspect(service["ID"])
        service_name = service["Spec"]["Name"]
        service_state, service_msg = await _get_service_state(client, service)

        # wait for service to start
        # await _wait_until_service_running_or_failed(client, service, node_uuid)
        log.debug("Service %s successfully started", service_name)
        # the docker swarm maybe opened some random port to access the service, get the latest version of the service
        service = await client.services.inspect(service["ID"])
        published_port, target_port = await _get_docker_image_port_mapping(service)
        # now pass boot parameters
        service_boot_parameters_labels = await _read_service_settings(
            app, service_key, service_tag, config.SERVICE_RUNTIME_BOOTSETTINGS
        )
        service_entrypoint = _get_service_entrypoint(service_boot_parameters_labels)
        if published_port:
            session = app[APP_CLIENT_SESSION_KEY]
            await _pass_port_to_service(
                service_name, published_port, service_boot_parameters_labels, session
            )

        return format_node_details_for_frontend(
            published_port=published_port,
            entry_point=service_entrypoint,
            service_uuid=node_uuid,
            service_key=service_key,
            service_version=service_tag,
            service_host=service_name,
            service_port=target_port,
            service_basepath=node_base_path,
            service_state=service_state,
            service_message=service_msg,
        )

    except exceptions.ServiceStartTimeoutError as err:
        log.exception("Service failed to start")
        await _silent_service_cleanup(app, node_uuid)
        raise
    except aiodocker.exceptions.DockerError as err:
        log.exception("Unexpected error")
        await _silent_service_cleanup(app, node_uuid)
        raise exceptions.ServiceNotAvailableError(service_key, service_tag) from err


async def _silent_service_cleanup(app: web.Application, node_uuid: str) -> None:
    try:
        await stop_service(app, node_uuid)
    except exceptions.DirectorException:
        pass


def _get_value_from_label(labels: Dict[str, Any], key: str) -> Any:
    """
    If a value is empty string it will be treated as None
    'null' values in yaml spec are converted to empty string.
    """
    value = labels.get(key, None)
    return None if value == "" else value


MATCH_SERVICE_TAG = "${SERVICE_TAG}"
MATCH_IMAGE_START = "${REGISTRY_URL}/"
MATCH_IMAGE_END = f":{MATCH_SERVICE_TAG}"


def _assemble_key(service_key: str, service_tag: str) -> str:
    return f"{service_key}:{service_tag}"


async def _extract_osparc_involved_service_labels(
    app: web.Application,
    service_key: str,
    service_tag: str,
    service_labels: Dict[str, str],
    compose_spec: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Returns all the involved oSPARC services from the provided service labels.

    If the service contains a compose-spec that will also be parsed for images.
    Searches for images like the following in the spec:
    - `${REGISTRY_URL}/**SOME_SERVICE_NAME**:${SERVICE_TAG}`
    - `${REGISTRY_URL}/**SOME_SERVICE_NAME**:1.2.3` where `1.2.3` is a hardcoded tag
    """

    # initialize with existing labels
    # stores labels mapped by image_name service:tag
    docker_image_name_by_services: Dict[str, Any] = {
        _assemble_key(service_key=service_key, service_tag=service_tag): service_labels
    }
    if compose_spec is None:
        return docker_image_name_by_services

    # maps form image_name to compose_spec key
    reverse_mapping: Dict[str, str] = {}

    for compose_service_key, service_data in compose_spec.get("services", {}).items():

        image = service_data.get("image", None)
        if image is None:
            continue

        # if image dose not have this format skip:
        # - `${REGISTRY_URL}/**SOME_SERVICE_NAME**:${SERVICE_TAG}`
        # - `${REGISTRY_URL}/**SOME_SERVICE_NAME**:1.2.3` a hardcoded tag
        if not image.startswith(MATCH_IMAGE_START) or ":" not in image:
            continue
        if not image.startswith(MATCH_IMAGE_START) or not image.endswith(
            MATCH_IMAGE_END
        ):
            continue

        # strips `${REGISTRY_URL}/`; replaces `${SERVICE_TAG}` with `service_tag`
        osparc_image_key = image.replace(MATCH_SERVICE_TAG, service_tag).replace(
            MATCH_IMAGE_START, ""
        )
        current_service_key, current_service_tag = osparc_image_key.split(":")
        involved_key = _assemble_key(
            service_key=current_service_key, service_tag=current_service_tag
        )
        reverse_mapping[involved_key] = compose_service_key

        # if the labels already existed no need to fetch them again
        if involved_key in docker_image_name_by_services:
            continue

        docker_image_name_by_services[
            involved_key
        ] = await registry_proxy.get_image_labels(
            app=app, image=current_service_key, tag=current_service_tag
        )

    # remaps from image_name as key to compose_spec key
    compose_spec_mapped_labels = {
        reverse_mapping[k]: v for k, v in docker_image_name_by_services.items()
    }
    return compose_spec_mapped_labels


def _merge_resources_in_settings(
    settings: Deque[Dict[str, Any]]
) -> Deque[Dict[str, Any]]:
    """All oSPARC services which have defined resource requirements will be added"""
    result: Deque[Dict[str, Any]] = deque()
    resources_entries: Deque[Dict[str, Any]] = deque()

    log.debug("merging settings %s", settings)

    for entry in settings:
        if entry.get("name") == "Resources" and entry.get("type") == "Resources":
            resources_entries.append(entry)
        else:
            result.append(entry)

    if len(resources_entries) <= 1:
        return settings

    # merge all resources
    empty_resource_entry: Dict[str, Any] = {
        "name": "Resources",
        "type": "Resources",
        "value": {
            "Limits": {"NanoCPUs": 0, "MemoryBytes": 0},
            "Reservations": {
                "NanoCPUs": 0,
                "MemoryBytes": 0,
                "GenericResources": [],
            },
        },
    }

    for resource_entry in resources_entries:
        limits = resource_entry["value"].get("Limits", {})
        empty_resource_entry["value"]["Limits"]["NanoCPUs"] += limits.get("NanoCPUs", 0)
        empty_resource_entry["value"]["Limits"]["MemoryBytes"] += limits.get(
            "MemoryBytes", 0
        )

        reservations = resource_entry["value"].get("Reservations", {})
        empty_resource_entry["value"]["Reservations"]["NanoCPUs"] = reservations.get(
            "NanoCPUs", 0
        )
        empty_resource_entry["value"]["Reservations"]["MemoryBytes"] = reservations.get(
            "MemoryBytes", 0
        )
        empty_resource_entry["value"]["Reservations"]["GenericResources"] = []
        # put all generic resources together without looking for duplicates
        empty_resource_entry["value"]["Reservations"]["GenericResources"].extend(
            reservations.get("GenericResources", [])
        )

    result.append(empty_resource_entry)

    return result


def _inject_target_service_into_env_vars(
    settings: Deque[Dict[str, Any]]
) -> Deque[Dict[str, Any]]:
    """NOTE: this method will modify settings in place"""

    def _forma_env_var(env_var: str, destination_container: str) -> str:
        var_name, var_payload = env_var.split("=")
        json_encoded = json.dumps(
            dict(destination_container=destination_container, env_var=var_payload)
        )
        return f"{var_name}={json_encoded}"

    for entry in settings:
        if entry.get("name") == "env" and entry.get("type") == "string":
            # process entry
            list_of_env_vars = entry.get("value", [])
            destination_container = entry["destination_container"]

            # transforms settings defined environment variables
            # from `ENV_VAR=PAYLOAD`
            # to   `ENV_VAR={"destination_container": "destination_container", "env_var": "PAYLOAD"}`
            entry["value"] = [
                _forma_env_var(x, destination_container) for x in list_of_env_vars
            ]

    return settings


def _add_compose_destination_container_to_settings_entries(
    settings: Deque[Dict[str, Any]], destination_container: str
) -> List[Dict[str, Any]]:
    def _inject_destination_container(item: Dict[str, Any]):
        item["destination_container"] = destination_container
        return item

    return [_inject_destination_container(x) for x in settings]


def _strip_compose_destination_container_from_settings_entries(
    settings: Deque[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    def _remove_destination_container(item: Dict[str, Any]):
        item.pop("destination_container", None)
        return item

    return [_remove_destination_container(x) for x in settings]


async def _start_docker_service_with_dynamic_service(
    app: web.Application,
    client: aiodocker.docker.Docker,
    user_id: str,
    project_id: str,
    node_uuid: str,
    service: Dict[str, Any],
    request_scheme: str,
    request_dns: str,
):
    """
    Assembles and passes on all the required information for the service
    to be ran by the service-sidecar.
    """
    image_labels = await registry_proxy.get_image_labels(
        app=app, image=service["key"], tag=service["tag"]
    )
    log.info(
        "image=%s, tag=%s, labels=%s", service["key"], service["tag"], image_labels
    )

    # paths_mapping express how to map service-sidecar paths to the compose-spec volumes
    # where the service expects to find its certain folders
    paths_mapping = _get_value_from_label(image_labels, "simcore.service.paths-mapping")
    if paths_mapping is None:
        raise exceptions.DirectorException(
            f"No label 'simcore.service.paths-mapping' defined for service {service}"
        )
    paths_mapping: Dict[str, Any] = json.loads(paths_mapping)

    str_compose_spec: Optional[str] = _get_value_from_label(
        image_labels, "simcore.service.compose-spec"
    )
    compose_spec: Optional[Dict[str, Any]] = (
        None if str_compose_spec is None else json.loads(str_compose_spec)
    )

    labels_for_involved_services: Dict[
        str, Any
    ] = await _extract_osparc_involved_service_labels(
        app=app,
        service_key=service["key"],
        service_tag=service["tag"],
        service_labels=image_labels,
        compose_spec=compose_spec,
    )
    logging.info("labels_for_involved_services=%s", labels_for_involved_services)

    target_container = _get_value_from_label(
        image_labels, "simcore.service.target-container"
    )

    # merge the settings from the all the involved services
    settings: Deque[Dict[str, Any]] = deque()
    for compose_spec_key, service_labels in labels_for_involved_services.items():
        service_settings: List[Dict[str, Any]] = json.loads(
            service_labels["simcore.service.settings"]
        )
        settings.extend(
            # inject compose spec key, used to target container specific services
            _add_compose_destination_container_to_settings_entries(
                settings=service_settings, destination_container=compose_spec_key
            )
        )

    settings = _merge_resources_in_settings(settings)
    settings = _inject_target_service_into_env_vars(settings)
    # destination_container is no longer required, removing
    settings = _strip_compose_destination_container_from_settings_entries(settings)

    # calls into director-v2 to start
    proxy_service_create_results = await start_service_sidecar_stack(
        app=app,
        user_id=user_id,
        project_id=project_id,
        service_key=service["key"],
        service_tag=service["tag"],
        node_uuid=node_uuid,
        settings=list(settings),
        paths_mapping=paths_mapping,
        compose_spec=compose_spec,
        target_container=target_container,
        request_scheme=request_scheme,
        request_dns=request_dns,
    )

    return await _get_node_details(
        app=app, client=client, service=proxy_service_create_results
    )


async def _create_node(
    app: web.Application,
    client: aiodocker.docker.Docker,
    user_id: str,
    project_id: str,
    list_of_services: List[Dict],
    node_uuid: str,
    node_base_path: str,
    request_scheme: str,
    request_dns: str,
    boot_as_service_sidecar: bool,
) -> List[Dict]:  # pylint: disable=R0913, R0915
    log.debug(
        "Creating %s docker services for node %s and base path %s for user %s",
        len(list_of_services),
        node_uuid,
        node_base_path,
        user_id,
    )
    log.debug("Services %s will be started", list_of_services)

    # if the service uses several docker images, a network needs to be setup to connect them together
    inter_docker_network_id = None
    if len(list_of_services) > 1 and not boot_as_service_sidecar:
        service_name = registry_proxy.get_service_first_name(list_of_services[0]["key"])
        inter_docker_network_id = await _create_overlay_network_in_swarm(
            client, service_name, node_uuid
        )
        log.debug("Created docker network in swarm for service %s", service_name)

    containers_meta_data = list()
    for service in list_of_services:
        log.debug("Service to start info %s", service)

        # The platform currently supports 2 boot modes, legacy(which will be deprecated in the future)
        # dynamic-sidecar. If inside the labels "simcore.service.boot-mode" is presend and is equal to
        # "service-sidecar", the dynamic sidecar will be used in place of the current system

        if boot_as_service_sidecar:
            service_meta_data = await _start_docker_service_with_dynamic_service(
                app=app,
                client=client,
                user_id=user_id,
                project_id=project_id,
                node_uuid=node_uuid,
                service=service,
                request_scheme=request_scheme,
                request_dns=request_dns,
            )
        else:
            service_meta_data = await _start_docker_service(
                app,
                client,
                user_id,
                project_id,
                service["key"],
                service["tag"],
                list_of_services.index(service) == 0,
                node_uuid,
                node_base_path,
                inter_docker_network_id,
            )

        log.debug(
            "Result of service start is_dynamic_sidecar=%s %s",
            boot_as_service_sidecar,
            service_meta_data,
        )
        containers_meta_data.append(service_meta_data)

    return containers_meta_data


async def _get_service_key_version_from_docker_service(
    service: Dict,
) -> Tuple[str, str]:
    service_full_name = str(service["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"])
    if not service_full_name.startswith(config.REGISTRY_PATH):
        raise exceptions.DirectorException(
            msg="Invalid service {}".format(service_full_name)
        )

    service_full_name = service_full_name[len(config.REGISTRY_PATH) :].strip("/")
    return service_full_name.split(":")[0], service_full_name.split(":")[1]


async def _get_service_basepath_from_docker_service(service: Dict) -> str:
    envs_list = service["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"]
    envs_dict = dict(x.split("=") for x in envs_list)
    return envs_dict["SIMCORE_NODE_BASEPATH"]


async def _boot_as_service_sidecar(
    app: web.Application, service_key: str, service_tag: str
) -> bool:
    image_labels = await registry_proxy.get_image_labels(
        app=app, image=service_key, tag=service_tag
    )

    return image_labels.get("simcore.service.boot-mode") == "service-sidecar"


async def start_service(
    app: web.Application,
    user_id: str,
    project_id: str,
    service_key: str,
    service_tag: str,
    node_uuid: str,
    node_base_path: str,
    request_dns: str,
    request_scheme: str,
) -> Dict:
    # pylint: disable=C0103
    log.debug(
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
        log.debug("Found service to start %s:%s", service_key, service_tag)
        list_of_services_to_start = [{"key": service_key, "tag": service_tag}]
        # find the service dependencies
        list_of_dependencies = await _get_dependant_repos(app, service_key, service_tag)
        log.debug("Found service dependencies: %s", list_of_dependencies)

        boot_as_service_sidecar = await _boot_as_service_sidecar(
            app=app, service_key=service_key, service_tag=service_tag
        )
        if list_of_dependencies and not boot_as_service_sidecar:
            list_of_services_to_start.extend(list_of_dependencies)

        containers_meta_data = await _create_node(
            app,
            client,
            user_id,
            project_id,
            list_of_services_to_start,
            node_uuid,
            node_base_path,
            request_scheme,
            request_dns,
            boot_as_service_sidecar,
        )
        node_details = containers_meta_data[0]
        if config.MONITORING_ENABLED:
            service_started(
                app,
                user_id,
                service_key,
                service_tag,
                "DYNAMIC",
            )
        # we return only the info of the main service
        return node_details


def format_node_details_for_frontend(**kwargs) -> Dict[str, Union[str, int]]:
    """this is used to format the node_details for either old
    or service-sidecar interactive services

    Usually 10 (old interactive service) or 11 (service-sidecar) fields are provided.
    When less the 10 fields are provided there is usually an error or something is still being formatted
    """

    def _format_service_state(
        input_service_state: Optional[Union[str, ServiceState]]
    ) -> str:
        if input_service_state is None:
            return ServiceState.PENDING.value
        return (
            input_service_state
            if isinstance(input_service_state, str)
            else input_service_state.value
        )

    node_status: Dict[str, Union[str, int]] = {}
    dynamic_type: Optional[str] = kwargs.get("dynamic_type", None)
    if dynamic_type is not None:
        # if this field is preset the service will be served via dynamic-sidecar
        node_status["dynamic_type"] = dynamic_type

    service_state: Optional[Union[str, ServiceState]] = kwargs.get(
        "service_state", None
    )

    if len(kwargs) < 10:
        # for the servie-sidecar sometimes the status is not availabe because:
        # API not responding, generic errors
        node_status["service_state"] = _format_service_state(service_state)
        node_status["service_message"] = kwargs.get("service_message", "")
        node_status["service_uuid"] = kwargs.get("service_uuid", "")
        return node_status

    node_status["published_port"] = kwargs["published_port"]
    node_status["entry_point"] = kwargs["entry_point"]
    node_status["service_uuid"] = kwargs["service_uuid"]
    node_status["service_key"] = kwargs["service_key"]
    node_status["service_version"] = kwargs["service_version"]
    node_status["service_host"] = kwargs["service_host"]
    node_status["service_port"] = kwargs["service_port"]
    node_status["service_basepath"] = kwargs["service_basepath"]
    node_status["service_state"] = _format_service_state(service_state)
    node_status["service_message"] = kwargs["service_message"]

    return node_status


async def _compute_dynamic_sidecar_node_details(
    app: web.Application, node_uuid: str
) -> Dict[str, Union[str, int]]:
    # pull all the details from the service-sidecar via an API call and pass it forward
    status_result = await get_service_sidecar_stack_status(app=app, node_uuid=node_uuid)
    if status_result is None:
        raise exceptions.DirectorException(
            f"Error while retriving status from service-sidecar for node {node_uuid}"
        )
    if (
        len(status_result) == 2
        and "service_state" in status_result
        and "service_message" in status_result
    ):
        return status_result
    return format_node_details_for_frontend(**status_result)


async def _get_node_details(
    app: web.Application, client: aiodocker.docker.Docker, service: Dict
) -> Dict:
    is_dynamic_sidecar = (
        service["Spec"]["Labels"].get("dynamic_type") == "dynamic-sidecar"
    )
    if is_dynamic_sidecar:
        return await _compute_dynamic_sidecar_node_details(
            app=app, node_uuid=service["Spec"]["Labels"]["uuid"]
        )

    # legacy node details computation
    service_key, service_tag = await _get_service_key_version_from_docker_service(
        service
    )

    # get boot parameters
    results = await asyncio.gather(
        _read_service_settings(
            app, service_key, service_tag, config.SERVICE_RUNTIME_BOOTSETTINGS
        ),
        _get_service_basepath_from_docker_service(service),
        _get_service_state(client, service),
    )

    service_boot_parameters_labels = results[0]
    service_entrypoint = _get_service_entrypoint(service_boot_parameters_labels)
    service_basepath = results[1]
    service_state, service_msg = results[2]
    service_name = service["Spec"]["Name"]
    service_uuid = service["Spec"]["Labels"]["uuid"]

    # get the published port
    published_port, target_port = await _get_docker_image_port_mapping(service)
    return format_node_details_for_frontend(
        published_port=published_port,
        entry_point=service_entrypoint,
        service_uuid=service_uuid,
        service_key=service_key,
        service_version=service_tag,
        service_host=service_name,
        service_port=target_port,
        service_basepath=service_basepath,
        service_state=service_state,
        service_message=service_msg,
    )


async def get_services_details(
    app: web.Application, user_id: Optional[str], study_id: Optional[str]
) -> List[Dict]:
    async with docker_utils.docker_client() as client:  # pylint: disable=not-async-context-manager
        try:
            filters = ["type=main", f"swarm_stack_name={config.SWARM_STACK_NAME}"]
            if user_id:
                filters.append("user_id=" + user_id)
            if study_id:
                filters.append("study_id=" + study_id)
            list_running_services = await client.services.list(
                filters={"label": filters}
            )
            services_details = [
                await _get_node_details(app, client, service)
                for service in list_running_services
            ]
            return services_details
        except aiodocker.exceptions.DockerError as err:
            log.exception(
                "Error while listing services with user_id, study_id %s, %s",
                user_id,
                study_id,
            )
            raise exceptions.GenericDockerError(
                "Error while accessing container", err
            ) from err


async def get_service_details(app: web.Application, node_uuid: str) -> Dict:
    async with docker_utils.docker_client() as client:  # pylint: disable=not-async-context-manager
        try:
            list_running_services_with_uuid = await client.services.list(
                filters={
                    "label": [
                        f"uuid={node_uuid}",
                        "type=main",
                        f"swarm_stack_name={config.SWARM_STACK_NAME}",
                    ]
                }
            )
            # error if no service with such an id exists
            if not list_running_services_with_uuid:
                raise exceptions.ServiceUUIDNotFoundError(node_uuid)

            if len(list_running_services_with_uuid) > 1:
                # someone did something fishy here
                raise exceptions.DirectorException(
                    msg="More than one docker service is labeled as main service"
                )

            node_details = await _get_node_details(
                app, client, list_running_services_with_uuid[0]
            )
            return node_details
        except aiodocker.exceptions.DockerError as err:
            log.exception("Error while accessing container with uuid: %s", node_uuid)
            raise exceptions.GenericDockerError(
                "Error while accessing container", err
            ) from err


@run_sequentially_in_context(target_args=["node_uuid"])
async def stop_service(app: web.Application, node_uuid: str) -> None:
    log.debug("stopping service with uuid %s", node_uuid)
    # get the docker client
    async with docker_utils.docker_client() as client:  # pylint: disable=not-async-context-manager
        try:
            list_running_services_with_uuid = await client.services.list(
                filters={
                    "label": [
                        f"uuid={node_uuid}",
                        f"swarm_stack_name={config.SWARM_STACK_NAME}",
                    ]
                }
            )
        except aiodocker.exceptions.DockerError as err:
            log.exception("Error while stopping container with uuid: %s", node_uuid)
            raise exceptions.GenericDockerError(
                "Error while stopping container", err
            ) from err

        # error if no service with such an id exists
        if not list_running_services_with_uuid:
            raise exceptions.ServiceUUIDNotFoundError(node_uuid)
        log.debug("found service(s) with uuid %s", list_running_services_with_uuid)
        # save the state of the main service if it can
        service_details = await get_service_details(app, node_uuid)

        if service_details.get("dynamic_type") == "dynamic-sidecar":
            # service-sidecar is exposed on port 8000 by default
            service_host_name = service_details["service_host"] + ":8000"
        else:
            # FIXME: the exception for the 3d-viewer shall be removed once the dy-sidecar comes in
            service_host_name = "{}:{}{}".format(
                service_details["service_host"],
                service_details["service_port"]
                if service_details["service_port"]
                else "80",
                service_details["service_basepath"]
                if not "3d-viewer" in service_details["service_host"]
                else "",
            )
        log.debug("saving state of service %s...", service_host_name)
        try:
            session = app[APP_CLIENT_SESSION_KEY]
            service_url = "http://" + service_host_name + "/" + "state"
            async with session.post(
                service_url,
                timeout=ServicesCommonSettings().director_dynamic_service_save_timeout,
            ) as response:
                if 199 < response.status < 300:
                    log.debug(
                        "service %s successfully saved its state", service_host_name
                    )
                else:
                    log.warning(
                        "service %s does not allow saving state, answered %s",
                        service_host_name,
                        await response.text(),
                    )
        except ClientConnectionError:
            log.warning(
                "service %s could not be contacted, state not saved", service_host_name
            )

        # remove the services
        try:
            log.debug("removing services...")
            for service in list_running_services_with_uuid:
                # calls into director-v2 to stop
                await stop_service_sidecar_stack(app=app, node_uuid=node_uuid)
                await client.services.delete(service["Spec"]["Name"])
            log.debug("removed services, now removing network...")
        except aiodocker.exceptions.DockerError as err:
            raise exceptions.GenericDockerError(
                "Error while removing services", err
            ) from err
        # remove network(s)
        await _remove_overlay_network_of_swarm(client, node_uuid)
        log.debug("removed network")

        if config.MONITORING_ENABLED:
            service_stopped(
                app,
                "undefined_user",
                service_details["service_key"],
                service_details["service_version"],
                "DYNAMIC",
                "SUCCESS",
            )
