import logging

from aiohttp import web_exceptions

from simcore_service_director import (config, exceptions, producer,
                                      registry_proxy)

from . import api_converters, node_validator
from .generated_code.models import (HealthCheck, HealthCheckEnveloped,
                                    NodeMetaV0, Response204Enveloped,
                                    RunningService, RunningServiceEnveloped,
                                    ServicesEnveloped)

_LOGGER = logging.getLogger(__name__)

async def root_get(request):  # pylint:disable=unused-argument
    service_health = HealthCheck(name="simcore-service-director", status="SERVICE_RUNNING", api_version="1.0.0", version="1.0.0")
    return HealthCheckEnveloped(data=service_health, status=200).to_dict()

async def services_get(request, service_type=None):  # pylint:disable=unused-argument
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

def list_services(list_service_fct):
    services = list_service_fct()
    if config.CONVERT_OLD_API:
        services = [api_converters.convert_service_from_old_api(x) for x in services]
    services = node_validator.validate_nodes(services)
    
    service_descs = [NodeMetaV0.from_dict(x) for x in services]
    return service_descs


async def running_interactive_services_post(request, service_key, service_uuid, service_tag=None):  # pylint:disable=unused-argument
    try:
        service = producer.start_service(service_key, service_tag, service_uuid)
        running_service = RunningService.from_dict(service)
        return RunningServiceEnveloped(data=running_service, status=201).to_dict()
    except exceptions.ServiceNotAvailableError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except exceptions.ServiceUUIDInUseError as err:
        raise web_exceptions.HTTPConflict(reason=str(err))
    except exceptions.RegistryConnectionError as err:
        raise web_exceptions.HTTPUnauthorized(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

async def running_interactive_services_get(request, service_uuid):  # pylint:disable=unused-argument
    try:
        producer.is_service_up(service_uuid)
    except exceptions.ServiceUUIDNotFoundError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

    return Response204Enveloped(status=204).to_dict()

async def running_interactive_services_delete(request, service_uuid):  # pylint:disable=unused-argument
    try:
        producer.stop_service(service_uuid)
    except exceptions.ServiceUUIDNotFoundError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

    return Response204Enveloped(status=204).to_dict()
