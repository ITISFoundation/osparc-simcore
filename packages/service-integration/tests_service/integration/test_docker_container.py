# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import docker
from service_integration.pytest_plugin.docker_integration import assert_container_runs


def test_run_container(
    validation_folders: dict,
    host_folders: dict,
    docker_container: docker.models.containers.Container,
):
    assert_container_runs(validation_folders, host_folders, docker_container)
