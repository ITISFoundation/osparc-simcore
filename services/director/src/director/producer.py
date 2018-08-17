"""[summary]

"""
# pylint: disable=C0111

import os
import time
import json
import logging
import requests
import tenacity

import docker
import registry_proxy

SERVICE_RUNTIME_SETTINGS = 'simcore.service.settings'
SERVICE_RUNTIME_BOOTSETTINGS = 'simcore.service.bootsettings'

_LOGGER = logging.getLogger(__name__)

def __get_docker_client():
    _LOGGER.debug("Initiializing docker client")
    return  docker.from_env()

def __login_docker_registry(docker_client):    
    try:
        # login
        registry_url = os.environ.get('REGISTRY_URL')
        username = os.environ.get('REGISTRY_USER')
        password = os.environ.get('REGISTRY_PW')
        _LOGGER.debug("logging into docker registry %s", registry_url)
        docker_client.login(registry=registry_url + '/v2',
                            username=username, password=password)
        _LOGGER.debug("logged into docker registry %s", registry_url)
    except docker.errors.APIError as err:
        _LOGGER.exception("Error while loggin into the registry")
        raise Exception from err

def __check_service_uuid_available(docker_client, service_uuid):
    _LOGGER.debug("Checked if UUID %s is already in use", service_uuid)
    # check if service with same uuid already exists
    list_of_running_services_w_uuid = docker_client.services.list(
        filters={'label': 'uuid=' + service_uuid})
    if list_of_running_services_w_uuid:
        raise Exception(
            'A service with the same uuid is already running: ' + service_uuid)
    _LOGGER.debug("UUID %s is free")

def __check_setting_correctness(setting):
    if 'name' not in setting or 'type' not in setting or 'value' not in setting:
        raise Exception("Invalid setting in %s" % setting)

def __get_service_runtime_parameters_labels(image, tag):
    # pylint: disable=C0103
    image_labels = registry_proxy.retrieve_labels_of_image(image, tag)
    runtime_parameters = dict()
    if SERVICE_RUNTIME_SETTINGS in image_labels:
        runtime_parameters = json.loads(image_labels[SERVICE_RUNTIME_SETTINGS])
    _LOGGER.debug("Retrieved service runtime settings: %s", runtime_parameters)
    return runtime_parameters

def __get_service_boot_parameters_labels(image, tag):
    # pylint: disable=C0103
    image_labels = registry_proxy.retrieve_labels_of_image(image, tag)
    boot_params = dict()
    if SERVICE_RUNTIME_BOOTSETTINGS in image_labels:
        boot_params = json.loads(image_labels[SERVICE_RUNTIME_BOOTSETTINGS])
    _LOGGER.debug("Retrieved service boot settings: %s", boot_params)
    return boot_params


def __convert_labels_to_docker_runtime_parameters(service_runtime_parameters_labels, service_uuid):
    # pylint: disable=C0103
    _LOGGER.debug("Converting labels to docker runtime parameters")
    runtime_params = dict()
    for param in service_runtime_parameters_labels:
        __check_setting_correctness(param)
        # index = str(param['value']).find("%service_uuid%")
        if str(param['value']).find("%service_uuid%") != -1:
            dummy_string = json.dumps(param['value'])
            dummy_string = dummy_string.replace("%service_uuid%", service_uuid)
            param['value'] = json.loads(dummy_string)
            # replace string by actual value
            #param['value'] = str(param['value']).replace("%service_uuid%", service_uuid)

        if param['name'] == 'ports':
            # special handling for we need to open a port with 0:XXX this tells the docker engine to allocate whatever free port
            enpoint_spec = docker.types.EndpointSpec(ports={0: int(param['value'])})
            runtime_params["endpoint_spec"] = enpoint_spec
        else:
            runtime_params[param['name']] = param['value']
    _LOGGER.debug("Converted labels to docker runtime parameters: %s", runtime_params)
    return runtime_params

def __get_service_entrypoint(service_boot_parameters_labels):
    _LOGGER.debug("Getting service entrypoint")
    for param in service_boot_parameters_labels:
        __check_setting_correctness(param)
        if param['name'] == 'entry_point':
            _LOGGER.debug("Service entrypoint is %s", param['value'])
            return param['value']
    return ''

def __add_to_swarm_network_if_ports_published(docker_client, docker_service_runtime_parameters):
    # TODO: SAN this is a brain killer... change services to something better...
    if "endpoint_spec" in docker_service_runtime_parameters:
        network_id = "services_default"
        _LOGGER.debug("Adding swarm network with id: %s to docker runtime parameters", network_id)
        list_of_networks =  docker_client.networks.list(names=[network_id])
        for network in list_of_networks:
            __add_network_to_service_runtime_params(docker_service_runtime_parameters, network)
        _LOGGER.debug("Added swarm network %s to docker runtime parameters", network_id)

def __add_uuid_label_to_service_runtime_params(docker_service_runtime_parameters, service_uuid):
    # pylint: disable=C0103
    # add the service uuid to the docker service
    if "labels" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["labels"]["uuid"] = service_uuid
    else:
        docker_service_runtime_parameters["labels"] = {"uuid": service_uuid}
    _LOGGER.debug("Added uuid label to docker runtime parameters: %s", docker_service_runtime_parameters["labels"])

def __add_network_to_service_runtime_params(docker_service_runtime_parameters, docker_network):
    # pylint: disable=C0103
    if "networks" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["networks"].append(docker_network.id)
    else:
        docker_service_runtime_parameters["networks"] = [docker_network.id]
    _LOGGER.debug("Added network parameter to docker runtime parameters: %s", docker_service_runtime_parameters["networks"])

def __add_env_variables_to_service_runtime_params(docker_service_runtime_parameters, service_uuid):
    variables = [
        "POSTGRES_ENDPOINT=" + os.environ.get("POSTGRES_ENDPOINT"),
        "POSTGRES_USER=" + os.environ.get("POSTGRES_USER"),
        "POSTGRES_PASSWORD=" + os.environ.get("POSTGRES_PASSWORD"),
        "POSTGRES_DB=" + os.environ.get("POSTGRES_DB"),
        "S3_ENDPOINT=" + os.environ.get("S3_ENDPOINT"),
        "S3_ACCESS_KEY=" + os.environ.get("S3_ACCESS_KEY"),
        "S3_SECRET_KEY=" + os.environ.get("S3_SECRET_KEY"),
        "S3_BUCKET_NAME=" + os.environ.get("S3_BUCKET_NAME"),
        "SIMCORE_NODE_UUID=" + service_uuid
    ]    
    if "env" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["env"].extend(variables)
    else:
        docker_service_runtime_parameters["env"] = variables
    _LOGGER.debug("Added env parameter to docker runtime parameters: %s", docker_service_runtime_parameters["env"])

def __set_service_name(docker_service_runtime_parameters, service_name, service_uuid):
    # pylint: disable=C0103
    docker_service_runtime_parameters["name"] = service_name + "_" + service_uuid
    _LOGGER.debug("Added service name parameter to docker runtime parameters: %s", docker_service_runtime_parameters["name"])


def __get_docker_image_published_ports(service_id):
    # pylint: disable=C0103
    low_level_client = docker.APIClient()
    service_infos_json = low_level_client.services(filters={'id': service_id})

    if len(service_infos_json) != 1:
        _LOGGER.warning("Expected a single port per service, got %s", service_infos_json)

    published_ports = list()
    for service_info in service_infos_json:
        if 'Endpoint' in service_info:
            service_endpoints = service_info['Endpoint']
            if 'Ports' in service_endpoints:
                ports_info_json = service_info['Endpoint']['Ports']
                for port in ports_info_json:
                    published_ports.append(port['PublishedPort'])
    _LOGGER.debug("Service %s publishes: %s ports", service_id, published_ports)
    return published_ports

@tenacity.retry(wait=tenacity.wait_fixed(2), stop=tenacity.stop_after_attempt(3) or tenacity.stop_after_delay(10))
def __pass_port_to_service(service, port, service_boot_parameters_labels):
    for param in service_boot_parameters_labels:
        __check_setting_correctness(param)
        if param['name'] == 'published_port':
            # time.sleep(5)
            route = param['value']
            _LOGGER.debug("Service needs to get published port %s using route %s", port, route)
            service_url = "http://" + str(service.name) + "/" + route
            query_string = {"port":str(port)}
            _LOGGER.debug("creating request %s and query %s", service_url, query_string)
            response = requests.post(service_url, data=query_string)
            _LOGGER.debug("query response: %s", response)
            return
    _LOGGER.debug("service %s does not need to know its external port", service.name)

def __create_network_name(service_name, service_uuid):
    return service_name + '_' + service_uuid

def __create_overlay_network_in_swarm(docker_client, service_name, service_uuid):    
    _LOGGER.debug("Creating overlay network for service %s with uuid %s", service_name, service_uuid)
    network_name = __create_network_name(service_name, service_uuid)    
    try:
        docker_network = docker_client.networks.create(
            network_name, driver="overlay", scope="swarm", labels={"uuid": service_uuid})
        _LOGGER.debug("Network %s created for service %s with uuid %s", network_name, service_name, service_uuid)
        return docker_network
    except docker.errors.APIError as err:
        _LOGGER.exception("Error while creating network for service %s", service_name)
        raise Exception from err

def __remove_overlay_network_of_swarm(docker_client, service_uuid):
    _LOGGER.debug("Removing overlay network for service with uuid %s", service_uuid)
    try:
        networks = docker_client.networks.list(
            filters={"label": "uuid=" + service_uuid})
        _LOGGER.debug("Found %s networks with uuid %s", len(networks), service_uuid)
        # remove any network in the list (should be only one)
        for network in networks:
            network.remove()
        _LOGGER.debug("Removed %s networks with uuid %s", len(networks), service_uuid)
    except docker.errors.APIError as err:
        _LOGGER.exception("Error while removing networks for service with uuid: %s", service_uuid)
        raise Exception from err

def __wait_until_service_running_or_failed(service_id):
    # pylint: disable=C0103
    _LOGGER.debug("Waiting for service %s to start", service_id)
    client = docker.APIClient()

    # some times one has to wait until the task info is filled
    while True:
        task_infos_json = client.tasks(filters={'service': service_id})
        if task_infos_json:
            # check the status
            status_json = task_infos_json[0]["Status"]
            task_state = status_json["State"]

            _LOGGER.debug("%s %s", service_id, task_state)
            if task_state == "running":
                break
            elif task_state in ("failed", "rejected"):
                raise Exception("the service could not be started")
        # TODO: all these functions should be async and here one could use await sleep which
        # would allow dealing with other events instead of wasting time here
        time.sleep(0.005)  # 5ms
    _LOGGER.debug("Waited for service %s to start", service_id)

def __get_list_of_images(service_name):
    # find the ones containing the service name
    list_repos_for_service = registry_proxy.retrieve_list_of_interactive_services_with_name(service_name)
    # get the available image for each service (syntax is image:tag)
    list_of_images = {}
    for repo in list_repos_for_service:
        list_of_images[repo] = registry_proxy.retrieve_list_of_images_in_repo(repo)
    _LOGGER.debug("Service %s has the following list of images available: %s", service_name, list_of_images)

    return list_of_images

def __find_service_tag(list_of_images, docker_image_path, service_tag):
    available_tags_list = sorted(list_of_images[docker_image_path]['tags'])
    if not available_tags_list:
        raise Exception('No available image in ' + docker_image_path)

    tag = available_tags_list[len(available_tags_list)-1]
    if not service_tag == 'latest' and available_tags_list.count(service_tag) == 1:
        tag = service_tag
    _LOGGER.debug("Service tag found is %s ", service_tag)
    return tag

def __prepare_runtime_parameters(docker_image_path, tag, service_uuid, docker_client):
    # get the runtime labels
    service_runtime_parameters_labels = __get_service_runtime_parameters_labels(docker_image_path, tag)
    # convert the labels to docker parameters
    docker_service_runtime_parameters = __convert_labels_to_docker_runtime_parameters(service_runtime_parameters_labels, service_uuid)
    # add specific parameters
    __add_to_swarm_network_if_ports_published(docker_client, docker_service_runtime_parameters)
    __add_uuid_label_to_service_runtime_params(docker_service_runtime_parameters, service_uuid)
    __add_env_variables_to_service_runtime_params(docker_service_runtime_parameters, service_uuid)
    __set_service_name(docker_service_runtime_parameters,
        registry_proxy.get_service_sub_name(docker_image_path),
        service_uuid)       
    return docker_service_runtime_parameters

def __create_services(docker_client, list_of_images, service_name, service_tag, service_uuid):
    _LOGGER.debug("Start creating docker services for service %s", service_name)

    # if the service uses several docker images, a network needs to be setup to connect them together
    if len(list_of_images) > 1:        
        inter_docker_network = __create_overlay_network_in_swarm(docker_client, service_name, service_uuid)
        _LOGGER.debug("Created docker network in swarm for service %s", service_name)

    containers_meta_data = list()
    for docker_image_path in list_of_images:
        tag = __find_service_tag(list_of_images, docker_image_path, service_tag)
        
        _LOGGER.debug("Preparing runtime parameters for docker image %s:%s", docker_image_path, tag)
        # prepare runtime parameters
        docker_service_runtime_parameters = __prepare_runtime_parameters(docker_image_path, tag, service_uuid, docker_client)
        # if an inter docker network exists, then the service must be part of it
        if len(list_of_images) > 1:
            __add_network_to_service_runtime_params(docker_service_runtime_parameters, inter_docker_network)
        # prepare boot parameters
        service_boot_parameters_labels = __get_service_boot_parameters_labels(docker_image_path, tag)
        service_entrypoint = __get_service_entrypoint(service_boot_parameters_labels)

        #let-s start the service
        try:
            docker_image_full_path = os.environ.get('REGISTRY_URL') + '/' + docker_image_path + ':' + tag
            _LOGGER.debug("Starting docker service %s using parameters %s", docker_image_full_path, docker_service_runtime_parameters)
            service = docker_client.services.create(docker_image_full_path, **docker_service_runtime_parameters)
            _LOGGER.debug("Service started now waiting for it to run")
            __wait_until_service_running_or_failed(service.id)
            # the docker swarm opened some random port to access the service
            published_ports = __get_docker_image_published_ports(service.id)
            _LOGGER.debug("Service with parameters %s successfully started, published ports are %s, entry_point is %s", docker_service_runtime_parameters, published_ports, service_entrypoint)
            container_meta_data = {
                "container_id": service.id,
                "published_ports": published_ports,
                "entry_point": service_entrypoint
                }
            containers_meta_data.append(container_meta_data)

            if published_ports:
                __pass_port_to_service(service, published_ports[0], service_boot_parameters_labels)
            
        except docker.errors.ImageNotFound as err:
            # first cleanup
            stop_service(service_uuid)
            _LOGGER.exception("The docker image was not found")
            raise Exception from err
        except docker.errors.APIError as err:
            # first cleanup
            stop_service(service_uuid)
            _LOGGER.exception("Error while accessing the server")
            raise Exception from err
    return containers_meta_data

def start_service(service_name, service_tag, service_uuid):
    # pylint: disable=C0103
    _LOGGER.debug("starting service %s with tag %s and uuid %s", service_name, service_tag, service_uuid)
    list_of_images = __get_list_of_images(service_name)
    
    docker_client = __get_docker_client()
    __check_service_uuid_available(docker_client, service_uuid)

    __login_docker_registry(docker_client)    

    # create services
    containers_meta_data = __create_services(docker_client, list_of_images, service_name, service_tag, service_uuid)
    service_meta_data = {
        "service_name": service_name,
        "service_uuid": service_uuid,
        "containers": containers_meta_data
        }
    return json.dumps(service_meta_data)


def stop_service(service_uuid):
    # get the docker client
    docker_client = __get_docker_client()
    __login_docker_registry(docker_client)

    try:
        list_running_services_with_uuid = docker_client.services.list(
            filters={'label': 'uuid=' + service_uuid})
        for service in list_running_services_with_uuid:
            service.remove()
        __remove_overlay_network_of_swarm(docker_client, service_uuid)
    except docker.errors.APIError as err:
        _LOGGER.exception("Error while stopping container with uuid: %s", service_uuid)
        raise Exception from err
