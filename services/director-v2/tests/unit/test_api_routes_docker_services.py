# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import pytest
from aiodocker import Docker, DockerError
from faker import Faker
from fastapi import status
from models_library.docker import DockerServiceID
from models_library.generated_models.docker_rest_api import ServiceSpec
from pydantic import TypeAdapter
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director_v2.api.routes.docker_services import _envs_to_dict
from starlette.testclient import TestClient
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed


@pytest.mark.parametrize(
    "provided,result",
    [
        (["some_value=k1=k_continued"], {"some_value": "k1=k_continued"}),
        ({"some_value": "k1=k_continued"}, {"some_value": "k1=k_continued"}),
    ],
)
def test__envs_to_dict(provided: dict | list, result: dict):
    assert _envs_to_dict(provided) == result


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


async def test_service_workflow(
    docker_swarm: None,
    client: TestClient,
    async_docker_client: Docker,
):
    service_name: str = "a_test_service"
    service_spec: ServiceSpec = TypeAdapter(ServiceSpec).validate_python(
        {
            "Name": "a_test_service",
            "TaskTemplate": {
                "ContainerSpec": {"Image": "nginx:latest", "Env": ["ENV_VAR=a_value"]},
                "RestartPolicy": {
                    "Condition": "any",
                    "Delay": 5000000000,
                    "MaxAttempts": 3,
                },
            },
            "Mode": {"Replicated": {"Replicas": 2}},
            "EndpointSpec": {
                "Ports": [{"Protocol": "tcp", "TargetPort": 80, "PublishedPort": 8080}]
            },
        }
    )

    response = client.post(
        "/v2/docker/services/", json=service_spec.model_dump(mode="json")
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    service_id: DockerServiceID = response.json()

    # check service is present
    async for attempt in AsyncRetrying(
        reraise=True, wait=wait_fixed(1), stop=stop_after_delay(10)
    ):
        with attempt:
            service_inspect = await async_docker_client.services.inspect(service_name)
            assert service_inspect["ID"] == service_id

    response = client.delete(f"/v2/docker/services/{service_id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text

    # check service was removed
    for name_or_id in (service_name, service_id):
        with pytest.raises(DockerError) as exc:
            await async_docker_client.services.inspect(name_or_id)

        assert exc.value.status == status.HTTP_404_NOT_FOUND
