# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterable

import pytest
from aiodocker import Docker, DockerError
from faker import Faker
from fastapi import status
from models_library.docker import DockerNetworkID
from models_library.generated_models.docker_rest_api import Network
from pytest_simcore.helpers.typing_env import EnvVarsDict
from starlette.testclient import TestClient


@pytest.fixture
def mock_env(
    mock_exclusive: None,
    disable_rabbitmq: None,
    disable_postgres: None,
    mock_env: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
) -> None:
    monkeypatch.setenv("DIRECTOR_V2_DOCKER_ENTRYPOINT_ACCESS_TOKEN", "adminadmin")

    monkeypatch.setenv("SC_BOOT_MODE", "default")
    monkeypatch.setenv("DIRECTOR_ENABLED", "false")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "false")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "false")

    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "false")

    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", faker.url())
    monkeypatch.setenv("S3_ACCESS_KEY", faker.pystr())
    monkeypatch.setenv("S3_REGION", faker.pystr())
    monkeypatch.setenv("S3_SECRET_KEY", faker.pystr())
    monkeypatch.setenv("S3_BUCKET_NAME", faker.pystr())


@pytest.fixture
async def docker_client() -> AsyncIterable[Docker]:
    async with Docker() as client:
        yield client


async def test_routes_are_protected(client: TestClient, docker_client: Docker):
    network_name = "a_test_network"
    network = Network(name=network_name)

    response = client.post("/v2/docker/networks/", json=network.model_dump(mode="json"))
    assert response.status_code == status.HTTP_200_OK, response.text
    network_id: DockerNetworkID = response.json()

    response = client.delete(f"/v2/docker/networks/{network_id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

    # check it is not here

    for name_or_id in (network_name, network_id):
        with pytest.raises(DockerError) as exc:
            await docker_client.networks.get(name_or_id)

        assert exc.value.status == status.HTTP_404_NOT_FOUND
