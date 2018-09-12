import logging

import pkg_resources
import yaml
from aiohttp import web_exceptions

from simcore_service_director import (
    config, 
    exceptions, 
    producer,
    registry_proxy
    )

from . import api_converters, node_validator
from .generated_code.models import (HealthCheck, HealthCheckEnveloped,
                                    NodeMetaV0, Response204Enveloped,
                                    RunningService, RunningServiceEnveloped,
                                    ServicesEnveloped)

_LOGGER = logging.getLogger(__name__)

async def root_get(request):  # pylint:disable=unused-argument
    _LOGGER.debug("Client does root_get request %s", request)
    distb = pkg_resources.get_distribution('simcore-service-director')
    api_path = config.OPEN_API_BASE_FOLDER / config.OPEN_API_SPEC_FILE
    with api_path.open() as file_ptr:
        api_dict = yaml.load(file_ptr)

    service_health = HealthCheck(
        name=distb.project_name, 
        status="SERVICE_RUNNING", 
        api_version=api_dict["info"]["version"], 
        version=distb.version)
    return HealthCheckEnveloped(data=service_health, status=200).to_dict()

async def services_get(request, service_type=None):  # pylint:disable=unused-argument
    _LOGGER.debug("Client does services_get request %s with service_type %s", request, service_type)
    try:
        services = []
        if not service_type or "computational" in service_type:
            services.extend(list_services(registry_proxy.list_computational_services))
        
        if not service_type or "interactive" in service_type:
            services.extend(list_services(registry_proxy.list_interactive_services))
        return ServicesEnveloped(data=services, status=200).to_dict()
    except exceptions.RegistryConnectionError as err:
        raise web_exceptions.HTTPUnauthorized(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

async def services_by_key_version_get(request, service_key, service_version):  # pylint:disable=unused-argument
    _LOGGER.debug("Client does services_get request %s with service_key %s, service_version %s", request, service_key, service_version)
    try:
        services = [registry_proxy.get_service_details(service_key, service_version)]    
        if config.CONVERT_OLD_API:
            services = [api_converters.convert_service_from_old_api(x) for x in services]    
        return ServicesEnveloped(data=services, status=200).to_dict()
    except exceptions.ServiceNotAvailableError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except exceptions.RegistryConnectionError as err:
        raise web_exceptions.HTTPUnauthorized(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

def list_services(list_service_fct):    
    services = list_service_fct()
    if config.CONVERT_OLD_API:
        services = [api_converters.convert_service_from_old_api(x) for x in services]
    services = node_validator.validate_nodes(services)
    
    service_descs = [NodeMetaV0.from_dict(x) for x in services]
    return service_descs


async def running_interactive_services_post(request, service_key, service_uuid, service_tag):  # pylint:disable=unused-argument
    _LOGGER.debug("Client does running_interactive_services_post request %s with service_key %s, service_uuid %s and service_tag %s", 
                request, service_key, service_uuid, service_tag)
    
    try:
        service = producer.start_service(service_key, service_tag, service_uuid)
        running_service = RunningService.from_dict(service)
        return RunningServiceEnveloped(data=running_service, status=201).to_dict()
    except exceptions.ServiceStartTimeoutError as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))
    except exceptions.ServiceNotAvailableError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except exceptions.ServiceUUIDInUseError as err:
        raise web_exceptions.HTTPConflict(reason=str(err))
    except exceptions.RegistryConnectionError as err:
        raise web_exceptions.HTTPUnauthorized(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

async def running_interactive_services_get(request, service_uuid):  # pylint:disable=unused-argument
    _LOGGER.debug("Client does running_interactive_services_get request %s with service_uuid %s", request, service_uuid)
    try:
        producer.is_service_up(service_uuid)
    except exceptions.ServiceUUIDNotFoundError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

    return Response204Enveloped(status=204).to_dict()

async def running_interactive_services_delete(request, service_uuid):  # pylint:disable=unused-argument
    _LOGGER.debug("Client does running_interactive_services_delete request %s with service_uuid %s", request, service_uuid)
    try:
        producer.stop_service(service_uuid)
    except exceptions.ServiceUUIDNotFoundError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

    return Response204Enveloped(status=204).to_dict()
