# pylint:disable=unused-import
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import time

import docker
import pytest
import tenacity

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def docker_registry():
    # run the registry outside of the stack
    docker_client = docker.from_env()
    container = docker_client.containers.run("registry:2",
        ports={"5000":"5000"},
        environment=["REGISTRY_STORAGE_DELETE_ENABLED=true"],
        restart_policy={"Name":"always"},
        detach=True
    )
    host = "127.0.0.1"
    port = 5000
    url = "{host}:{port}".format(host=host, port=port)
    # Wait until we can connect
    assert _wait_till_registry_is_responsive(url)

    # test the registry
    docker_client = docker.from_env()
    # get the hello world example from docker hub
    hello_world_image = docker_client.images.pull("hello-world","latest")
    # login to private registry
    docker_client.login(registry=url, username="simcore")
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

    yield url

    container.stop()

    while docker_client.containers.list(filters={"name": container.name}):
        time.sleep(1)

@tenacity.retry(wait=tenacity.wait_fixed(1), stop=tenacity.stop_after_delay(60))
def _wait_till_registry_is_responsive(url):
    docker_client = docker.from_env()
    docker_client.login(registry=url, username="simcore")
    return True
