#pylint: disable=W0621
import asyncio
import logging

import pytest
import requests
from pytest_docker import docker_ip, docker_services  # pylint:disable=W0611

from simcore_service_storage_sdk import ApiClient, Configuration, UsersApi
from simcore_service_storage_sdk.rest import ApiException

log = logging.getLogger(__name__)

def is_responsive(url, code=200):
    try:
        if requests.get(url).status_code == code:
            return True
    except Exception:  #pylint: disable=W0703
        logging.exception("Connection to storage failed")
        return False

    return False

@pytest.fixture(scope="module")
def storage(docker_ip, docker_services): 
    host = docker_ip
    port = docker_services.port_for('storage', 8080)
    url = "http://{}:{}".format(host, port)
    # Wait until we can connect
    docker_services.wait_until_responsive(
        check=lambda: is_responsive(url, 404),
        timeout=30.0,
        pause=1.0,
    )
    
    yield url
    # cleanup
    
@pytest.fixture()    
async def storage_api(storage):
    config = Configuration()
    config.host = "{}/{}".format(storage, "v0")
    client = ApiClient(config)
    api = UsersApi(client)
    yield api
    
