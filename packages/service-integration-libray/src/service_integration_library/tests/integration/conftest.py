# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
from pathlib import Path

import pytest

import docker


@pytest.fixture
def docker_client() -> docker.DockerClient:
    return docker.from_env()


@pytest.fixture
def docker_image_key(docker_client: docker.DockerClient) -> str:
    image_key = "{{ cookiecutter.project_name.lower().replace(' ', '-') }}:"
    docker_images = [image for image in docker_client.images.list() if any(
        image_key in tag for tag in image.tags)]
    return docker_images[0].tags[0]


@pytest.fixture
def docker_image(docker_client: docker.DockerClient, docker_image_key: str) -> docker.models.images.Image:
    docker_image = docker_client.images.get(docker_image_key)
    assert docker_image
    return docker_image


def _is_gitlab_executor() -> bool:
    return "GITLAB_CI" in os.environ


@pytest.fixture
def temporary_path(tmp_path: Path) -> Path:
    if _is_gitlab_executor():
        # /builds is a path that is shared between the docker in docker container and the job builder container
        shared_path = Path(
            "/builds/{}/tmp".format(os.environ["CI_PROJECT_PATH"]))
        shared_path.mkdir(parents=True, exist_ok=True)
        return shared_path
    return tmp_path
