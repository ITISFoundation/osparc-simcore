#pylint: disable=W0621, unused-argument
import logging
import threading

import pytest
import requests
from pytest_docker import docker_ip, docker_services  # pylint:disable=W0611

log = logging.getLogger(__name__)

API_VERSION = 'v0'

def _fake_logger_while_building_storage():
    print("Hey Travis I'm still alive ... don't give up on me :-)")

def _is_responsive(url, code=200):
    try:
        if requests.get(url).status_code == code:
            return True
    except Exception:  #pylint: disable=W0703
        logging.exception("Connection to storage failed")
        return False

    return False

@pytest.fixture(scope="module")
def storage(bucket, engine, docker_ip, docker_services):
    host = docker_ip
    port = docker_services.port_for('storage', 8080)
    endpoint = "http://{}:{}/{}/".format(host, port, API_VERSION)

    # Wait until we can connect
    keep_alive_timer = threading.Timer(interval=60.0, function=_fake_logger_while_building_storage)
    keep_alive_timer.start()
    docker_services.wait_until_responsive(
        check=lambda: _is_responsive(endpoint, 200),
        timeout=30.0,
        pause=1.0,
    )
    keep_alive_timer.cancel()

    yield endpoint
    # cleanup
