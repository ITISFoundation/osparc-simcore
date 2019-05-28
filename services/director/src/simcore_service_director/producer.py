# pylint: disable=C0111, R0913

import asyncio
import json
import logging
from typing import Dict, List, Tuple

import aiodocker
import aiohttp
import tenacity
from asyncio_extras import async_contextmanager

from . import config, exceptions, registry_proxy
from .system_utils import get_system_extra_hosts_raw

SERVICE_RUNTIME_SETTINGS = 'simcore.service.settings'
SERVICE_RUNTIME_BOOTSETTINGS = 'simcore.service.bootsettings'

log = logging.getLogger(__name__)


@async_contextmanager
async def _docker_client() -> aiodocker.docker.Docker:
    try:
        client = aiodocker.Docker()
        yield client
    except aiodocker.exceptions.DockerError:
        log.exception(msg="Unexpected error with docker client")
        raise
    finally:
        await client.close()


async def _create_auth() -> Dict:
    return {
        "username": config.REGISTRY_USER,
        "password": config.REGISTRY_PW
    }

async def _check_node_uuid_available(client: aiodocker.docker.Docker, node_uuid: str):
    log.debug("Checked if UUID %s is already in use", node_uuid)
    # check if service with same uuid already exists
    try:
        list_of_running_services_w_uuid = await client.services.list(
            filters={'label': 'uuid=' + node_uuid})
    except aiodocker.exceptions.DockerError as err:
        log.exception("Error while retrieving services list")
        raise exceptions.GenericDockerError(
            "Error while retrieving services", err) from err
    if list_of_running_services_w_uuid:
        raise exceptions.ServiceUUIDInUseError(node_uuid)
    log.debug("UUID %s is free", node_uuid)


async def _check_setting_correctness(setting: Dict):
    if 'name' not in setting or 'type' not in setting or 'value' not in setting:
        raise exceptions.DirectorException("Invalid setting in %s" % setting)


async def _read_service_settings(key: str, tag: str) -> Dict:
    # pylint: disable=C0103
    image_labels = await registry_proxy.retrieve_labels_of_image(key, tag)
    runtime_parameters = json.loads(image_labels[SERVICE_RUNTIME_SETTINGS]) if SERVICE_RUNTIME_SETTINGS in image_labels else {}
    log.debug("Retrieved service runtime settings: %s", runtime_parameters)
    return runtime_parameters


async def _get_service_boot_parameters_labels(key: str, tag: str) -> Dict:
    # pylint: disable=C0103
    image_labels = await registry_proxy.retrieve_labels_of_image(key, tag)
    boot_params = json.loads(image_labels[SERVICE_RUNTIME_BOOTSETTINGS]) if SERVICE_RUNTIME_BOOTSETTINGS in image_labels else {}
    log.debug("Retrieved service boot settings: %s", boot_params)
    return boot_params


# pylint: disable=too-many-branches
async def _create_docker_service_params(client: aiodocker.docker.Docker,
                                        service_key: str,
                                        service_tag: str,
                                        main_service: bool,
                                        user_id: str,
                                        node_uuid: str,
                                        project_id: str,
                                        node_base_path: str,
                                        internal_network_id: str) -> Dict:

    service_parameters_labels = await _read_service_settings(service_key, service_tag)

    log.debug("Converting labels to docker runtime parameters")
    container_spec = {
        "Image": "{}/{}:{}".format(config.REGISTRY_URL, service_key, service_tag),
        "Env": {
            **config.SERVICES_DEFAULT_ENVS,
            "SIMCORE_USER_ID": user_id,
            "SIMCORE_NODE_UUID": node_uuid,
            "SIMCORE_PROJECT_ID": project_id,
            "SIMCORE_NODE_BASEPATH": node_base_path or ""
        },
        "Hosts": get_system_extra_hosts_raw(config.EXTRA_HOSTS_SUFFIX)
    }
    docker_params = {
        "auth": await _create_auth() if config.REGISTRY_AUTH else {},
        "registry": config.REGISTRY_URL if config.REGISTRY_AUTH else "",
        "name": registry_proxy.get_service_last_names(service_key) + "_" + node_uuid,
        "task_template": {
            "ContainerSpec": container_spec,
            "Placement": {
                "Constraints": []
            },
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": 5000000,
                "MaxAttempts": 2
            },
            "Resources": {
                "Limits": {
                    "NanoCPUs": 4 * pow(10, 9),
                    "MemoryBytes": 16 * pow(1024, 3)
                },
                "Reservation": {
                    "NanoCPUs": 0,
                    "MemoryBytes": 0
                }
            }
        },
        "endpoint_spec": {},
        "labels": {
            "uuid": node_uuid,
            "type": "main" if main_service else "dependency"
        },
        "networks": [internal_network_id] if internal_network_id else []
    }
    for param in service_parameters_labels:
        await _check_setting_correctness(param)
        # replace %service_uuid% by the given uuid
        if str(param['value']).find("%service_uuid%") != -1:
            dummy_string = json.dumps(param['value'])
            dummy_string = dummy_string.replace("%service_uuid%", node_uuid)
            param['value'] = json.loads(dummy_string)

        if param["type"] == "Resources":
            # python-API compatible for backward compatibility
            if "mem_limit" in param["value"]:
                docker_params["task_template"]["Resources"]["Limits"]["MemoryBytes"] = param["value"]["mem_limit"]
            if "cpu_limit" in param["value"]:
                docker_params["task_template"]["Resources"]["Limits"]["NanoCPUs"] = param["value"]["cpu_limit"]
            if "mem_reservation" in param["value"]:
                docker_params["task_template"]["Resources"]["Reservation"]["MemoryBytes"] = param["value"]["mem_reservation"]
            if "cpu_reservation" in param["value"]:
                docker_params["task_template"]["Resources"]["Reservation"]["NanoCPUs"] = param["value"]["cpu_reservation"]
            # REST-API compatible
            if "Limits" in param["value"] or "Reservation" in param["value"]:
                docker_params["task_template"]["Resources"] = param["value"]

        elif param["name"] == "ports" and param["type"] == "int": # backward comp
            # special handling for we need to open a port with 0:XXX this tells the docker engine to allocate whatever free port
            docker_params["endpoint_spec"] = {
                "Ports": [
                    {
                        "TargetPort": int(param["value"]),
                        "PublishedPort": 0
                    }
                ]
            }
        elif param["type"] == "EndpointSpec": # REST-API compatible
            docker_params["endpoint_spec"] = param["value"]
        elif param["name"] == "constraints": # python-API compatible
            docker_params["task_template"]["Placement"]["Constraints"] = param["value"]
        elif param["type"] == "Constraints": # REST-API compatible
            docker_params["task_template"]["Placement"]["Constraints"] = param["value"]

    # the service may be part of the swarm network
    if "Ports" in docker_params["endpoint_spec"]:
        try:
            swarm_network_id = (await _get_swarm_network(client))["Id"]
            docker_params["networks"].append(swarm_network_id)
        except exceptions.DirectorException:
            log.exception("Could not find swarm network")

    log.debug("Converted labels to docker runtime parameters: %s", docker_params)
    return docker_params


async def _get_service_entrypoint(service_boot_parameters_labels: Dict) -> str:
    log.debug("Getting service entrypoint")
    for param in service_boot_parameters_labels:
        await _check_setting_correctness(param)
        if param['name'] == 'entry_point':
            log.debug("Service entrypoint is %s", param['value'])
            return param['value']
    return ''

async def _get_swarm_network(client: aiodocker.docker.Docker) -> Dict:
    network_name = "_default"
    if config.SWARM_STACK_NAME:
        network_name = config.SWARM_STACK_NAME
    # try to find the network name (usually named STACKNAME_default)
    networks = [x for x in (await client.networks.list()) if "swarm" in x["Scope"] and network_name in x["Name"]]
    if not networks or len(networks) > 1:
        raise exceptions.DirectorException(
            msg="Swarm network name is not configured, found following networks: {}".format(networks))
    return networks[0]

async def _get_docker_image_port_mapping(service: Dict) -> Tuple[str, str]:
    log.debug("getting port published by service: %s", service)

    published_ports = list()
    target_ports = list()
    if 'Endpoint' in service:
        service_endpoints = service['Endpoint']
        if 'Ports' in service_endpoints:
            ports_info_json = service_endpoints['Ports']
            for port in ports_info_json:
                published_ports.append(port['PublishedPort'])
                target_ports.append(port["TargetPort"])
    log.debug("Service %s publishes: %s ports", service["ID"], published_ports)
    published_port = None
    target_port = None
    if published_ports:
        published_port = published_ports[0]
    if target_ports:
        target_port = target_ports[0]
    return published_port, target_port


@tenacity.retry(wait=tenacity.wait_fixed(2),
                stop=tenacity.stop_after_attempt(3) or tenacity.stop_after_delay(10))
async def _pass_port_to_service(service_name: str,
                                port: str,
                                service_boot_parameters_labels: Dict):
    for param in service_boot_parameters_labels:
        await _check_setting_correctness(param)
        if param['name'] == 'published_host':
            # time.sleep(5)
            route = param['value']
            log.debug("Service needs to get published host %s:%s using route %s",
                      config.PUBLISHED_HOST_NAME, port, route)
            service_url = "http://" + service_name + "/" + route
            query_string = {"hostname": str(
                config.PUBLISHED_HOST_NAME), "port": str(port)}
            log.debug("creating request %s and query %s",
                      service_url, query_string)
            async with aiohttp.ClientSession() as session:
                async with session.post(service_url, data=query_string) as response:
                    log.debug("query response: %s", await response.text())
            return
    log.debug("service %s does not need to know its external port", service_name)


async def _create_network_name(service_name: str, node_uuid: str) -> str:
    return service_name + '_' + node_uuid


async def _create_overlay_network_in_swarm(client: aiodocker.docker.Docker,
                                           service_name: str,
                                           node_uuid: str) -> str:
    log.debug("Creating overlay network for service %s with uuid %s", service_name, node_uuid)
    network_name = await _create_network_name(service_name, node_uuid)
    try:
        network_config = {
            "Name": network_name,
            "Driver": "overlay",
            "Labels": {
                "uuid": node_uuid
            }
        }
        docker_network = await client.networks.create(network_config)
        log.debug("Network %s created for service %s with uuid %s", network_name, service_name, node_uuid)
        return docker_network.id
    except aiodocker.exceptions.DockerError as err:
        log.exception(
            "Error while creating network for service %s", service_name)
        raise exceptions.GenericDockerError(
            "Error while creating network", err) from err


async def _remove_overlay_network_of_swarm(client: aiodocker.docker.Docker, node_uuid: str):
    log.debug("Removing overlay network for service with uuid %s", node_uuid)
    try:
        networks = await client.networks.list()
        networks = [x for x in (await client.networks.list()) if x["Labels"] and "uuid" in x["Labels"] and x["Labels"]["uuid"] == node_uuid]
        log.debug("Found %s networks with uuid %s", len(networks), node_uuid)
        # remove any network in the list (should be only one)
        for network in networks:
            docker_network = aiodocker.networks.DockerNetwork(client, network["Id"])
            await docker_network.delete()
        log.debug("Removed %s networks with uuid %s", len(networks), node_uuid)
    except aiodocker.exceptions.DockerError as err:
        log.exception(
            "Error while removing networks for service with uuid: %s", node_uuid)
        raise exceptions.GenericDockerError(
            "Error while removing networks", err) from err


async def _wait_until_service_running_or_failed(client: aiodocker.docker.Docker, service: Dict, node_uuid: str):
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
                log.error("Error while waiting for service with %s", last_task["Status"])
                raise exceptions.ServiceStartTimeoutError(service_name, node_uuid)
            if task_state in ("running", "complete"):
                break
        # allows dealing with other events instead of wasting time here
        await asyncio.sleep(1)  # 1s
    log.debug("Waited for service %s to start", service_name)


async def _get_repos_from_key(service_key: str) -> List[Dict]:
    # get the available image for the main service (syntax is image:tag)
    list_of_images = {
        service_key: await registry_proxy.retrieve_list_of_image_tags(service_key)
    }
    log.debug("entries %s", list_of_images)
    if not list_of_images[service_key]:
        raise exceptions.ServiceNotAvailableError(service_key)

    log.debug("Service %s has the following list of images available: %s",
              service_key, list_of_images)

    return list_of_images


async def _get_dependant_repos(service_key: str, service_tag: str) -> Dict:
    list_of_images = await _get_repos_from_key(service_key)
    tag = await _find_service_tag(list_of_images, service_key, service_tag)
    # look for dependencies
    dependent_repositories = await registry_proxy.list_interactive_service_dependencies(service_key, tag)
    return dependent_repositories


async def _find_service_tag(list_of_images: Dict, service_key: str, service_tag: str) -> str:
    available_tags_list = sorted(list_of_images[service_key])
    # not tags available... probably an undefined service there...
    if not available_tags_list:
        raise exceptions.ServiceNotAvailableError(service_key, service_tag)
    tag = service_tag
    if not service_tag or service_tag == 'latest':
        # get latest tag
        tag = available_tags_list[len(available_tags_list)-1]
    elif available_tags_list.count(service_tag) != 1:
        raise exceptions.ServiceNotAvailableError(
            service_name=service_key, service_tag=service_tag)

    log.debug("Service tag found is %s ", service_tag)
    return tag

async def _start_docker_service(client: aiodocker.docker.Docker,
                                user_id: str,
                                project_id: str,
                                service_key: str,
                                service_tag: str,
                                main_service: bool,
                                node_uuid: str,
                                node_base_path: str,
                                internal_network_id: str
                                ) -> Dict:  # pylint: disable=R0913
    service_parameters = await _create_docker_service_params(client, service_key, service_tag, main_service,
                                                                user_id, node_uuid, project_id, node_base_path, internal_network_id)
    log.debug("Starting docker service %s:%s using parameters %s", service_key, service_tag, service_parameters)
    # lets start the service
    try:
        service = await client.services.create(**service_parameters)
        if "ID" not in service:
            # error while starting service
            raise exceptions.DirectorException("Error while starting service: {}".format(str(service)))
        log.debug("Service started now waiting for it to run")

        # get the full info from docker
        service = await client.services.inspect(service["ID"])
        service_name = service["Spec"]["Name"]
        # wait for service to start
        await _wait_until_service_running_or_failed(client, service, node_uuid)
        log.debug("Service %s successfully started", service_name)
        # the docker swarm maybe opened some random port to access the service, get the latest version of the service
        service = await client.services.inspect(service["ID"])
        published_port, target_port = await _get_docker_image_port_mapping(service)
        # now pass boot parameters
        service_boot_parameters_labels = await _get_service_boot_parameters_labels(service_key, service_tag)
        service_entrypoint = await _get_service_entrypoint(service_boot_parameters_labels)
        if published_port:
            await _pass_port_to_service(service_name, published_port, service_boot_parameters_labels)

        container_meta_data = {
            "published_port": published_port,
            "entry_point": service_entrypoint,
            "service_uuid": node_uuid,
            "service_key": service_key,
            "service_version": service_tag,
            "service_host": service_name,
            "service_port": target_port,
            "service_basepath": node_base_path
        }
        return container_meta_data

    except exceptions.ServiceStartTimeoutError as err:
        log.exception("Service failed to start")
        await _silent_service_cleanup(node_uuid)
        raise
    except aiodocker.exceptions.DockerError as err:
        log.exception("Unexpected error")
        await _silent_service_cleanup(node_uuid)
        raise exceptions.ServiceNotAvailableError(
            service_key, service_tag) from err


async def _silent_service_cleanup(node_uuid):
    try:
        await stop_service(node_uuid)
    except exceptions.DirectorException:
        pass


async def _create_node(client: aiodocker.docker.Docker,
                        user_id: str,
                        project_id: str,
                        list_of_services: List[Dict],
                        node_uuid: str,
                        node_base_path: str
                        ) -> List[Dict]:  # pylint: disable=R0913, R0915
    log.debug("Creating %s docker services for node %s and base path %s for user %s",
        len(list_of_services), node_uuid, node_base_path, user_id)
    log.debug("Services %s will be started", list_of_services)

    # if the service uses several docker images, a network needs to be setup to connect them together
    inter_docker_network_id = None
    if len(list_of_services) > 1:
        service_name = registry_proxy.get_service_first_name(list_of_services[0]["key"])
        inter_docker_network_id = await _create_overlay_network_in_swarm(client, service_name, node_uuid)
        log.debug("Created docker network in swarm for service %s", service_name)

    containers_meta_data = list()
    for service in list_of_services:
        service_meta_data = await _start_docker_service(client, user_id,
                                                        project_id,
                                                        service["key"],
                                                        service["tag"],
                                                        list_of_services.index(
                                                            service) == 0,
                                                        node_uuid,
                                                        node_base_path,
                                                        inter_docker_network_id)
        containers_meta_data.append(service_meta_data)

    return containers_meta_data


async def start_service(user_id: str, project_id: str, service_key: str, service_tag: str, node_uuid: str, node_base_path: str) -> Dict:
    # pylint: disable=C0103
    log.debug("starting service %s:%s using uuid %s, basepath %s",
              service_key, service_tag, node_uuid, node_base_path)
    # first check the uuid is available
    async with _docker_client() as client: # pylint: disable=not-async-context-manager
        await _check_node_uuid_available(client, node_uuid)
        list_of_images = await _get_repos_from_key(service_key)
        service_tag = await _find_service_tag(list_of_images, service_key, service_tag)
        log.debug("Found service to start %s:%s", service_key, service_tag)
        list_of_services_to_start = [{"key": service_key, "tag": service_tag}]
        # find the service dependencies
        list_of_dependencies = await _get_dependant_repos(service_key, service_tag)
        log.debug("Found service dependencies: %s", list_of_dependencies)
        if list_of_dependencies:
            list_of_services_to_start.extend(list_of_dependencies)

        containers_meta_data = await _create_node(client, user_id, project_id,
                                                   list_of_services_to_start,
                                                   node_uuid, node_base_path)
        node_details = containers_meta_data[0]
        # we return only the info of the main service
        return node_details


async def _get_service_key_version_from_docker_service(service: Dict) -> Tuple[str, str]:
    # docker_image = config.REGISTRY_URL + '/' + service_key + ':' + service_tag
    service_full_name = str(
        service["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"])
    if not service_full_name.startswith(config.REGISTRY_URL):
        raise exceptions.DirectorException(
            msg="Invalid service {}".format(service_full_name))

    service_full_name = service_full_name[len(config.REGISTRY_URL):].strip("/")
    return service_full_name.split(":")[0], service_full_name.split(":")[1]


async def _get_service_basepath_from_docker_service(service: Dict) -> str:
    envs_list = service["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"]
    envs_dict = {key: value for key, value in (
        x.split("=") for x in envs_list)}
    return envs_dict["SIMCORE_NODE_BASEPATH"]

async def get_service_details(node_uuid: str) -> Dict:
    async with _docker_client() as client:  # pylint: disable=not-async-context-manager
        try:
            list_running_services_with_uuid = await client.services.list(
                filters={'label': ['uuid=' + node_uuid, "type=main"]})
            # error if no service with such an id exists
            if not list_running_services_with_uuid:
                raise exceptions.ServiceUUIDNotFoundError(node_uuid)

            if len(list_running_services_with_uuid) > 1:
                # someone did something fishy here
                raise exceptions.DirectorException(msg="More than one docker service is labeled as main service")

            service = list_running_services_with_uuid[0]
            service_key, service_tag = await _get_service_key_version_from_docker_service(service)

            # get boot parameters
            service_boot_parameters_labels = await _get_service_boot_parameters_labels(service_key, service_tag)
            service_entrypoint = await _get_service_entrypoint(service_boot_parameters_labels)
            service_basepath = await _get_service_basepath_from_docker_service(service)
            service_name =  service["Spec"]["Name"]

            # get the published port
            published_port, target_port = await _get_docker_image_port_mapping(service)
            node_details = {
                "published_port": published_port,
                "entry_point": service_entrypoint,
                "service_uuid": node_uuid,
                "service_key": service_key,
                "service_version": service_tag,
                "service_host": service_name,
                "service_port": target_port,
                "service_basepath": service_basepath
            }
            return node_details
        except aiodocker.exceptions.DockerError as err:
            log.exception(
                "Error while accessing container with uuid: %s", node_uuid)
            raise exceptions.GenericDockerError(
                "Error while accessing container", err) from err


async def stop_service(node_uuid: str):
    # get the docker client
    async with _docker_client() as client: # pylint: disable=not-async-context-manager
        try:
            list_running_services_with_uuid = await client.services.list(
                filters={'label': 'uuid=' + node_uuid})
        except aiodocker.exceptions.DockerError as err:
            log.exception("Error while stopping container with uuid: %s", node_uuid)
            raise exceptions.GenericDockerError("Error while stopping container", err) from err

        # error if no service with such an id exists
        if not list_running_services_with_uuid:
            raise exceptions.ServiceUUIDNotFoundError(node_uuid)
        # remove the services
        try:
            for service in list_running_services_with_uuid:
                await client.services.delete(service["Spec"]["Name"])
        except aiodocker.exceptions.DockerError as err:
            raise exceptions.GenericDockerError("Error while removing services", err)
        # remove network(s)
        await _remove_overlay_network_of_swarm(client, node_uuid)
