import logging

import pkg_resources
import yaml
from aiohttp import web_exceptions, web
from simcore_service_director import (config, exceptions, producer,
                                      registry_proxy, resources)

from . import (api_converters, node_validator)

log = logging.getLogger(__name__)

async def root_get(request):  # pylint:disable=unused-argument
    log.debug("Client does root_get request %s", request)
    distb = pkg_resources.get_distribution('simcore-service-director')
    with resources.stream(resources.RESOURCE_OPEN_API) as file_ptr:
        api_dict = yaml.load(file_ptr)

    service_health = dict(
        name=distb.project_name,
        status="SERVICE_RUNNING",
        api_version=api_dict["info"]["version"],
        version=distb.version)
    return web.json_response(dict(data=service_health))

async def services_get(request, service_type=None):  # pylint:disable=unused-argument
    log.debug("Client does services_get request %s with service_type %s", request, service_type)
    try:
        services = []
        if not service_type or "computational" in service_type:
            services.extend(_list_services(registry_proxy.list_computational_services))
        if not service_type or "interactive" in service_type:
            services.extend(_list_services(registry_proxy.list_interactive_services))
        return web.json_response(data=dict(data=services))
    except exceptions.RegistryConnectionError as err:
        raise web_exceptions.HTTPUnauthorized(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

async def services_by_key_version_get(request, service_key, service_version):  # pylint:disable=unused-argument
    log.debug("Client does services_get request %s with service_key %s, service_version %s", request, service_key, service_version)
    try:
        services = [registry_proxy.get_service_details(service_key, service_version)]
        if config.CONVERT_OLD_API:
            services = [api_converters.convert_service_from_old_api(x) for x in services]
        return web.json_response(data=dict(data=services))
    except exceptions.ServiceNotAvailableError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except exceptions.RegistryConnectionError as err:
        raise web_exceptions.HTTPUnauthorized(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

def _list_services(list_service_fct):    
    services = list_service_fct()
    
    if config.CONVERT_OLD_API:
        services = [api_converters.convert_service_from_old_api(x) for x in services if not node_validator.is_service_valid(x)]
    services = node_validator.validate_nodes(services)
    return services

async def running_interactive_services_post(request, service_key, service_uuid, service_tag):  # pylint:disable=unused-argument
    log.debug("Client does running_interactive_services_post request %s with service_key %s, service_uuid %s and service_tag %s",
                request, service_key, service_uuid, service_tag)

    try:
        service = producer.start_service(service_key, service_tag, service_uuid)
        return web.json_response(data=dict(data=service), status=201)
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
    log.debug("Client does running_interactive_services_get request %s with service_uuid %s", request, service_uuid)
    try:
        producer.get_service_details(service_uuid)
    except exceptions.ServiceUUIDNotFoundError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

    return web.json_response(status=204)

async def running_interactive_services_delete(request, service_uuid):  # pylint:disable=unused-argument
    log.debug("Client does running_interactive_services_delete request %s with service_uuid %s", request, service_uuid)
    try:
        producer.stop_service(service_uuid)
    except exceptions.ServiceUUIDNotFoundError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

    return web.json_response(status=204)
