"""
    The director takes care of starting/stopping services.
"""
# pylint: disable=bare-except

import json
import logging

import producer
import registry_proxy
from flask import Flask, abort, request

_LOGGER = logging.getLogger(__name__)

# TODO: configure via command line or config file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s-%(lineno)d: %(message)s'
    )

APP = Flask(__name__)
registry_proxy.setup_registry_connection()

@APP.route('/')
def hello_world():
    """ Routing to test that the director is online

    Returns:
        [type] -- [description]
    """
    return "<h1>Hoi zaeme! Salut les d'jeunz!</h1><h3>This is {} responding!</h2>".format(__name__)


@APP.route('/list_interactive_services', methods=['GET'])
def list_interactive_services():
    """[summary]

    Returns:
        [type] -- [description]
    """

    # get the services repos
    list_of_interactive_repos = registry_proxy.retrieve_list_of_repos_with_interactive_services()
    # some services may have several parts, fuse these
    # the syntax of services are simcore/services/%SERVICENAME%/...
    list_of_interactive_services = []
    for repo in list_of_interactive_repos:
        service_name = registry_proxy.get_service_name(repo)
        if service_name not in list_of_interactive_services:
            list_of_interactive_services.append(service_name)

    #list_of_interactive_services = [registry_proxy.retrieve_list_of_images_in_repo(repo) for repo in list_of_interactive_repos]

    return json.dumps(list_of_interactive_services)


@APP.route('/start_service', methods=['POST'])
def start_service():
    """[summary]

    Returns:
        [type] -- [description]
    """
    # check syntax
    if not request.json or not 'service_name' in request.json or not 'service_uuid' in request.json:
        _LOGGER.debug("Rejected start_service request: %s", request.json)
        abort(400)

    # get required parameters
    service_name = request.json['service_name']
    uuid = request.json['service_uuid']

    # get optional tag parameter
    if 'tag' in request.json:
        service_tag = request.json['tag']
    else:
        service_tag = 'latest'

    try:
        return producer.start_service(service_name, service_tag, uuid), 201
    except:
        _LOGGER.exception("Failed to start service %s:%s", service_name, service_tag)
        abort(500)


@APP.route('/stop_service', methods=['POST'])
def stop_service():
    """[summary]

    Returns:
        [type] -- [description]
    """

    # check syntax
    if not request.json or not 'service_uuid' in request.json:
        abort(400)
    service_uuid = request.json['service_uuid']
    try:
        producer.stop_service(service_uuid)
        return json.dumps('service stopped'), 201
    except:
        _LOGGER.exception("Failed to stop service")
        abort(500)


if __name__ == "__main__":
    APP.run(host='0.0.0.0', debug=False, port=8001, threaded=True)
