# pylint: disable=C0111, R0913

import asyncio
import json
import logging
from asyncio_extras import async_contextmanager
from typing import Dict, List, Tuple


import aiodocker
import aiohttp
import docker
import tenacity
from aiodocker.docker import Docker as DockerClient

from . import config, exceptions, registry_proxy
from .system_utils import get_system_extra_hosts_raw

SERVICE_RUNTIME_SETTINGS = 'simcore.service.settings'
SERVICE_RUNTIME_BOOTSETTINGS = 'simcore.service.bootsettings'

log = logging.getLogger(__name__)


@async_contextmanager
async def _docker_client() -> DockerClient:
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
        "username": config.REGISTRY_URL,
        "password": config.REGISTRY_PW,
        "email": "",
        "serveraddress": "{}/v2".format(config.REGISTRY_URL)
    }

async def _check_node_uuid_available(client: DockerClient, node_uuid: str):
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


async def _read_runtime_parameters(key: str, tag: str) -> Dict:
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


async def _convert_labels_to_docker_runtime_parameters(
        service_runtime_parameters_labels: Dict,
        node_uuid: str) -> Dict:
    # pylint: disable=C0103
    log.debug("Converting labels to docker runtime parameters")
    runtime_params = dict()
    for param in service_runtime_parameters_labels:
        await _check_setting_correctness(param)
        # index = str(param['value']).find("%node_uuid%")
        if str(param['value']).find("%service_uuid%") != -1:
            dummy_string = json.dumps(param['value'])
            dummy_string = dummy_string.replace("%service_uuid%", node_uuid)
            param['value'] = json.loads(dummy_string)

        # backward compatible till all dyn services are correctly updated
        if param["type"] != "string" and param["name"] != "ports":
            # this is a special docker API type
            arguments_dict = param["value"]
            runtime_params[param['name']] = getattr(
                docker.types, param["type"])(**arguments_dict)
        elif param['name'] == 'ports':
            # special handling for we need to open a port with 0:XXX this tells the docker engine to allocate whatever free port
            enpoint_spec = docker.types.EndpointSpec(
                ports={0: int(param['value'])})
            runtime_params["endpoint_spec"] = enpoint_spec
        else:
            runtime_params[param['name']] = param['value']
    log.debug("Converted labels to docker runtime parameters: %s", runtime_params)
    return runtime_params


async def _get_service_entrypoint(service_boot_parameters_labels: Dict) -> str:
    log.debug("Getting service entrypoint")
    for param in service_boot_parameters_labels:
        await _check_setting_correctness(param)
        if param['name'] == 'entry_point':
            log.debug("Service entrypoint is %s", param['value'])
            return param['value']
    return ''


async def _get_swarm_network(client: DockerClient) -> Dict:
    network_name = "_default"
    if config.SWARM_STACK_NAME:
        network_name = config.SWARM_STACK_NAME
    # try to find the network name (usually named STACKNAME_default)
    networks = [x for x in (await client.networks.list()) if network_name in x["Name"]]
    if not networks or len(networks) > 1:
        raise exceptions.DirectorException(
            msg="Swarm network name is not configured, found following networks: {}".format(networks))
    return networks[0]


async def _add_to_swarm_network_if_ports_published(client: DockerClient, docker_service_runtime_parameters: Dict):
    if "endpoint_spec" in docker_service_runtime_parameters:
        try:
            swarm_network = await _get_swarm_network(client)
            log.debug(
                "Adding swarm network with id: %s to docker runtime parameters", swarm_network["Name"])
            await _add_network_to_service_runtime_params(docker_service_runtime_parameters, swarm_network)
        except exceptions.DirectorException:
            log.exception("Could not find a swarm network, not in a swarm?")


async def _add_uuid_label_to_service_runtime_params(
        docker_service_runtime_parameters: Dict,
        node_uuid: str):
    # pylint: disable=C0103
    # add the service uuid to the docker service
    if "labels" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["labels"]["uuid"] = node_uuid
    else:
        docker_service_runtime_parameters["labels"] = {"uuid": node_uuid}
    log.debug("Added uuid label to docker runtime parameters: %s",
              docker_service_runtime_parameters["labels"])


async def _add_main_service_label_to_service_runtime_params(
        docker_service_runtime_parameters: Dict,
        main_service: bool):
    # pylint: disable=C0103
    # add the service uuid to the docker service
    service_type = "main" if main_service else "dependency"
    if "labels" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["labels"]["type"] = service_type
    else:
        docker_service_runtime_parameters["labels"] = {"type": service_type}
    log.debug("Added type label to docker runtime parameters: %s",
              docker_service_runtime_parameters["labels"])


async def _add_network_to_service_runtime_params(docker_service_runtime_parameters: Dict, docker_network: Dict):

    # pylint: disable=C0103
    if "networks" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["networks"].append(docker_network["Id"])
    else:
        docker_service_runtime_parameters["networks"] = [docker_network["Id"]]
    log.debug("Added network parameter to docker runtime parameters: %s",
              docker_service_runtime_parameters["networks"])


async def _add_env_variables_to_service_runtime_params(
        docker_service_runtime_parameters: Dict,
        user_id: str,
        project_id: str,
        node_uuid: str,
        node_base_path: str):

    service_env_variables = [
        "=".join([key, value]) for key, value in config.SERVICES_DEFAULT_ENVS.items()]
    # add specifics
    service_env_variables.append("=".join(["SIMCORE_USER_ID", user_id]))
    service_env_variables.append("=".join(["SIMCORE_NODE_UUID", node_uuid]))
    service_env_variables.append("=".join(["SIMCORE_PROJECT_ID", project_id]))
    service_env_variables.append(
        "=".join(["SIMCORE_NODE_BASEPATH", node_base_path or ""]))

    if "env" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["env"].extend(service_env_variables)
    else:
        docker_service_runtime_parameters["env"] = service_env_variables
    log.debug("Added env parameter to docker runtime parameters: %s",
              docker_service_runtime_parameters["env"])


async def _add_extra_hosts_to_service_runtime_params(docker_service_runtime_parameters: Dict):
    log.debug("Getting extra hosts with suffix: %s", config.EXTRA_HOSTS_SUFFIX)
    extra_hosts = get_system_extra_hosts_raw(config.EXTRA_HOSTS_SUFFIX)
    if "hosts" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["hosts"].update(extra_hosts)
    else:
        docker_service_runtime_parameters["hosts"] = extra_hosts


async def _set_service_name(docker_service_runtime_parameters: Dict,
                            service_name: str,
                            node_uuid: str):
    # pylint: disable=C0103
    docker_service_runtime_parameters["name"] = service_name + "_" + node_uuid
    log.debug("Added service name parameter to docker runtime parameters: %s",
              docker_service_runtime_parameters["name"])


async def _get_docker_image_port_mapping(client: DockerClient, service: Dict) -> Tuple[str, str]:
    log.debug("getting port published by service: %s", service)
    service_details = await client.services.inspect(service["ID"])

    published_ports = list()
    target_ports = list()
    if 'Endpoint' in service_details:
        service_endpoints = service_details['Endpoint']
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


async def _create_overlay_network_in_swarm(client: DockerClient,
                                           service_name: str,
                                           node_uuid: str) -> Dict:
    log.debug("Creating overlay network for service %s with uuid %s",
              service_name, node_uuid)
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
        return docker_network
    except docker.errors.APIError as err:
        log.exception(
            "Error while creating network for service %s", service_name)
        raise exceptions.GenericDockerError(
            "Error while creating network", err) from err


async def _remove_overlay_network_of_swarm(client: DockerClient, node_uuid: str):
    log.debug("Removing overlay network for service with uuid %s", node_uuid)
    try:
        networks = await client.networks.list()
        networks = [x for x in (await client.networks.list()) if x["Labels"] and "uuid" in x["Labels"] and x["Labels"]["uuid"] == node_uuid]
        log.debug("Found %s networks with uuid %s", len(networks), node_uuid)
        # remove any network in the list (should be only one)
        for network in networks:
            await network.delete()
        log.debug("Removed %s networks with uuid %s", len(networks), node_uuid)
    except docker.errors.APIError as err:
        log.exception(
            "Error while removing networks for service with uuid: %s", node_uuid)
        raise exceptions.GenericDockerError(
            "Error while removing networks", err) from err


async def _wait_until_service_running_or_failed(client: DockerClient,
                                                service_id: str,
                                                service_name: str,
                                                node_uuid: str):
    # pylint: disable=C0103
    log.debug("Waiting for service %s to start", service_id)
    # some times one has to wait until the task info is filled
    while True:
        service = await client.services.inspect(service_id)
        tasks = await client.tasks.list(filters={"desired-state": "running", "service": service["Spec"]["Name"]})
        all_tasks_running = True
        for task in tasks:
            task_state = task["Status"]["State"]
            # log.debug("%s %s", service_id, task_state)
            if task_state in ("failed", "rejected"):
                log.error("Error while waiting for service")
                raise exceptions.ServiceStartTimeoutError(
                    service_name, node_uuid)
            elif task_state != "running":
                all_tasks_running = False
                break
        if all_tasks_running:
            break
        # allows dealing with other events instead of wasting time here
        await asyncio.sleep(1)  # 1s
    log.debug("Waited for service %s to start", service_id)


async def _get_repos_from_key(service_key: str) -> List[Dict]:
    # get the available image for the main service (syntax is image:tag)
    list_of_images = {
        service_key: await registry_proxy.retrieve_list_of_images_in_repo(service_key)
    }
    log.debug("entries %s", list_of_images)
    if not list_of_images[service_key]:
        raise exceptions.ServiceNotAvailableError(service_key)

    log.debug("Service %s has the following list of images available: %s",
              service_key, list_of_images)

    return list_of_images


async def _get_dependant_repos(service_key: str, service_tag: str) -> Dict:
    list_of_images = await _get_repos_from_key(service_key)
    tag = await _find_service_tag(list_of_images, service_key,
                                  'Unkonwn name', service_tag)
    # look for dependencies
    dependent_repositories = await registry_proxy.list_interactive_service_dependencies(service_key, tag)
    return dependent_repositories


async def _find_service_tag(list_of_images: Dict,
                            service_key: str,
                            service_name: str,
                            service_tag: str) -> str:
    available_tags_list = sorted(list_of_images[service_key]['tags'])
    # not tags available... probably an undefined service there...
    if not available_tags_list:
        raise exceptions.ServiceNotAvailableError(service_name, service_tag)
    tag = service_tag
    if not service_tag or service_tag == 'latest':
        # get latest tag
        tag = available_tags_list[len(available_tags_list)-1]
    elif available_tags_list.count(service_tag) != 1:
        raise exceptions.ServiceNotAvailableError(
            service_name=service_name, service_tag=service_tag)

    log.debug("Service tag found is %s ", service_tag)
    return tag


async def _prepare_runtime_parameters(user_id: str,
                                      project_id: str,
                                      service_key: str,
                                      service_tag: str,
                                      main_service: bool,
                                      node_uuid: str,
                                      node_base_path: str,
                                      client: DockerClient
                                      ) -> Dict:
    service_runtime_parameters_labels = await _read_runtime_parameters(service_key, service_tag)
    docker_service_runtime_parameters = await _convert_labels_to_docker_runtime_parameters(service_runtime_parameters_labels, node_uuid)
    # add specific parameters
    await _add_to_swarm_network_if_ports_published(client, docker_service_runtime_parameters)
    await _add_uuid_label_to_service_runtime_params(docker_service_runtime_parameters, node_uuid)
    await _add_main_service_label_to_service_runtime_params(docker_service_runtime_parameters, main_service)
    await _add_env_variables_to_service_runtime_params(docker_service_runtime_parameters, user_id, project_id, node_uuid, node_base_path)
    await _add_extra_hosts_to_service_runtime_params(docker_service_runtime_parameters)
    await _set_service_name(docker_service_runtime_parameters,
                            registry_proxy.get_service_last_names(service_key),
                            node_uuid)
    return docker_service_runtime_parameters


async def _convert_to_rest_api_parameters(docker_image_full_path: str, docker_service_runtime_parameters: Dict) -> Tuple[Dict, Dict, Dict, str, Dict]:

    task_template = {
        "ContainerSpec": {
            "Image": docker_image_full_path,
            "Env": {env.split("=")[0]: env.split("=")[1] for env in docker_service_runtime_parameters["env"]} if "env" in docker_service_runtime_parameters else {},
            "Hosts": docker_service_runtime_parameters["hosts"] if "hosts" in docker_service_runtime_parameters else []
        },
        "Placement": {
            "Constraints": [x for x in docker_service_runtime_parameters["constraints"]] if "constraints" in docker_service_runtime_parameters else []
        },
    }

    endpoint_spec = {
        "Ports": docker_service_runtime_parameters["endpoint_spec"]["Ports"]
    }  if "endpoint_spec" in docker_service_runtime_parameters else {}

    labels = docker_service_runtime_parameters["labels"] if "labels" in docker_service_runtime_parameters else []
    name = docker_service_runtime_parameters["name"] if "name" in docker_service_runtime_parameters else None
    networks = docker_service_runtime_parameters["networks"] if "networks" in docker_service_runtime_parameters else []
    return task_template, endpoint_spec, labels, name, networks


async def _start_docker_service(client: DockerClient,
                                user_id: str,
                                project_id: str,
                                service_key: str,
                                service_tag: str,
                                main_service: bool,
                                node_uuid: str,
                                node_base_path: str,
                                internal_network: Dict
                                ) -> Dict:  # pylint: disable=R0913
    # prepare runtime parameters
    docker_service_runtime_parameters = await _prepare_runtime_parameters(user_id,
                                                                          project_id,
                                                                          service_key,
                                                                          service_tag,
                                                                          main_service,
                                                                          node_uuid,
                                                                          node_base_path,
                                                                          client)
    # if an inter docker network exists, then the service must be part of it
    if internal_network is not None:
        await _add_network_to_service_runtime_params(docker_service_runtime_parameters, internal_network)
    # prepare boot parameters
    service_boot_parameters_labels = await _get_service_boot_parameters_labels(service_key, service_tag)
    service_entrypoint = await _get_service_entrypoint(service_boot_parameters_labels)

    # lets start the service
    try:
        docker_image_full_path = "{}/{}:{}".format(config.REGISTRY_URL, service_key, service_tag)
        log.debug("Starting docker service %s using parameters %s", docker_image_full_path, docker_service_runtime_parameters)
        tast_template, endpoint_spec, labels, name, networks = await _convert_to_rest_api_parameters(docker_image_full_path, docker_service_runtime_parameters)

        service = await client.services.create(task_template=tast_template, name=name, labels=labels, endpoint_spec=endpoint_spec, networks=networks)

        log.debug("Service started now waiting for it to run")
        service_id = service["ID"]

        service = await client.services.inspect(service_id)
        service_name = await _get_service_name(service)
        await _wait_until_service_running_or_failed(client, service_id, docker_image_full_path, node_uuid)
        # the docker swarm opened some random port to access the service
        published_port, target_port = await _get_docker_image_port_mapping(client, service)
        log.debug("Service successfully started on %s:%s", service_entrypoint, published_port)
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
        if published_port:
            await _pass_port_to_service(service_name, published_port, service_boot_parameters_labels)
        return container_meta_data

    except exceptions.ServiceStartTimeoutError as err:
        log.exception("Service failed to start")
        await _silent_service_cleanup(node_uuid)
        raise
    except docker.errors.ImageNotFound as err:
        log.exception("The docker image was not found")
        await _silent_service_cleanup(node_uuid)
        raise exceptions.ServiceNotAvailableError(
            service_key, service_tag) from err
    except docker.errors.APIError as err:
        log.exception("Error while accessing the server")
        # await _silent_service_cleanup(node_uuid)
        raise exceptions.GenericDockerError(
            "Error while creating service", err) from err


async def _silent_service_cleanup(node_uuid):
    try:
        await stop_service(node_uuid)
    except exceptions.DirectorException:
        pass


async def _create_node(client: DockerClient,
                        user_id: str,
                        project_id: str,
                        list_of_services: List[Dict],
                        service_name: str,
                        node_uuid: str,
                        node_base_path: str
                        ) -> List[Dict]:  # pylint: disable=R0913, R0915
    log.debug("Creating %s docker services for node %s using uuid %s and base path %s for user %s", len(
        list_of_services), service_name, node_uuid, node_base_path, user_id)
    log.debug("Services %s will be started", list_of_services)

    # if the service uses several docker images, a network needs to be setup to connect them together
    inter_docker_network = None
    if len(list_of_services) > 1:
        inter_docker_network = await _create_overlay_network_in_swarm(
            client, service_name, node_uuid)
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
                                                        inter_docker_network)
        containers_meta_data.append(service_meta_data)

    return containers_meta_data


async def start_service(user_id: str, project_id: str, service_key: str, service_tag: str, node_uuid: str, node_base_path: str) -> Dict:
    # pylint: disable=C0103
    log.debug("starting service %s:%s using uuid %s, basepath %s",
              service_key, service_tag, node_uuid, node_base_path)
    # first check the uuid is available
    async with _docker_client() as client:
        await _check_node_uuid_available(client, node_uuid)

        service_name = registry_proxy.get_service_first_name(service_key)
        list_of_images = await _get_repos_from_key(service_key)
        service_tag = await _find_service_tag(list_of_images, service_key, service_name, service_tag)
        log.debug("Found service to start %s:%s", service_key, service_tag)
        list_of_services_to_start = [{"key": service_key, "tag": service_tag}]
        # find the service dependencies
        list_of_dependencies = await _get_dependant_repos(service_key, service_tag)
        log.debug("Found service dependencies: %s", list_of_dependencies)
        if list_of_dependencies:
            list_of_services_to_start.extend(list_of_dependencies)

        # create services
        # _login_docker_registry(client)

        containers_meta_data = await _create_node(client, user_id, project_id,
                                                   list_of_services_to_start,
                                                   service_name, node_uuid, node_base_path)
        node_details = containers_meta_data[0]
        # we return only the info of the main service
        return node_details


async def _get_service_key_version_from_docker_service(service: Dict) -> Tuple[str, str]:
    # docker_image_full_path = config.REGISTRY_URL + '/' + service_key + ':' + service_tag
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


async def _get_service_name(service: Dict) -> str:
    return service["Spec"]["Name"]


async def get_service_details(node_uuid: str) -> Dict:
    # get the docker client
    async with _docker_client() as client:
        # _login_docker_registry(client)
        try:
            list_running_services_with_uuid = await client.services.list(
                filters={'label': ['uuid=' + node_uuid, "type=main"]})
            # error if no service with such an id exists
            if not list_running_services_with_uuid:
                raise exceptions.ServiceUUIDNotFoundError(node_uuid)

            if len(list_running_services_with_uuid) > 1:
                # someone did something fishy here
                raise exceptions.DirectorException(
                    msg="More than one docker service is labeled as main service")

            service = list_running_services_with_uuid[0]
            service_key, service_tag = await _get_service_key_version_from_docker_service(service)

            # get boot parameters to get the entrypoint
            service_boot_parameters_labels = await _get_service_boot_parameters_labels(service_key, service_tag)
            service_entrypoint = await _get_service_entrypoint(service_boot_parameters_labels)

            service_basepath = await _get_service_basepath_from_docker_service(service)
            service_name = await _get_service_name(service)

            # get the published port
            published_port, target_port = await _get_docker_image_port_mapping(client, service)
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
        except docker.errors.APIError as err:
            log.exception(
                "Error while accessing container with uuid: %s", node_uuid)
            raise exceptions.GenericDockerError(
                "Error while accessing container", err) from err


async def stop_service(node_uuid: str):
    # get the docker client
    async with _docker_client() as client:
        # _login_docker_registry(client)

        try:
            list_running_services_with_uuid = await client.services.list(
                filters={'label': 'uuid=' + node_uuid})
        except docker.errors.APIError as err:
            log.exception(
                "Error while stopping container with uuid: %s", node_uuid)
            raise exceptions.GenericDockerError(
                "Error while stopping container", err) from err

        # error if no service with such an id exists
        if not list_running_services_with_uuid:
            raise exceptions.ServiceUUIDNotFoundError(node_uuid)
        # remove the services
        try:
            for service in list_running_services_with_uuid:
                await client.services.delete(await _get_service_name(service))
        except docker.errors.APIError as err:
            raise exceptions.GenericDockerError(
                "Error while removing services", err)
        # remove network(s)
        await _remove_overlay_network_of_swarm(client, node_uuid)
