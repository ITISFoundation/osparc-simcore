#pylint: disable=W0621
import logging
import asyncio
import pytest
from pytest_docker import docker_ip, docker_services  # pylint:disable=W0611
from simcore_service_storage_sdk import ApiClient, UsersApi, Configuration
from simcore_service_storage_sdk.rest import ApiException

log = logging.getLogger(__name__)

def is_responsive(config):
    try:
        client = ApiClient(config)
        api = UsersApi(client)        
        loop = asyncio.get_event_loop()
        loop.run_until_complete(api.health_check())
        return True
    except Exception:  #pylint: disable=W0703
        logging.exception("Connection to storage failed")
        return False

    return False

@pytest.fixture(scope="module")
def storage_client(docker_ip, docker_services): 
    host = docker_ip
    port = docker_services.port_for('storage', 8080)
    cfg = Configuration()
    cfg.host = cfg.host.format(
        host=host,
        port=port,
        basePath="v0"
    )    
    # Wait until we can connect
    docker_services.wait_until_responsive(
        check=lambda: is_responsive(cfg),
        timeout=30.0,
        pause=1.0,
    )

    connection_ok = False
    try:
        client = ApiClient(cfg)        
        connection_ok = True
    except ApiException:
        log.exception("could not connect to storage service")

    assert connection_ok
    
    yield client
    # cleanup


@pytest.fixture
def storage_users_api(storage_client):
    api = UsersApi(storage_client)
    yield api
    # teardown