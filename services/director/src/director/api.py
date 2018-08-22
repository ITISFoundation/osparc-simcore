import logging
from collections import defaultdict

from aiohttp import web_exceptions
import aiohttp_apiset.middlewares
from aiohttp_apiset.exceptions import ValidationError

from director import producer, registry_proxy, exceptions

from director.models.service_description import ServiceDescription
from director.models.service import Service

_LOGGER = logging.getLogger(__name__)
registry_proxy.setup_registry_connection()

async def root_get(request, errors: defaultdict(set)):  # noqa: E501
    """Returns a nice greeting

    Returns a nice greeting # noqa: E501

    :rtype: str
    """
    greeting = "<h1>Hoi zaeme! Salut les d'jeunz!</h1><h3>This is {} responding!</h3>".format(__name__)
    return greeting

async def list_interactive_services_get(request, errors: defaultdict(set)):  # noqa: E501
    """lists available interactive services in the oSparc platform

    lists available interactive services in the oSparc platform # noqa: E501


    :rtype: List[ServiceDescription]
    """
    # get the services repos
    try:
        list_of_interactive_repos = registry_proxy.retrieve_list_of_repos_with_interactive_services()
        service_descs = [ServiceDescription.from_dict(x) for x in list_of_interactive_repos.values()]
        return service_descs
    except exceptions.DirectorException as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))
    


async def start_service_post(request, service_name, service_uuid, service_tag=None):  # noqa: E501
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
    try:
      service = producer.start_service(service_name, service_tag, service_uuid)
    except exceptions.ServiceNotFoundError as err:
      raise web_exceptions.HTTPNotFound(reason=str(err))
    except exceptions.ServiceUUIDInUseError as err:
      raise web_exceptions.HTTPConflict(reason=str(err))
    except exceptions.DirectorException as err:
      raise web_exceptions.HTTPInternalServerError(reason=str(err))

    return service


async def stop_service_post(service_uuid):  # noqa: E501
    """Stops and removes an interactive service from the oSparc platform

    Stops and removes an interactive service from the oSparc platform # noqa: E501

    :param service_uuid: The uuid of the service to stop
    :type service_uuid: str

    :rtype: None
    """
    try:
      producer.stop_service(service_uuid)
    except exceptions.ServiceNotFoundError as err:
      raise web_exceptions.HTTPNotFound(reason=str(err))
    except exceptions.DirectorException as err:
      raise web_exceptions.HTTPInternalServerError(reason=str(err))
    
    return {"status":204}

async def list_computational_services_get():  # noqa: E501
    """Lists available computational services in the oSparc platform

    Lists available computational services in the oSparc platform # noqa: E501


    :rtype: List[ServiceDescription]
    """
    try:
        repos = registry_proxy.list_computational_services()
        return repos
    except exceptions.DirectorException as err:
      raise web_exceptions.HTTPInternalServerError(reason=str(err))
