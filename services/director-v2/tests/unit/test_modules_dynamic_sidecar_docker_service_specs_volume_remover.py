# pylint: disable=redefined-outer-name
import pytest
from pydantic import parse_obj_as
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs.volume_remover import (
    DockerVersion,
)


@pytest.mark.parametrize(
    "docker_version",
    [
        "20.10.17",
        "20.10.17+azure-1-dind",  # github workers
        "20.10.17.",
        "20.10.17asdjasjsaddas",
    ],
)
def test_docker_version_strips_unwanted(docker_version: str):
    assert parse_obj_as(DockerVersion, docker_version) == "20.10.17"


@pytest.mark.parametrize(
    "invalid_docker_version",
    [
        "nope",
        ".20.10.17.",
        ".20.10.17",
    ],
)
def test_docker_version_invalid(invalid_docker_version: str):
    with pytest.raises(ValueError):
        parse_obj_as(DockerVersion, invalid_docker_version)
