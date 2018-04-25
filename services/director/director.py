import os
import json
import docker
import logging

from flask import Flask, request
from flask import abort
import registry_proxy
import producer

app = Flask(__name__)


@app.route('/')
def hello_world():
    return 'Hello I\'m alive!'

@app.route('/list_interactive_services', methods=['GET'])
def list_interactive_services():
    # get the services repos
    list_of_interactive_repos = registry_proxy.retrieve_list_of_repos_with_interactive_services()
    # some services may have several parts, fuse these
    # the syntax of services are simcore/services/%SERVICENAME%/...
    list_of_interactive_services = []
    [list_of_interactive_services.append(registry_proxy.get_service_name(i)) for i in list_of_interactive_repos if not list_of_interactive_services.count(registry_proxy.get_service_name(i))]

    #list_of_interactive_services = [registry_proxy.retrieve_list_of_images_in_repo(repo) for repo in list_of_interactive_repos]

    return json.dumps(list_of_interactive_services)

@app.route('/start_service', methods=['POST'])
def start_service():
    # check syntax
    if not request.json or not 'service_name' in request.json or not 'service_uuid' in request.json:
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
    except Exception as e:
        logging.exception(e)
        abort(500)
    
    

@app.route('/stop_service', methods=['POST'])
def stop_service():
    # check syntax
    if not request.json or not 'service_uuid' in request.json:
        abort(400)
    service_uuid = request.json['service_uuid']
    try:
        producer.stop_service(service_uuid)
        return json.dumps('service stopped'), 201
    except Exception as e:
        logging.exception(e)
        abort(500)

if __name__ == "__main__":
    registry_proxy.setup_registry_connection()    

    app.run(host='0.0.0.0', debug=False, port=8001, threaded=True)
