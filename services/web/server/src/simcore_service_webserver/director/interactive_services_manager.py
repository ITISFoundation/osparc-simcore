""" Manages lifespan of interactive services.

    - uses director's client-sdk to communicate with the director service

"""
# pylint: disable=W0703
# pylint: disable=C0111
import logging
from typing import Dict
from simcore_director_sdk.rest import ApiException

from . import director_sdk

log = logging.getLogger(__file__)

# TODO: cannot scale server! Use server.session instead or delegate to a director?
__RUNNING_SERVICES = dict()


def session_connect(user_id:str):
    __RUNNING_SERVICES[user_id] = list()


async def session_disconnected(user_id:str):
    """  Stops all running services when session disconnects

    """
    log.debug("Session disconnection of session %s", user_id)
    try:
        director = director_sdk.get_director()
        # let's stop all running interactive services
        running_services_for_session = __RUNNING_SERVICES[user_id]
        for service_session_uuid in running_services_for_session:
            await director.running_interactive_services_delete(service_session_uuid)
        __RUNNING_SERVICES[user_id] = list()
    except ApiException as exc:
        log.exception("Api Error while accessing director")
        return {"data": exc.reason, "status":exc.status}
    except Exception:
        log.exception("Unexpected error")
        raise

async def retrieve_list_of_services():
    log.debug("Retrieving list of services")
    try:
        director = director_sdk.get_director()
        services = await director.services_get(service_type="interactive")
        return services.to_dict()
    except ApiException as exc:
        log.exception("Api Error while accessing director")
        return {"data": exc.reason, "status":exc.status}
    except Exception:
        log.exception("Unexpected error")
        raise


async def start_service(user_id:str, service_key:str, service_uuid:str, service_version:str) -> Dict:
    log.debug("User %s starting service %s:%s with uuid %s", user_id, service_key, service_version, service_uuid)
    try:
        director = director_sdk.get_director()
        result = await director.running_interactive_services_post(user_id, service_key, service_uuid, service_tag=service_version)
        log.debug("Started service result: %s", result)
        __RUNNING_SERVICES[user_id].append(service_uuid)
        return result.to_dict()
    except ApiException as exc:
        log.exception("Api Error while accessing director")
        return {"data": exc.reason, "status":exc.status}
    except Exception:
        log.exception("Unexpected error")
        raise


async def stop_service(user_id, service_uuid):
    """ Stops and removes a running service

        :param str service_uuid: The uuid to assign the service with (required)
    """
    log.debug("Stopping service with uuid %s", service_uuid)
    try:
        director = director_sdk.get_director()
        await director.running_interactive_services_delete(service_uuid)
        __RUNNING_SERVICES[user_id].remove(service_uuid)
        log.debug("Service stopped")
    except ApiException as exc:
        log.exception("Api Error while accessing director")
        return {"data": exc.reason, "status":exc.status}
    except Exception:
        log.exception("Unexpected error")
        raise
