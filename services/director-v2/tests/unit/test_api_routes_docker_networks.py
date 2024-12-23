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
async def async_docker_client() -> AsyncIterable[Docker]:
    async with Docker() as client:
        yield client


@pytest.mark.parametrize(
    "network_name, network",
    [
        ("test_a_network", Network(name="test_a_network")),
        (
            "test_overlay_network",
            Network(
                name="test_overlay_network",
                driver="overlay",
                labels={
                    "io.simcore.zone": "mock_value",
                    "com.simcore.description": "interactive for node: mock_value",
                    "uuid": "mock_value",
                },
                attachable=True,
                internal=False,
            ),
        ),
    ],
)
async def test_routes_are_protected(
    docker_swarm: None,
    client: TestClient,
    async_docker_client: Docker,
    network_name: str,
    network: Network,
):
    response = client.post("/v2/docker/networks/", json=network.model_dump(mode="json"))
    assert response.status_code == status.HTTP_200_OK, response.text
    network_id: DockerNetworkID = response.json()

    # check network is present
    docker_network = await async_docker_client.networks.get(network_name)
    assert docker_network.id == network_id

    response = client.delete(f"/v2/docker/networks/{network_id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

    # check network was removed
    for name_or_id in (network_name, network_id):
        with pytest.raises(DockerError) as exc:
            await async_docker_client.networks.get(name_or_id)

        assert exc.value.status == status.HTTP_404_NOT_FOUND
