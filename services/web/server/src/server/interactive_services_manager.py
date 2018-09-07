""" Manages lifespan of interactive services.

"""
# pylint: disable=W0703
# pylint: disable=C0111
import logging

from simcore_director_sdk.rest import ApiException

from . import director_sdk

_LOGGER = logging.getLogger(__file__)

# TODO: cannot scale server! Use server.session instead or delegate to a director?
__RUNNING_SERVICES = dict()


def session_connect(session_id):
    __RUNNING_SERVICES[session_id] = list()


async def session_disconnected(session_id):
    _LOGGER.debug("Session disconnection of session %s", session_id)
    try:
        director = director_sdk.get_director()
        # let's stop all running interactive services
        running_services_for_session = __RUNNING_SERVICES[session_id]
        for service_session_uuid in running_services_for_session:
            await director.running_interactive_services_delete(service_session_uuid)
        __RUNNING_SERVICES[session_id] = list()
    except ApiException as exc:
        _LOGGER.exception("Api Error while accessing director")
        return {"data": exc.reason, "status":exc.status}
    except Exception:
        _LOGGER.exception("Unexpected error")
        raise

async def retrieve_list_of_services():
    _LOGGER.debug("Retrieving list of services")
    try:
        director = director_sdk.get_director()
        services = await director.services_get(service_type="interactive")
        return services.to_dict()
    except ApiException as exc:
        _LOGGER.exception("Api Error while accessing director")
        return {"data": exc.reason, "status":exc.status}
    except Exception:
        _LOGGER.exception("Unexpected error")
        raise


async def start_service(session_id, service_key, service_uuid, service_version=None):
    if not service_version:
        service_version = "latest"
    _LOGGER.debug("Starting service %s:%s with uuid %s", service_key, service_version, service_uuid)
    try:
        director = director_sdk.get_director()
        result = await director.running_interactive_services_post(service_key, service_uuid, service_tag=service_version)
        _LOGGER.debug("Started service result: %s", result)
        __RUNNING_SERVICES[session_id].append(service_uuid)
        return result.to_dict()
    except ApiException as exc:
        _LOGGER.exception("Api Error while accessing director")
        return {"data": exc.reason, "status":exc.status}
    except Exception:
        _LOGGER.exception("Unexpected error")
        raise


async def stop_service(session_id, service_uuid):
    _LOGGER.debug("Stopping service with uuid %s", service_uuid)
    try:
        director = director_sdk.get_director()
        await director.running_interactive_services_delete(service_uuid)
        __RUNNING_SERVICES[session_id].remove(service_uuid)
        _LOGGER.debug("Service stopped")
    except ApiException as exc:
        _LOGGER.exception("Api Error while accessing director")
        return {"data": exc.reason, "status":exc.status}
    except Exception:
        _LOGGER.exception("Unexpected error")
        raise
