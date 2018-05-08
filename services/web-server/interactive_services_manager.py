""" Manages lifespan of interactive services.

"""
# pylint: disable=W0703
# pylint: disable=C0111
import director_proxy

__RUNNING_SERVICES = dict()


def session_connect(session_id):
    __RUNNING_SERVICES[session_id] = list()


def session_disconnected(session_id):
    # let's stop all running interactive services
    running_services_for_session = __RUNNING_SERVICES[session_id]
    for service_session_uuid in running_services_for_session:
        director_proxy.stop_service(service_session_uuid)
    __RUNNING_SERVICES[session_id] = list()


def retrieve_list_of_services():
    try:
        return director_proxy.retrieve_interactive_services()
    except Exception as err:
        return "Failed retrieving list of services: " + str(err)


def start_service(session_id, service_name, service_uuid):
    try:
        result = director_proxy.start_service(service_name, service_uuid)
        __RUNNING_SERVICES[session_id].append(service_uuid)
        return result
    except Exception as err:
        return "Failed starting service " + service_name + ": " + str(err)


def stop_service(session_id, service_uuid):
    try:
        result = director_proxy.stop_service(service_uuid)
        __RUNNING_SERVICES[session_id].remove(service_uuid)
        return result
    except Exception as err:
        return "Failed stopping service " + str(err)
