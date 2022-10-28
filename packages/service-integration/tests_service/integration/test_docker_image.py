# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import docker
from service_integration.pytest_plugin.docker_integration import (
    assert_docker_io_simcore_labels_against_files,
    assert_validate_docker_io_simcore_labels,
)


def test_docker_io_simcore_labels_against_files(
    docker_image: docker.models.images.Image, metadata_labels: dict
):
    assert_docker_io_simcore_labels_against_files(docker_image, metadata_labels)


def test_validate_docker_io_simcore_labels(
    docker_image: docker.models.images.Image, osparc_service_labels_jsonschema: dict
):
    assert_validate_docker_io_simcore_labels(
        docker_image, osparc_service_labels_jsonschema
    )
