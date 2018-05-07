import os
import registry_proxy
import json
import docker
import time

SERVICE_RUNTIME_SETTINGS = 'simcore.service.settings'

def IsServiceAWebServer(dockerImagePath):
    return str(dockerImagePath).find('webserver') != -1

def login_docker_registry(docker_client):
    try:
        # login
        registry_url = os.environ.get('REGISTRY_URL')
        username = os.environ.get('REGISTRY_USER')
        password = os.environ.get('REGISTRY_PW')
        docker_client.login(registry=registry_url + '/v2', username=username, password=password)
    except docker.errors.APIError as e:
        raise Exception('Error while loging to registry: ' + str(e))

def check_service_uuid_available(docker_client, service_uuid):
    # check if service with same uuid already exists
    listOfRunningServicesWithUUID = docker_client.services.list(filters={'label':'uuid=' + service_uuid})
    if (len(listOfRunningServicesWithUUID) != 0):
        raise Exception('A service with the same uuid is already running: ' + service_uuid)

def get_service_runtime_parameters_labels(image, tag):
    image_labels = registry_proxy.retrieve_labels_of_image(image, tag)
    runtime_parameters = dict()
    if SERVICE_RUNTIME_SETTINGS in image_labels:
        runtime_parameters = json.loads(image_labels[SERVICE_RUNTIME_SETTINGS])
    return runtime_parameters

def convert_labels_to_docker_runtime_parameters(service_runtime_parameters_labels, service_uuid):
    runtime_params = dict()
    for param in service_runtime_parameters_labels:
        if 'name' not in param or 'type' not in param or 'value' not in param:
            pass
        index = str(param['value']).find("%service_uuid%")
        if  str(param['value']).find("%service_uuid%") != -1:
            dummy_string = json.dumps(param['value'])
            dummy_string = dummy_string.replace("%service_uuid%", service_uuid)
            param['value'] = json.loads(dummy_string)
            # replace string by actual value
            #param['value'] = str(param['value']).replace("%service_uuid%", service_uuid)

        if param['name'] == 'ports':
            # special handling for we need to open a port with 0:XXX this tells the docker engine to allocate whatever free port
            enpoint_spec = docker.types.EndpointSpec(ports={0:int(param['value'])})
            runtime_params["endpoint_spec"] = enpoint_spec
        else:
            runtime_params[param['name']] = param['value']
    return runtime_params

def add_uuid_label_to_service_runtime_params(docker_service_runtime_parameters, service_uuid):
    # add the service uuid to the docker service
    if "labels" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["labels"]["uuid"] = service_uuid
    else:
        docker_service_runtime_parameters["labels"] = {"uuid":service_uuid}

def add_network_to_service_runtime_params(docker_service_runtime_parameters, docker_network):
    if "networks" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["networks"].append(docker_network.id)
    else:
        docker_service_runtime_parameters["networks"] = [docker_network.id]

def set_service_name(docker_service_runtime_parameters, service_name, service_uuid):
    docker_service_runtime_parameters["name"] = service_name + "_" + service_uuid

def get_docker_image_published_ports(service_id):
    low_level_client = docker.APIClient()
    service_infos_json = low_level_client.services(filters={'id':service_id})
    published_ports = list()
    for service_info in service_infos_json: # there should be only one actually
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
        docker_network = docker_client.networks.create(network_name, driver="overlay", scope="swarm", labels={"uuid":service_uuid})
        return docker_network
    except docker.errors.APIError as e:
        raise Exception('Docker server error while creating network: ' + str(e))

def remove_overlay_network_of_swarm(docker_client, service_uuid):
    try:
        networks = docker_client.networks.list(filters={"label":"uuid=" + service_uuid})
        # remove any network in the list (should be only one)
        for network in networks:
            network.remove()
    except docker.errors.APIError as e:
        raise Exception("docker server error while removing networks for service with uuid " + service_uuid)

def wait_until_service_running_or_failed(service_id):
    client = docker.APIClient()

    # some times one has to wait until the task info is filled
    while True:
        task_infos_json = client.tasks(filters={'service':service_id})
        if len(task_infos_json) > 0:
            # check the status
            status_json = task_infos_json[0]["Status"]
            task_state = status_json["State"]
            if task_state == "running":
                # great it is running
                break
            elif task_state == 'failed' or task_state == "rejected":
                # error
                raise Exception("the service could not be started")
        time.sleep(0.005) # 5ms

def start_service(service_name, service_tag, service_uuid):
    # find the ones containing the service name
    list_repos_for_service = registry_proxy.retrieve_list_of_interactive_services_with_name(service_name)
    # get the available image for each service (syntax is image:tag)
    list_of_images = {}
    for repo in list_repos_for_service:
        list_of_images[repo] = registry_proxy.retrieve_list_of_images_in_repo(repo)

    # initialise docker client and check the uuid is available
    docker_client = docker.from_env()
    check_service_uuid_available(docker_client, service_uuid)
    login_docker_registry(docker_client)

    if len(list_of_images) > 1:
      # create a new network to connect the differnt containers
      docker_network = create_overlay_network_in_swarm(docker_client, service_name, service_uuid)
    # create services
    containers_meta_data = list()
    for docker_image_path in list_of_images:
        available_tags_list = sorted(list_of_images[docker_image_path]['tags'])
        if len(available_tags_list) == 0:
            raise Exception('No available image in ' + docker_image_path)

        tag = available_tags_list[len(available_tags_list)-1]
        if not service_tag == 'latest' and available_tags_list.count(service_tag) == 1:
            tag = service_tag

        docker_image_full_path = os.environ.get('REGISTRY_URL') +'/' + docker_image_path + ':' + tag

        # prepare runtime parameters
        service_runtime_parameters_labels = get_service_runtime_parameters_labels(docker_image_path, tag)
        docker_service_runtime_parameters = convert_labels_to_docker_runtime_parameters(service_runtime_parameters_labels, service_uuid)
        add_uuid_label_to_service_runtime_params(docker_service_runtime_parameters, service_uuid)
        if len(list_of_images) > 1:
          add_network_to_service_runtime_params(docker_service_runtime_parameters, docker_network)
        set_service_name(docker_service_runtime_parameters, registry_proxy.get_service_sub_name(docker_image_path), service_uuid)
        # let-s start the service
        try:
            service = docker_client.services.create(docker_image_full_path, **docker_service_runtime_parameters)
            wait_until_service_running_or_failed(service.id)
            published_ports = get_docker_image_published_ports(service.id)
            container_meta_data = {"container_id":service.id, "published_ports":published_ports}
            containers_meta_data.append(container_meta_data)
        except docker.errors.ImageNotFound as e:
            # first cleanup
            stop_service(service_uuid)
            raise Exception('Error service not found: ' + str(e))
        except docker.errors.APIError as e:
            # first cleanup
            stop_service(service_uuid)
            raise Exception('Error while accessing docker server: ' + str(e))
    service_meta_data = {"service_name":service_name, "service_uuid":service_uuid, "containers":containers_meta_data}
    return json.dumps(service_meta_data)

def stop_service(service_uuid):
    # get the docker client
    docker_client = docker.from_env()
    login_docker_registry(docker_client)

    try:
        list_running_services_with_uuid = docker_client.services.list(filters={'label':'uuid=' + service_uuid})
        [service.remove() for service in list_running_services_with_uuid]
        remove_overlay_network_of_swarm(docker_client, service_uuid)
    except docker.errors.APIError as e:
        raise Exception('Error while stopping container' + str(e))
