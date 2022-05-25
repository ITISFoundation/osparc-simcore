# pylint: disable=redefined-outer-name
import pytest
from simcore_service_image_puller.docker_api import pull_image

pytestmark = pytest.mark.asyncio


@pytest.fixture
def small_docker_image() -> str:
    return "joseluisq/static-web-server:latest"


async def test_pull_image_found(small_docker_image: str) -> None:
    assert await pull_image(small_docker_image) is True


@pytest.mark.parametrize(
    "bad_image",
    [
        "no-access-to-repository:latest",
        "traefik:tag-does-not-exist-and-never-will",
    ],
)
async def test_pull_image_not_found(bad_image: str) -> None:
    assert await pull_image(bad_image) is False
