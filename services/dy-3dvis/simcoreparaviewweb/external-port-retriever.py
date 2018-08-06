import logging
import os
import docker

_LOGGER = logging.getLogger(__name__)

def __get_docker_client():
    _LOGGER.debug("Initializing docker client")
    return  docker.from_env()


def __get_service_with_uuid(client, service_uuid):
    list_of_running_services_w_uuid = client.services.list(
        filters={'label': 'uuid=' + service_uuid})
    if not list_of_running_services_w_uuid:
        raise Exception('No service with uuid %s available: ' % (service_uuid))

    return list_of_running_services_w_uuid[0]        


def __get_service_open_ports(service):
    low_level_client = docker.APIClient()
    service_infos_json = low_level_client.services(filters={'id': service.id})

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
    _LOGGER.debug("Service %s publishes: %s ports", service.id, published_ports)
    return published_ports


node_uuid = os.environ.get("SIMCORE_NODE_UUID")
docker_client = __get_docker_client()
my_service = __get_service_with_uuid(docker_client, node_uuid)
list_of_open_ports = __get_service_open_ports(my_service)
for open_port in list_of_open_ports:
    print(open_port)