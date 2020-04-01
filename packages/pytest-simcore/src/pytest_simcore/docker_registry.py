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


# ********************************************************* Services ***************************************


def _pull_push_service(pull_key: str, push_key: str, tag: str) -> Dict[str, str]:
    client = docker.from_env()
    # pull image from original location
    image = client.images.pull(pull_key, tag=tag)
    assert image, f"image {pull_key}:{tag} not pulled!"
    # tag image
    new_image_tag = f"{push_key}:{tag}"
    assert image.tag(new_image_tag) == True
    # push the image to the new location
    client.images.push(new_image_tag)

    # return image io.simcore.* labels
    image_labels = image.labels
    return {
        "schema": {
            key[len("io.simcore.") :]: json.loads(value)[key[len("io.simcore.") :]]
            for key, value in image_labels.items()
            if key.startswith("io.simcore.")
        },
        "image": {"name": push_key[(push_key.find("/") + 1) :], "tag": tag},
    }


# pull from itisfoundation/sleeper and push into local registry
@pytest.fixture(scope="session")
def sleeper_service(docker_registry: str) -> Dict[str, str]:
    """ Adds a itisfoundation/sleeper in docker registry

    """
    return _pull_push_service(
        "itisfoundation/sleeper",
        f"{docker_registry}/simcore/services/comp/itis/sleeper",
        "1.0.0",
    )


@pytest.fixture(scope="session")
def jupyter_service(docker_registry: str) -> Dict[str, str]:
    """ Adds a itisfoundation/jupyter-base-notebook in docker registry

    """
    return _pull_push_service(
        "itisfoundation/jupyter-base-notebook",
        f"{docker_registry}/simcore/services/dynamic/jupyter-base-notebook)",
        "2.13.0",
    )
