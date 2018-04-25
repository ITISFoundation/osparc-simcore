import os
import registry_proxy
import json
import docker

def IsServiceAWebServer(dockerImagePath):    
    return str(dockerImagePath).find('webserver') != -1

def login_docker_registry(dockerClient):
    try:
        # login
        registry_url = os.environ.get('REGISTRY_URL')
        username = os.environ.get('REGISTRY_USER')
        password = os.environ.get('REGISTRY_PW')
        dockerClient.login(registry=registry_url + '/v2', username=username, password=password)        
    except docker.errors.APIError as e:
        raise Exception('Error while loging to registry: ' + str(e))

def check_service_uuid_available(dockerClient, service_uuid):
    # check if service with same uuid already exists
    listOfRunningServicesWithUUID = dockerClient.services.list(filters={'label':'uuid=' + service_uuid})
    if (len(listOfRunningServicesWithUUID) != 0):
        raise Exception('A service with the same uuid is already running: ' + service_uuid)

def get_service_runtime_parameters_labels(image, tag):
    image_labels = registry_proxy.retrieve_labels_of_image(image, tag)
    SERVICE_RUNTIME_SETTINGS = 'simcore.service.settings'
    runtime_parameters = dict()
    if SERVICE_RUNTIME_SETTINGS in image_labels:
        runtime_parameters = json.loads(image_labels[SERVICE_RUNTIME_SETTINGS])
    return runtime_parameters

def convert_labels_to_docker_runtime_parameters(service_runtime_parameters_labels):
    runtime_params = dict()
    for param in service_runtime_parameters_labels:
        if 'name' not in param or 'type' not in param or 'value' not in param:
            pass

        if param['name'] == 'ports':
            # special handling for we need to open a port with 0:XXX this tells the docker engine to allocate whatever free port
            enpoint_spec = docker.types.EndpointSpec(ports={0:int(param['value'])})
            runtime_params["endpoint_spec"] = enpoint_spec
        else:
            runtime_params[param['name']] = param['value']

    
    
    return runtime_params

def add_uuid_label(docker_service_runtime_parameters, service_uuid):
    # add the service uuid to the docker service
    if "labels" in docker_service_runtime_parameters:
        docker_service_runtime_parameters["labels"]["uuid"] = service_uuid
    else:
        docker_service_runtime_parameters["labels"] = {"uuid":service_uuid}

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

def start_service(service_name, service_tag, service_uuid):
    # get the repos implied by the service name
    listOfInteractiveServicesRepositories = registry_proxy.retrieve_list_of_repos_with_interactive_services()
    # find the ones containing the service name
    listOfReposForService = []
    [listOfReposForService.append(i) for i in listOfInteractiveServicesRepositories if registry_proxy.get_service_name(i) == service_name]
    # get the available tags for each service
    listOfImages = {}
    for repo in listOfReposForService:
        listOfImages[repo] = registry_proxy.retrieve_list_of_images_in_repo(repo)
    
    # initialise docker client and check the uuid is available
    dockerClient = docker.from_env()
    check_service_uuid_available(dockerClient, service_uuid)
    login_docker_registry(dockerClient)
    
    containers_meta_data = list()
    for dockerImagePath in listOfImages:
        availableTagsList = sorted(listOfImages[dockerImagePath]['tags'])
        if len(availableTagsList) == 0:
            raise Exception('No available image in ' + dockerImagePath)

        tag = availableTagsList[len(availableTagsList)-1]
        if not service_tag == 'latest' and availableTagsList.count(service_tag) == 1:
            tag = service_tag
        
        dockerImageFullPath = os.environ.get('REGISTRY_URL') +'/' + dockerImagePath + ':' + tag
        
        service_runtime_parameters_labels = get_service_runtime_parameters_labels(dockerImagePath, tag)
        docker_service_runtime_parameters = convert_labels_to_docker_runtime_parameters(service_runtime_parameters_labels)
        add_uuid_label(docker_service_runtime_parameters, service_uuid)
        # let-s start the service
        try:            
            service = dockerClient.services.create(dockerImageFullPath, **docker_service_runtime_parameters)
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
    dockerClient = docker.from_env()
    login_docker_registry(dockerClient)
    
    try:
        listOfRunningServicesWithUUID = dockerClient.services.list(filters={'label':'uuid=' + service_uuid})
        [service.remove() for service in listOfRunningServicesWithUUID]

    except docker.errors.APIError as e:
        raise Exception('Error while stopping container' + str(e))
    