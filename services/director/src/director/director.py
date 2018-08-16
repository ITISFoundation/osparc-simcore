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
    _LOGGER.debug("received hello to the people")
    return "<h1>Hoi zaeme! Salut les d'jeunz!</h1><h3>This is {} responding!</h2>".format(__name__)


@APP.route('/list_interactive_services', methods=['GET'])
def list_interactive_services():
    """returns the list of interactive services

    Returns:
        json -- {service_name: {repos: [/simcore/service/], details: []}}
    """
    _LOGGER.debug("received call to list of interactive services")
    # get the services repos
    list_of_interactive_repos = registry_proxy.retrieve_list_of_repos_with_interactive_services()
    #list_of_interactive_services = [registry_proxy.retrieve_list_of_images_in_repo(repo) for repo in list_of_interactive_repos]
    _LOGGER.debug("retrieved list of interactive services %s", list_of_interactive_repos)
    return json.dumps(list_of_interactive_repos)


@APP.route('/start_service', methods=['POST'])
def start_service():
    """[summary]

    Returns:
        [type] -- [description]
    """
    _LOGGER.debug("received call to start service with %s", request.json)
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
    _LOGGER.debug("Asked to start service %s with uuid %s and tag %s", service_name, uuid, service_tag)
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
    _LOGGER.debug("received call to stop service with %s", request.json)
    # check syntax
    if not request.json or not 'service_uuid' in request.json:
        abort(400)
    service_uuid = request.json['service_uuid']
    _LOGGER.debug("Asked to stop service with uuid %s", service_uuid)
    try:
        producer.stop_service(service_uuid)
        return json.dumps('service stopped'), 201
    except:
        _LOGGER.exception("Failed to stop service")
        abort(500)

@APP.route('/list_computational_services', methods=['GET'])
def list_computational_services():
    repos = registry_proxy.list_computational_services()

    return json.dumps(repos)

if __name__ == "__main__":
    APP.run(host='0.0.0.0', debug=False, port=8001, threaded=True)
