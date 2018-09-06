""" Manages lifespan of interactive services.

"""
# pylint: disable=W0703
# pylint: disable=C0111
import logging

from . import director_sdk

_LOGGER = logging.getLogger(__file__)

# TODO: cannot scale server! Use server.session instead or delegate to a director?
__RUNNING_SERVICES = dict()


def session_connect(session_id):
    __RUNNING_SERVICES[session_id] = list()


def session_disconnected(session_id):
    try:
        director = director_sdk.get_director()
        # let's stop all running interactive services
        running_services_for_session = __RUNNING_SERVICES[session_id]
        for service_session_uuid in running_services_for_session:
            director.running_interactive_services_delete(service_session_uuid)
        __RUNNING_SERVICES[session_id] = list()
    except Exception:
        _LOGGER.exception("Error when deleting all services")
        raise

def retrieve_list_of_services():    
    try:
        director = director_sdk.get_director()
        services = director.services_get(service_type="interactive")
        return services
    except Exception:
        _LOGGER.exception("Error while retrieving interactive services")
        raise


def start_service(session_id, service_key, service_uuid, service_version=None):
    if not service_version:
        service_version = "latest"
    try:
        director = director_sdk.get_director()
        _LOGGER.debug("Starting service %s", service_key)
        result = director.running_interactive_services_post(service_key, service_uuid, service_tag=service_version)
        _LOGGER.debug("Started service result: %s", result)
        __RUNNING_SERVICES[session_id].append(service_uuid)
        return result
    except Exception:
        _LOGGER.exception("Failed to start %s", service_key)
        raise


def stop_service(session_id, service_uuid):
    try:
        director = director_sdk.get_director()
        director.running_interactive_services_delete(service_uuid)
        __RUNNING_SERVICES[session_id].remove(service_uuid)
    except Exception:
        # FIXME: shouldn't I return a json??
        _LOGGER.exception("Failed to stop %s", service_uuid)
        raise
