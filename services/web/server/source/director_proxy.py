"""
This module is responsible for communicating with the director entity
"""

# pylint: disable=C0111
import sys
import os
import logging
import json

from requests import RequestException, Session

_LOGGER = logging.getLogger(__name__)

_SESSION = Session()


def director_request(path, method="GET", data=dict()):
    api_url = os.environ.get('DIRECTOR_HOST', '0.0.0.0') + \
        ':' + os.environ.get('DIRECTOR_PORT', '8001') + '/' + path
    try:
        if len(data) == 0:
            request_result = getattr(_SESSION, method.lower())(api_url)
        else:
            request_result = getattr(
                _SESSION, method.lower())(api_url, json=data)

        # TODO: we should only check for success (e.g. 201), and handle any error in a dedicated function
        if request_result.status_code == 400:
            raise Exception('Return Code was 400, Bad request, malformed syntax!')
        if request_result.status_code == 401:
            raise Exception('Return Code was 401, Authentication required / not successful!')
        elif request_result.status_code == 404:
            raise Exception('Return code 404, Unknown URL used!')
        elif request_result.status_code == 500:
            raise Exception('Return code 500, Internal Server Error!')
        else:
            _LOGGER.warning('return ok: %s', request_result.json())
            return request_result
    except RequestException as err:
        raise RequestException("Problem during connection to director" + str(e))


def retrieve_interactive_services():
    request = director_request('list_interactive_services')
    return request.json()


def start_service(service_name, service_uuid):
    request = director_request('start_service', method='POST', data={
                               'service_name': service_name, 'service_uuid': str(service_uuid)})
    return request.json()


def stop_service(service_uuid):
    request = director_request('stop_service', method='POST', data={
                               'service_uuid': str(service_uuid)})
    return request.json()
