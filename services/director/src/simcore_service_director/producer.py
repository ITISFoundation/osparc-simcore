# pylint: disable=C0111

import asyncio
import json
import logging
from typing import Dict, List

import aiohttp
import docker
import tenacity

from . import config, exceptions, registry_proxy

SERVICE_RUNTIME_SETTINGS = 'simcore.service.settings'
SERVICE_RUNTIME_BOOTSETTINGS = 'simcore.service.bootsettings'

log = logging.getLogger(__name__)

def __get_docker_client() -> docker.client:
    log.debug("Initiializing docker client")
    return  docker.from_env()

def __login_docker_registry(client: docker.client):
    try:
        # login
        registry_url = config.REGISTRY_URL
        username = config.REGISTRY_USER
        password = config.REGISTRY_PW
        log.debug("logging into docker registry %s", registry_url)
        client.login(registry=registry_url + '/v2',
                            username=username, password=password)
        log.debug("logged into docker registry %s", registry_url)
    except docker.errors.APIError as err:
        log.exception("Error while loggin into the registry")
        raise exceptions.RegistryConnectionError("Error while logging to docker registry", err) from err

def __check_node_uuid_available(client: docker.client, node_uuid: str):
    log.debug("Checked if UUID %s is already in use", node_uuid)
    # check if service with same uuid already exists
    try:
        list_of_running_services_w_uuid = client.services.list(
            filters={'label': 'uuid=' + node_uuid})
    except docker.errors.APIError as err:
        log.exception("Error while retrieving services list")
        raise exceptions.GenericDockerError("Error while retrieving services", err) from err
    if list_of_running_services_w_uuid:
        raise exceptions.ServiceUUIDInUseError(node_uuid)
    log.debug("UUID %s is free", node_uuid)

def __check_setting_correctness(setting: Dict):
    if 'name' not in setting or 'type' not in setting or 'value' not in setting:
        raise exceptions.DirectorException("Invalid setting in %s" % setting)

async def __get_service_runtime_parameters_labels(image: docker.models.images.Image, tag: str) -> Dict:
    # pylint: disable=C0103
    image_labels = await registry_proxy.retrieve_labels_of_image(image, tag)
    runtime_parameters = dict()
    if SERVICE_RUNTIME_SETTINGS in image_labels:
        runtime_parameters = json.loads(image_labels[SERVICE_RUNTIME_SETTINGS])
    log.debug("Retrieved service runtime settings: %s", runtime_parameters)
    return runtime_parameters

async def __get_service_boot_parameters_labels(image: docker.models.images.Image, tag: str) -> Dict:
    # pylint: disable=C0103
    image_labels = await registry_proxy.retrieve_labels_of_image(image, tag)
    boot_params = dict()
    if SERVICE_RUNTIME_BOOTSETTINGS in image_labels:
        boot_params = json.loads(image_labels[SERVICE_RUNTIME_BOOTSETTINGS])
    log.debug("Retrieved service boot settings: %s", boot_params)
    return boot_params


def __convert_labels_to_docker_runtime_parameters(service_runtime_parameters_labels: Dict, node_uuid: str) -> Dict:
    # pylint: disable=C0103
    log.debug("Converting labels to docker runtime parameters")
    runtime_params = dict()
    for param in service_runtime_parameters_labels:
        __check_setting_correctness(param)
        # index = str(param['value']).find("%node_uuid%")
        if str(param['value']).find("%node_uuid%") != -1:
            dummy_string = json.dumps(param['value'])
            dummy_string = dummy_string.replace("%node_uuid%", node_uuid)
            param['value'] = json.loads(dummy_string)
            # replace string by actual value
            #param['value'] = str(param['value']).replace("%node_uuid%", node_uuid)

        if param['name'] == 'ports':
            # special handling for we need to open a port with 0:XXX this tells the docker engine to allocate whatever free port
            enpoint_spec = docker.types.EndpointSpec(ports={0: int(param['value'])})
            runtime_params["endpoint_spec"] = enpoint_spec
        else:
            runtime_params[param['name']] = param['value']
    log.debug("Converted labels to docker runtime parameters: %s", runtime_params)
    return runtime_params

def __get_service_entrypoint(service_boot_parameters_labels: Dict) -> str:
    log.debug("Getting service entrypoint")
    for param in service_boot_parameters_labels:
        __check_setting_correctness(param)
        if param['name'] == 'entry_point':
            log.debug("Service entrypoint is %s", param['value'])
            return param['value']
    return ''

def __add_to_swarm_network_if_ports_published(client: docker.client, docker_service_runtime_parameters: Dict):
    # TODO: SAN this is a brain killer... change services to something better...
    if "endpoint_spec" in docker_service_runtime_parameters:
        network_id = "services_default"
        log.debug("Adding swarm network with id: %s to docker runtime parameters", network_id)
        list_of_networks =  client.networks.list(names=[network_id])
        for network in list_of_networks:
            __add_network_to_service_runtime_params(docker_service_runtime_parameters, network)
        log.debug("Added swarm network %s to docker runtime parameters", network_id)

def __add_uuid_label_to_service_runtime_params(docker_service_runtime_parameters: Dict, node_uuid: str):
    # pylint: disable=C0103
    # add the service uuid to the docker service
    if "labels" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["labels"]["uuid"] = node_uuid
    else:
        docker_service_runtime_parameters["labels"] = {"uuid": node_uuid}
    log.debug("Added uuid label to docker runtime parameters: %s", docker_service_runtime_parameters["labels"])

def __add_network_to_service_runtime_params(docker_service_runtime_parameters: Dict, docker_network: docker.models.networks.Network):
    # pylint: disable=C0103
    if "networks" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["networks"].append(docker_network.id)
    else:
        docker_service_runtime_parameters["networks"] = [docker_network.id]
    log.debug("Added network parameter to docker runtime parameters: %s", docker_service_runtime_parameters["networks"])

def __add_env_variables_to_service_runtime_params(docker_service_runtime_parameters: Dict, user_id:str, node_uuid: str):

    service_env_variables = ["=".join([key, value]) for key,value in config.SERVICES_DEFAULT_ENVS.items()]
    # add specifics
    service_env_variables.append("=".join(["SIMCORE_USER_ID", user_id]))
    service_env_variables.append("=".join(["SIMCORE_NODE_UUID", node_uuid]))

    if "env" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["env"].extend(service_env_variables)
    else:
        docker_service_runtime_parameters["env"] = service_env_variables
    log.debug("Added env parameter to docker runtime parameters: %s", docker_service_runtime_parameters["env"])

def __set_service_name(docker_service_runtime_parameters: Dict, service_name: str, node_uuid: str):
    # pylint: disable=C0103
    docker_service_runtime_parameters["name"] = service_name + "_" + node_uuid
    log.debug("Added service name parameter to docker runtime parameters: %s", docker_service_runtime_parameters["name"])


def __get_docker_image_published_port(service_id: str) -> str:
    # pylint: disable=C0103
    low_level_client = docker.APIClient()
    service_infos_json = low_level_client.services(filters={'id': service_id})

    if len(service_infos_json) != 1:
        log.warning("Expected a single port per service, got %s", service_infos_json)

    published_ports = list()
    for service_info in service_infos_json:
        if 'Endpoint' in service_info:
            service_endpoints = service_info['Endpoint']
            if 'Ports' in service_endpoints:
                ports_info_json = service_info['Endpoint']['Ports']
                for port in ports_info_json:
                    published_ports.append(port['PublishedPort'])
    log.debug("Service %s publishes: %s ports", service_id, published_ports)
    published_port = None
    if published_ports:
        published_port = published_ports[0]
    return published_port

@tenacity.retry(wait=tenacity.wait_fixed(2), stop=tenacity.stop_after_attempt(3) or tenacity.stop_after_delay(10))
async def __pass_port_to_service(service: docker.models.services.Service, port: str, service_boot_parameters_labels: Dict):
    for param in service_boot_parameters_labels:
        __check_setting_correctness(param)
        if param['name'] == 'published_host':
            # time.sleep(5)
            route = param['value']
            log.debug("Service needs to get published host %s:%s using route %s", config.PUBLISHED_HOST_NAME, port, route)
            service_url = "http://" + str(service.name) + "/" + route            
            query_string = {"hostname":str(config.PUBLISHED_HOST_NAME), "port":str(port)}
            log.debug("creating request %s and query %s", service_url, query_string)
            async with aiohttp.ClientSession() as session:
                async with session.post(service_url, data=query_string) as response:                    
                    log.debug("query response: %s", await response.text())
            return
    log.debug("service %s does not need to know its external port", service.name)

def __create_network_name(service_name: str, node_uuid: str) -> str:
    return service_name + '_' + node_uuid

def __create_overlay_network_in_swarm(client: docker.client, service_name: str, node_uuid: str) -> docker.models.networks.Network:
    log.debug("Creating overlay network for service %s with uuid %s", service_name, node_uuid)
    network_name = __create_network_name(service_name, node_uuid)
    try:
        docker_network = client.networks.create(
            network_name, driver="overlay", scope="swarm", labels={"uuid": node_uuid})
        log.debug("Network %s created for service %s with uuid %s", network_name, service_name, node_uuid)
        return docker_network
    except docker.errors.APIError as err:
        log.exception("Error while creating network for service %s", service_name)
        raise exceptions.GenericDockerError("Error while creating network", err) from err

def __remove_overlay_network_of_swarm(client: docker.client, node_uuid: str):
    log.debug("Removing overlay network for service with uuid %s", node_uuid)
    try:
        networks = client.networks.list(
            filters={"label": "uuid=" + node_uuid})
        log.debug("Found %s networks with uuid %s", len(networks), node_uuid)
        # remove any network in the list (should be only one)
        for network in networks:
            network.remove()
        log.debug("Removed %s networks with uuid %s", len(networks), node_uuid)
    except docker.errors.APIError as err:
        log.exception("Error while removing networks for service with uuid: %s", node_uuid)
        raise exceptions.GenericDockerError("Error while removing networks", err) from err

async def __wait_until_service_running_or_failed(service_id: str, service_name: str, node_uuid: str):
    # pylint: disable=C0103
    log.debug("Waiting for service %s to start", service_id)
    client = docker.APIClient()

    # some times one has to wait until the task info is filled
    while True:
        task_infos_json = client.tasks(filters={'service': service_id})
        if task_infos_json:
            # check the status
            status_json = task_infos_json[0]["Status"]
            task_state = status_json["State"]

            log.debug("%s %s", service_id, task_state)
            if task_state == "running":
                break
            elif task_state in ("failed", "rejected"):
                log.error("Error while waiting for service")               
                raise exceptions.ServiceStartTimeoutError(service_name, node_uuid)
        # would allow dealing with other events instead of wasting time here
        await asyncio.sleep(0.005)  # 5ms
    log.debug("Waited for service %s to start", service_id)

async def __get_repos_from_key(service_key: str) -> List[Dict]:
    # get the available image for the main service (syntax is image:tag)
    list_of_images = {
        service_key: await registry_proxy.retrieve_list_of_images_in_repo(service_key)
    }
    log.info("entries %s", list_of_images)
    if not list_of_images[service_key]:
        raise exceptions.ServiceNotAvailableError(service_key)

    log.debug("Service %s has the following list of images available: %s", service_key, list_of_images)

    return list_of_images

async def __get_dependant_repos(service_key: str, service_tag: str) -> Dict:
    list_of_images = await __get_repos_from_key(service_key)
    tag = __find_service_tag(list_of_images, service_key, 'Unkonwn name', service_tag)
    # look for dependencies
    dependent_repositories = await registry_proxy.list_interactive_service_dependencies(service_key, tag)
    return dependent_repositories

def __find_service_tag(list_of_images: Dict, service_key: str, service_name: str, service_tag: str) -> str:
    available_tags_list = sorted(list_of_images[service_key]['tags'])
    # not tags available... probably an undefined service there...
    if not available_tags_list:
        raise exceptions.ServiceNotAvailableError(service_name, service_tag)
    tag = service_tag
    if not service_tag or service_tag == 'latest':
        # get latest tag
        tag = available_tags_list[len(available_tags_list)-1]
    elif available_tags_list.count(service_tag) != 1:
        raise exceptions.ServiceNotAvailableError(service_name=service_name, service_tag=service_tag)

    log.debug("Service tag found is %s ", service_tag)
    return tag

async def __prepare_runtime_parameters(user_id: str, service_key: str, service_tag: str, node_uuid: str, client: docker.client) -> Dict:
    # get the docker runtime labels
    service_runtime_parameters_labels = await __get_service_runtime_parameters_labels(service_key, service_tag)
    # convert the labels to docker parameters
    docker_service_runtime_parameters = __convert_labels_to_docker_runtime_parameters(service_runtime_parameters_labels, node_uuid)
    # add specific parameters
    __add_to_swarm_network_if_ports_published(client, docker_service_runtime_parameters)
    __add_uuid_label_to_service_runtime_params(docker_service_runtime_parameters, node_uuid)
    __add_env_variables_to_service_runtime_params(docker_service_runtime_parameters, user_id, node_uuid)
    __set_service_name(docker_service_runtime_parameters,
        registry_proxy.get_service_last_names(service_key),
        node_uuid)
    return docker_service_runtime_parameters

async def _start_docker_service(client: docker.client, user_id:str, service_key:str, service_tag:str, node_uuid:str, internal_network: docker.models.networks.Network) -> Dict: #pylint: disable=R0913
    # prepare runtime parameters
    docker_service_runtime_parameters = await __prepare_runtime_parameters(user_id, service_key, service_tag, node_uuid, client)
    # if an inter docker network exists, then the service must be part of it
    if internal_network is not None:
        __add_network_to_service_runtime_params(docker_service_runtime_parameters, internal_network)
    # prepare boot parameters
    service_boot_parameters_labels = await __get_service_boot_parameters_labels(service_key, service_tag)
    service_entrypoint = __get_service_entrypoint(service_boot_parameters_labels)

    #let-s start the service
    try:
        docker_image_full_path = config.REGISTRY_URL + '/' + service_key + ':' + service_tag
        log.debug("Starting docker service %s using parameters %s", docker_image_full_path, docker_service_runtime_parameters)
        service = client.services.create(docker_image_full_path, **docker_service_runtime_parameters)
        log.debug("Service started now waiting for it to run")
        await __wait_until_service_running_or_failed(service.id, docker_image_full_path, node_uuid)
        # the docker swarm opened some random port to access the service
        published_port = __get_docker_image_published_port(service.id)
        log.debug("Service successfully started on %s:%s",service_entrypoint, published_port)
        container_meta_data = {
            "published_port": published_port,
            "entry_point": service_entrypoint,
            "service_uuid":node_uuid
            }
        if published_port:
            await __pass_port_to_service(service, published_port, service_boot_parameters_labels)
        return container_meta_data
        
    except exceptions.ServiceStartTimeoutError as err:
        log.exception("Service failed to start")
        await _silent_service_cleanup(node_uuid)
        raise
    except docker.errors.ImageNotFound as err:
        log.exception("The docker image was not found")
        await _silent_service_cleanup(node_uuid)
        raise exceptions.ServiceNotAvailableError(service_key, service_tag) from err
    except docker.errors.APIError as err:
        log.exception("Error while accessing the server")
        # await _silent_service_cleanup(node_uuid)
        raise exceptions.GenericDockerError("Error while creating service", err) from err

async def _silent_service_cleanup(node_uuid):
    try:
        await stop_service(node_uuid)
    except exceptions.DirectorException:
        pass    

async def __create_node(client: docker.client, user_id:str, list_of_services: List[Dict], service_name: str, node_uuid: str) -> List[Dict]: # pylint: disable=R0913, R0915
    log.debug("Creating %s docker services for node %s using %s for user %s", len(list_of_services), service_name, node_uuid, user_id)
    # if the service uses several docker images, a network needs to be setup to connect them together
    inter_docker_network = None
    if len(list_of_services) > 1:
        inter_docker_network = __create_overlay_network_in_swarm(client, service_name, node_uuid)
        log.debug("Created docker network in swarm for service %s", service_name)

    containers_meta_data = list()
    for service in list_of_services:        
        service_meta_data = await _start_docker_service(client, user_id, service["key"], service["tag"], node_uuid, inter_docker_network)
        containers_meta_data.append(service_meta_data)
        
    return containers_meta_data

async def start_service(user_id: str, service_key: str, service_tag: str, node_uuid: str) -> Dict:
    # pylint: disable=C0103
    log.debug("starting service %s:%s and uuid %s", service_key, service_tag, node_uuid)
    # first check the uuid is available
    client = __get_docker_client()
    __check_node_uuid_available(client, node_uuid)

    service_name = registry_proxy.get_service_first_name(service_key)
    list_of_images = await __get_repos_from_key(service_key)
    service_tag = __find_service_tag(list_of_images, service_key, service_name, service_tag)
    log.debug("Found service to start %s:%s", service_key, service_tag)
    list_of_services_to_start = [{"key":service_key, "tag":service_tag}]
    # find the service dependencies
    list_of_dependencies = await __get_dependant_repos(service_key, service_tag)
    log.debug("Found service dependencies: %s", list_of_dependencies)
    if list_of_dependencies:
        list_of_services_to_start.append(list_of_dependencies)

    # create services
    __login_docker_registry(client)
    
    containers_meta_data = await __create_node(client, user_id, list_of_services_to_start, service_name, node_uuid)
    # we return only the info of the main service
    return containers_meta_data[0]

async def get_service_details(node_uuid: str) -> Dict:
    # get the docker client
    client = __get_docker_client()
    __login_docker_registry(client)
    try:
        list_running_services_with_uuid = client.services.list(
            filters={'label': 'uuid=' + node_uuid})
    except docker.errors.APIError as err:
        log.exception("Error while accessing container with uuid: %s", node_uuid)
        raise exceptions.GenericDockerError("Error while accessing container", err) from err
    # error if no service with such an id exists
    if not list_running_services_with_uuid:
        raise exceptions.ServiceUUIDNotFoundError(node_uuid)

async def stop_service(node_uuid: str):
    # get the docker client
    client = __get_docker_client()
    __login_docker_registry(client)

    try:
        list_running_services_with_uuid = client.services.list(
            filters={'label': 'uuid=' + node_uuid})
    except docker.errors.APIError as err:
        log.exception("Error while stopping container with uuid: %s", node_uuid)
        raise exceptions.GenericDockerError("Error while stopping container", err) from err

    # error if no service with such an id exists
    if not list_running_services_with_uuid:
        raise exceptions.ServiceUUIDNotFoundError(node_uuid)
    # remove the services
    try:
        for service in list_running_services_with_uuid:
            service.remove()
    except docker.errors.APIError as err:
        raise exceptions.GenericDockerError("Error while removing services", err)
    # remove network(s)
    __remove_overlay_network_of_swarm(client, node_uuid)
