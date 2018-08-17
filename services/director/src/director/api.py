from aiohttp import web
import producer
import registry_proxy
import logging

_LOGGER = logging.getLogger(__name__)
registry_proxy.setup_registry_connection()

async def root_get():  # noqa: E501
    """Returns a nice greeting

    Returns a nice greeting # noqa: E501


    :rtype: str
    """
    greeting = "<h1>Hoi zaeme! Salut les d'jeunz!</h1><h3>This is {} responding!</h2>".format(__name__)    
    return greeting

async def list_interactive_services_get():  # noqa: E501
    """lists available interactive services in the oSparc platform

    lists available interactive services in the oSparc platform # noqa: E501


    :rtype: List[ServiceDescription]
    """
    # get the services repos
    list_of_interactive_repos = registry_proxy.retrieve_list_of_repos_with_interactive_services()
    return list_of_interactive_repos

async def start_service_post(service_name, service_uuid, service_tag=None):  # noqa: E501
    """Starts an interactive service in the oSparc platform and returns its entrypoint

    Starts an interactive service in the oSparc platform and returns its entrypoint # noqa: E501

    :param service_name: The name of the service to start
    :type service_name: str
    :param service_uuid: The uuid to assign the service with
    :type service_uuid: str
    :param service_tag: The tag/version of the service to start
    :type service_tag: str

    :rtype: List[Service]
    """
    print(service_name)
    service = producer.start_service(service_name, service_tag, service_uuid)

    return web.json_response(data=service)


async def stop_service_post(service_uuid):  # noqa: E501
    """Stops and removes an interactive service from the oSparc platform

    Stops and removes an interactive service from the oSparc platform # noqa: E501

    :param service_uuid: The uuid of the service to stop
    :type service_uuid: str

    :rtype: None
    """
    producer.stop_service(service_uuid)
    return web.json_response(data="service stopped")

async def list_computational_services_get():  # noqa: E501
    """Lists available computational services in the oSparc platform

    Lists available computational services in the oSparc platform # noqa: E501


    :rtype: List[ServiceDescription]
    """
    repos = registry_proxy.list_computational_services()
    return web.json_response(data=repos)