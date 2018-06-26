"""[summary]

"""
# pylint: disable=C0111

import os
import time
import json
import logging

import docker
import registry_proxy

SERVICE_RUNTIME_SETTINGS = 'simcore.service.settings'

_LOGGER = logging.getLogger(__name__)

def is_service_a_web_server(docker_image_path):
    return str(docker_image_path).find('webserver') != -1


def login_docker_registry(docker_client):
    try:
        # login
        registry_url = os.environ.get('REGISTRY_URL')
        username = os.environ.get('REGISTRY_USER')
        password = os.environ.get('REGISTRY_PW')
        docker_client.login(registry=registry_url + '/v2',
                            username=username, password=password)
    except docker.errors.APIError as err:
        raise Exception('Error while loging to registry: ' + str(err))


def check_service_uuid_available(docker_client, service_uuid):
    # check if service with same uuid already exists
    list_of_running_services_w_uuid = docker_client.services.list(
        filters={'label': 'uuid=' + service_uuid})
    if list_of_running_services_w_uuid:
        raise Exception(
            'A service with the same uuid is already running: ' + service_uuid)


def get_service_runtime_parameters_labels(image, tag):
    # pylint: disable=C0103
    image_labels = registry_proxy.retrieve_labels_of_image(image, tag)
    runtime_parameters = dict()
    if SERVICE_RUNTIME_SETTINGS in image_labels:
        runtime_parameters = json.loads(image_labels[SERVICE_RUNTIME_SETTINGS])
    return runtime_parameters


def convert_labels_to_docker_runtime_parameters(service_runtime_parameters_labels, service_uuid):
    # pylint: disable=C0103
    runtime_params = dict()
    for param in service_runtime_parameters_labels:
        if 'name' not in param or 'type' not in param or 'value' not in param:
            pass
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
    return runtime_params


def add_uuid_label_to_service_runtime_params(docker_service_runtime_parameters, service_uuid):
    # pylint: disable=C0103
    # add the service uuid to the docker service
    if "labels" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["labels"]["uuid"] = service_uuid
    else:
        docker_service_runtime_parameters["labels"] = {"uuid": service_uuid}

def add_network_to_service_runtime_params(docker_service_runtime_parameters, docker_network):
    # pylint: disable=C0103
    if "networks" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["networks"].append(docker_network.id)
    else:
        docker_service_runtime_parameters["networks"] = [docker_network.id]

def add_env_variables_to_service_runtime_params(docker_service_runtime_parameters, service_uuid):
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
        docker_service_runtime_parameters["env"].append(variables)
    else:
        docker_service_runtime_parameters["env"] = variables

def set_service_name(docker_service_runtime_parameters, service_name, service_uuid):
    # pylint: disable=C0103
    docker_service_runtime_parameters["name"] = service_name + \
        "_" + service_uuid


def get_docker_image_published_ports(service_id):
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
    return published_ports


def create_network_name(service_name, service_uuid):
    return service_name + '_' + service_uuid


def create_overlay_network_in_swarm(docker_client, service_name, service_uuid):
    network_name = create_network_name(service_name, service_uuid)
    try:
        docker_network = docker_client.networks.create(
            network_name, driver="overlay", scope="swarm", labels={"uuid": service_uuid})
        return docker_network
    except docker.errors.APIError as err:
        raise Exception(
            'Docker server error while creating network: ' + str(err))


def remove_overlay_network_of_swarm(docker_client, service_uuid):
    try:
        networks = docker_client.networks.list(
            filters={"label": "uuid=" + service_uuid})
        # remove any network in the list (should be only one)
        for network in networks:
            network.remove()
    except docker.errors.APIError:
        raise Exception(
            "docker server error while removing networks for service with uuid " + service_uuid)


def wait_until_service_running_or_failed(service_id):
    # pylint: disable=C0103
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
            elif task_state == 'failed' or task_state == "rejected":
                raise Exception("the service could not be started")
        # TODO: all these functions should be async and here one could use await sleep which
        # would allow dealing with other events instead of wasting time here
        time.sleep(0.005)  # 5ms


def start_service(service_name, service_tag, service_uuid):
    # pylint: disable=C0103

    # find the ones containing the service name
    list_repos_for_service = registry_proxy.retrieve_list_of_interactive_services_with_name(service_name)

    # get the available image for each service (syntax is image:tag)
    list_of_images = {}
    for repo in list_repos_for_service:
        list_of_images[repo] = registry_proxy.retrieve_list_of_images_in_repo(repo)

    _LOGGER.debug("Found list of images %s for service %s", list_of_images, service_name)
    # initialise docker client and check the uuid is available
    docker_client = docker.from_env()
    check_service_uuid_available(docker_client, service_uuid)
    login_docker_registry(docker_client)
    _LOGGER.debug("Logged in docker registry")
    if len(list_of_images) > 1:
        # create a new network to connect the differnt containers
        docker_network = create_overlay_network_in_swarm(
            docker_client, service_name, service_uuid)
        _LOGGER.debug("Created docker network in swarm for service %s", service_name)

    # create services
    containers_meta_data = list()
    for docker_image_path in list_of_images:
        available_tags_list = sorted(list_of_images[docker_image_path]['tags'])
        if not available_tags_list:
            raise Exception('No available image in ' + docker_image_path)

        tag = available_tags_list[len(available_tags_list)-1]
        if not service_tag == 'latest' and available_tags_list.count(service_tag) == 1:
            tag = service_tag

        docker_image_full_path = os.environ.get('REGISTRY_URL') + '/' + docker_image_path + ':' + tag

        # prepare runtime parameters
        service_runtime_parameters_labels = get_service_runtime_parameters_labels(docker_image_path, tag)
        docker_service_runtime_parameters = convert_labels_to_docker_runtime_parameters(service_runtime_parameters_labels, service_uuid)
        add_uuid_label_to_service_runtime_params(docker_service_runtime_parameters, service_uuid)
        if len(list_of_images) > 1:
            add_network_to_service_runtime_params(docker_service_runtime_parameters, docker_network)
        add_env_variables_to_service_runtime_params(docker_service_runtime_parameters, service_uuid)
        set_service_name(docker_service_runtime_parameters,
            registry_proxy.get_service_sub_name(docker_image_path),
            service_uuid)

        # TODO: SAN this is a brain killer... change services to something better...
        list_of_networks =  docker_client.networks.list(names=["services_default"])
        for network in list_of_networks:
            add_network_to_service_runtime_params(docker_service_runtime_parameters, network)

        # let-s start the service
        try:
            _LOGGER.debug("Starting service with parameters %s", docker_service_runtime_parameters)
            service = docker_client.services.create(docker_image_full_path, **docker_service_runtime_parameters)
            wait_until_service_running_or_failed(service.id)            
            published_ports = get_docker_image_published_ports(service.id)
            _LOGGER.debug("Service with parameters %s successfully started, published ports are %s", docker_service_runtime_parameters, published_ports)
            container_meta_data = {
                "container_id": service.id,
                "published_ports": published_ports
                }
            containers_meta_data.append(container_meta_data)
        except docker.errors.ImageNotFound as err:
            # first cleanup
            # TODO: check exceptions policy
            stop_service(service_uuid)
            raise Exception('Error service not found: ' + str(err))
        except docker.errors.APIError as err:
            # first cleanup
            # TODO: check exceptions policy
            stop_service(service_uuid)
            raise Exception('Error while accessing docker server: ' + str(err))

    service_meta_data = {
        "service_name": service_name,
        "service_uuid": service_uuid,
        "containers": containers_meta_data
        }
    return json.dumps(service_meta_data)


def stop_service(service_uuid):
    # get the docker client
    docker_client = docker.from_env()
    login_docker_registry(docker_client)

    try:
        list_running_services_with_uuid = docker_client.services.list(
            filters={'label': 'uuid=' + service_uuid})
        for service in list_running_services_with_uuid:
            service.remove()
        remove_overlay_network_of_swarm(docker_client, service_uuid)
    except docker.errors.APIError as err:
        # TODO: check exceptions policy
        raise Exception('Error while stopping container' + str(err))
