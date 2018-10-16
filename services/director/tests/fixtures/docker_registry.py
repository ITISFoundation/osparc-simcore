import logging

import docker
import pytest
from pytest_docker import docker_ip, docker_services  # pylint:disable=W0611

log = logging.getLogger(__name__)

def is_responsive(url):
    try:
        docker_client = docker.from_env()
        docker_client.login(registry=url, username="test")
    except docker.errors.APIError:
        log.exception("Error while loggin into the registry")
        return False
    return True

# pylint:disable=redefined-outer-name
@pytest.fixture(scope="session")
def docker_registry(docker_ip, docker_services): 
    host = docker_ip
    port = docker_services.port_for('registry', 5000)
    url = "{host}:{port}".format(host=host, port=port)
    # Wait until we can connect
    docker_services.wait_until_responsive(
        check=lambda: is_responsive(url),
        timeout=30.0,
        pause=1.0,
    )

    # test the registry
    try:
        docker_client = docker.from_env()
        # get the hello world example from docker hub
        hello_world_image = docker_client.images.pull("hello-world","latest")
        # login to private registry
        docker_client.login(registry=url, username="test")
        # tag the image
        repo = url + "/hello-world:dev"
        assert hello_world_image.tag(repo) == True
        # push the image to the private registry
        docker_client.images.push(repo)
        # wipe the images
        docker_client.images.remove(image="hello-world:latest")
        docker_client.images.remove(image=hello_world_image.id)
        # pull the image from the private registry
        private_image = docker_client.images.pull(repo)
        docker_client.images.remove(image=private_image.id)
    except docker.errors.APIError:
        log.exception("Unexpected docker API error")
        raise

    yield url
    print("teardown docker registry")
