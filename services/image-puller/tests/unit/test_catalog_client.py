# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from httpx import AsyncClient
from models_library.docker import DockerImage
from pytest_httpx import HTTPXMock
from simcore_service_image_puller.catalog_client import (
    get_images_to_pull,
    get_shared_client,
)
from simcore_service_image_puller.settings import ImagePullerSettings

pytestmark = pytest.mark.asyncio


@pytest.fixture
def catalog_client() -> AsyncClient:
    return get_shared_client(ImagePullerSettings.create_from_envs())


@pytest.fixture
def images_to_pull() -> list[DockerImage]:
    return ["nginx:latest", "traefik"]


@pytest.fixture
def mock_catalog_client(
    httpx_mock: HTTPXMock,
    catalog_client: AsyncClient,
    images_to_pull: list[DockerImage],
) -> None:
    httpx_mock.add_response(
        method="GET",
        url=f"{catalog_client.base_url}sync/-/images",
        json=images_to_pull,
    )


async def test_get_images_to_pull(
    catalog_client: AsyncClient,
    images_to_pull: list[DockerImage],
    mock_catalog_client: None,
) -> None:
    result = await get_images_to_pull(catalog_client)
    assert result == images_to_pull
