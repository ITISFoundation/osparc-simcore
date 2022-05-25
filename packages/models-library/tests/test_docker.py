from models_library.docker import DockerImage
import pytest
from pydantic import parse_obj_as, ValidationError


@pytest.mark.parametrize(
    "example",
    [
        "nginx",
        "nginx:latest",
        "nginx:1.0.0",
        "nxing-me:1.0.0",
        "wiht/me:1.0.0",
        "nginx-me:latest",
        "this.is.ok:latest",
    ],
)
def test_docker_image(example: str) -> None:
    parse_obj_as(DockerImage, example)


@pytest.mark.parametrize(
    "example",
    [
        "NO-UPPER-CASE",
    ],
)
def test_docker_image_fails(example: str) -> None:
    with pytest.raises(ValidationError):
        parse_obj_as(DockerImage, example)
