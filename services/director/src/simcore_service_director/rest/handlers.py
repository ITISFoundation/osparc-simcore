# pylint:disable=too-many-arguments

import logging
from typing import Optional

import pkg_resources
import yaml
from aiohttp import web, web_exceptions
from simcore_service_director import exceptions, producer, registry_proxy, resources

log = logging.getLogger(__name__)


async def root_get(
    request: web.Request,
) -> web.Response:
    log.debug("Client does root_get request %s", request)
    distb = pkg_resources.get_distribution("simcore-service-director")
    with resources.stream(resources.RESOURCE_OPEN_API) as file_ptr:
        api_dict = yaml.safe_load(file_ptr)

    service_health = dict(
        name=distb.project_name,
        status="SERVICE_RUNNING",
        api_version=api_dict["info"]["version"],
        version=distb.version,
    )
    return web.json_response(data=dict(data=service_health))


async def services_get(
    request: web.Request, service_type: Optional[str] = None
) -> web.Response:
    log.debug(
        "Client does services_get request %s with service_type %s",
        request,
        service_type,
    )
    try:
        services = []
        if not service_type:
            services = await registry_proxy.list_services(
                request.app, registry_proxy.ServiceType.ALL
            )
        elif "computational" in service_type:
            services = await registry_proxy.list_services(
                request.app, registry_proxy.ServiceType.COMPUTATIONAL
            )
        elif "interactive" in service_type:
            services = await registry_proxy.list_services(
                request.app, registry_proxy.ServiceType.DYNAMIC
            )
        # NOTE: the validation is done in the catalog. This entrypoint IS and MUST BE only used by the catalog!!
        # NOTE2: the catalog will directly talk to the registry see case #2165 [https://github.com/ITISFoundation/osparc-simcore/issues/2165]
        # services = node_validator.validate_nodes(services)
        return web.json_response(data=dict(data=services))
    except exceptions.RegistryConnectionError as err:
        raise web_exceptions.HTTPUnauthorized(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))


async def services_by_key_version_get(
    request: web.Request, service_key: str, service_version: str
) -> web.Response:
    log.debug(
        "Client does services_get request %s with service_key %s, service_version %s",
        request,
        service_key,
        service_version,
    )
    try:
        services = [
            await registry_proxy.get_image_details(
                request.app, service_key, service_version
            )
        ]
        return web.json_response(data=dict(data=services))
    except exceptions.ServiceNotAvailableError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except exceptions.RegistryConnectionError as err:
        raise web_exceptions.HTTPUnauthorized(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))


async def get_service_labels(
    request: web.Request, service_key: str, service_version: str
) -> web.Response:
    log.debug(
        "Retrieving service labels %s with service_key %s, service_version %s",
        request,
        service_key,
        service_version,
    )
    try:
        service_labels = await registry_proxy.get_image_labels(
            request.app, service_key, service_version
        )
        return web.json_response(data=dict(data=service_labels))
    except exceptions.ServiceNotAvailableError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except exceptions.RegistryConnectionError as err:
        raise web_exceptions.HTTPUnauthorized(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))


# GET /service_extras/{service_key}/{service_version}
async def service_extras_by_key_version_get(
    request: web.Request, service_key: str, service_version: str
) -> web.Response:
    log.debug(
        "Client does service_extras_by_key_version_get request %s with service_key %s, service_version %s",
        request,
        service_key,
        service_version,
    )
    try:
        service_extras = await registry_proxy.get_service_extras(
            request.app, service_key, service_version
        )
        return web.json_response(data=dict(data=service_extras))
    except exceptions.ServiceNotAvailableError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except exceptions.RegistryConnectionError as err:
        raise web_exceptions.HTTPUnauthorized(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))


async def running_interactive_services_list_get(
    request: web.Request, user_id: str, project_id: str
) -> web.Response:
    log.debug(
        "Client does running_interactive_services_list_get request %s, user_id %s, project_id %s",
        request,
        user_id,
        project_id,
    )
    try:
        service = await producer.get_services_details(request.app, user_id, project_id)
        return web.json_response(data=dict(data=service), status=200)
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))


async def running_interactive_services_post(
    request: web.Request,
    user_id: str,
    project_id: str,
    service_key: str,
    service_uuid: str,
    service_tag: str,
    service_basepath: str,
) -> web.Response:
    # NOTE: servicelib is not present here
    request_simcore_user_agent = request.headers.get("X-Simcore-User-Agent", "")
    log.debug(
        "Client does running_interactive_services_post request %s with user_id %s, project_id %s, service %s:%s, service_uuid %s, service_basepath %s, request_simcore_user_agent %s",
        request,
        user_id,
        project_id,
        service_key,
        service_tag,
        service_uuid,
        service_basepath,
        request_simcore_user_agent,
    )
    try:
        service = await producer.start_service(
            request.app,
            user_id,
            project_id,
            service_key,
            service_tag,
            service_uuid,
            service_basepath,
            request_simcore_user_agent,
        )
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


async def running_interactive_services_get(
    request: web.Request, service_uuid: str
) -> web.Response:
    log.debug(
        "Client does running_interactive_services_get request %s with service_uuid %s",
        request,
        service_uuid,
    )
    try:
        service = await producer.get_service_details(request.app, service_uuid)
        return web.json_response(data=dict(data=service), status=200)
    except exceptions.ServiceUUIDNotFoundError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except Exception as err:
        raise web_exceptions.HTTPInternalServerError(reason=str(err))


async def running_interactive_services_delete(
    request: web.Request, service_uuid: str, save_state: Optional[bool] = True
) -> web.Response:
    log.debug(
        "Client does running_interactive_services_delete request %s with service_uuid %s",
        request,
        service_uuid,
    )
    try:
        await producer.stop_service(request.app, service_uuid, save_state)

    except exceptions.ServiceUUIDNotFoundError as err:
        raise web_exceptions.HTTPNotFound(reason=str(err))
    except Exception as err:
        # server errors are logged (>=500)
        log.exception(
            "Failed to delete dynamic service %s (save_state=%s)",
            service_uuid,
            save_state,
        )
        raise web_exceptions.HTTPInternalServerError(reason=str(err))

    return web.json_response(status=204)
