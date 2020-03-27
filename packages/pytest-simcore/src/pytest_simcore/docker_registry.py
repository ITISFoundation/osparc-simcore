# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import logging
import os
import time
from typing import Dict

import docker
import pytest
import tenacity

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def docker_registry(keep_docker_up: bool) -> str:
    # run the registry outside of the stack
    docker_client = docker.from_env()
    # try to login to private registry
    host = "127.0.0.1"
    port = 5000
    url = "{host}:{port}".format(host=host, port=port)
    container = None
    try:
        docker_client.login(registry=url, username="simcore")
        container = docker_client.containers.list({"name": "pytest_registry"})[0]
    except Exception:  # pylint: disable=broad-except
        print("Warning: docker registry is already up!")
        container = docker_client.containers.run(
            "registry:2",
            ports={"5000": "5000"},
            name="pytest_registry",
            environment=["REGISTRY_STORAGE_DELETE_ENABLED=true"],
            restart_policy={"Name": "always"},
            detach=True,
        )

        # Wait until we can connect
        assert wait_till_registry_is_responsive(url)

    # get the hello world example from docker hub
    hello_world_image = docker_client.images.pull("hello-world", "latest")
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

    # necessary for old school configs
    os.environ["REGISTRY_URL"] = url
    os.environ["REGISTRY_USER"] = "simcore"
    os.environ["REGISTRY_PW"] = ""

    yield url

    if not keep_docker_up:
        container.stop()
        container.remove(force=True)

        while docker_client.containers.list(filters={"name": container.name}):
            time.sleep(1)


@tenacity.retry(
    wait=tenacity.wait_fixed(2),
    stop=tenacity.stop_after_delay(20),
    before_sleep=tenacity.before_sleep_log(log, logging.INFO),
    reraise=True,
)
def wait_till_registry_is_responsive(url: str) -> bool:
    docker_client = docker.from_env()
    docker_client.login(registry=url, username="simcore")
    return True


# pull from itisfoundation/sleeper and push into local registry
@pytest.fixture(scope="session")
def sleeper_service(docker_registry: str) -> Dict[str, str]:
    """ Adds a itisfoundation/sleeper in docker registry

    """
    client = docker.from_env()
    TAG = "1.0.0"
    image = client.images.pull("itisfoundation/sleeper", tag=TAG)
    assert not image is None
    repo = f"{docker_registry}/simcore/services/comp/itis/sleeper:{TAG}"
    assert image.tag(repo) == True
    client.images.push(repo)
    image = client.images.pull(repo)
    assert image
    image_labels = image.labels

    yield {
        "schema": {
            key[len("io.simcore.") :]: json.loads(value)[key[len("io.simcore.") :]]
            for key, value in image_labels.items()
            if key.startswith("io.simcore.")
        },
        "image": {"name": "simcore/services/comp/itis/sleeper", "tag": TAG},
    }


@pytest.fixture(scope="session")
def jupyter_service(docker_registry: str) -> Dict[str, str]:
    """ Adds a itisfoundation/jupyter-base-notebook in docker registry

    """
    client = docker.from_env()

    # TODO: cleanup

    # pull from dockerhub
    reponame, tag = "itisfoundation/jupyter-base-notebook:2.13.0".split(":")
    image = client.images.pull(reponame, tag=tag)
    assert not image is None

    # push to fixture registry (services/{dynamic|comp})
    image_name = reponame.split("/")[-1]
    repo = f"{docker_registry}/simcore/services/dynamic/{image_name}:{tag}"
    assert image.tag(repo) == True
    client.images.push(repo)

    # check
    image = client.images.pull(repo)
    assert image
    image_labels = image.labels

    yield {
        "schema": {
            key[len("io.simcore.") :]: json.loads(value)[key[len("io.simcore.") :]]
            for key, value in image_labels.items()
            if key.startswith("io.simcore.")
        },
        "image": {"name": f"simcore/services/dynamic/{image_name}", "tag": f"{tag}"},
    }
