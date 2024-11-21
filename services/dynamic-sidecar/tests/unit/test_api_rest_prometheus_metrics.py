# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from collections.abc import AsyncIterable
from typing import Final
from unittest.mock import AsyncMock

import pytest
from aiodocker.volumes import DockerVolume
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.callbacks_mapping import CallbacksMapping
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from pydantic import AnyHttpUrl, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.fastapi.long_running_tasks.client import (
    Client,
    TaskId,
    periodic_task_result,
)
from servicelib.fastapi.long_running_tasks.client import setup as client_setup
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.models.schemas.containers import (
    ContainersComposeSpec,
    ContainersCreate,
)
from simcore_service_dynamic_sidecar.modules.prometheus_metrics import (
    _USER_SERVICES_NOT_STARTED,
    UserServicesMetrics,
)

_FAST_STATUS_POLL: Final[float] = 0.1
_CREATE_SERVICE_CONTAINERS_TIMEOUT: Final[float] = 60


@pytest.fixture
async def enable_prometheus_metrics(
    monkeypatch: pytest.MonkeyPatch, mock_environment: EnvVarsDict
) -> None:
    setenvs_from_dict(
        monkeypatch,
        {
            "DY_SIDECAR_CALLBACKS_MAPPING": json.dumps(
                CallbacksMapping.model_config["json_schema_extra"]["examples"][2]
            )
        },
    )


@pytest.fixture
async def app(mock_rabbitmq_envs: EnvVarsDict, app: FastAPI) -> AsyncIterable[FastAPI]:
    client_setup(app)
    async with LifespanManager(app):
        yield app


@pytest.fixture
def backend_url() -> AnyHttpUrl:
    return TypeAdapter(AnyHttpUrl).validate_python("http://backgroud.testserver.io")


@pytest.fixture
async def httpx_async_client(
    app: FastAPI,
    backend_url: AnyHttpUrl,
    ensure_external_volumes: tuple[DockerVolume],
    cleanup_containers: None,
) -> AsyncIterable[AsyncClient]:
    async with AsyncClient(
        app=app,
        base_url=f"{backend_url}",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
def client(
    app: FastAPI, httpx_async_client: AsyncClient, backend_url: AnyHttpUrl
) -> Client:
    return Client(app=app, async_client=httpx_async_client, base_url=f"{backend_url}")


@pytest.fixture
def compose_spec() -> str:
    return json.dumps(
        {
            "version": "3",
            "services": {
                "rt-web": {
                    "image": "alpine:latest",
                    "command": ["sh", "-c", "sleep 100000"],
                }
            },
        }
    )


async def _get_task_id_create_service_containers(
    httpx_async_client: AsyncClient,
    compose_spec: str,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
) -> TaskId:
    ctontainers_compose_spec = ContainersComposeSpec(
        docker_compose_yaml=compose_spec,
    )
    await httpx_async_client.post(
        f"/{API_VTAG}/containers/compose-spec",
        json=ctontainers_compose_spec.model_dump(),
    )
    containers_create = ContainersCreate(metrics_params=mock_metrics_params)
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers", json=containers_create.model_dump()
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def test_metrics_disabled(
    mock_core_rabbitmq: dict[str, AsyncMock], httpx_async_client: AsyncClient
) -> None:
    response = await httpx_async_client.get("/metrics")
    assert response.status_code == status.HTTP_404_NOT_FOUND, response


async def test_metrics_enabled_no_containers_running(
    enable_prometheus_metrics: None,
    mock_core_rabbitmq: dict[str, AsyncMock],
    httpx_async_client: AsyncClient,
) -> None:
    response = await httpx_async_client.get("/metrics")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response
    assert _USER_SERVICES_NOT_STARTED in response.text


async def test_metrics_enabled_containers_will_start(
    enable_prometheus_metrics: None,
    mock_core_rabbitmq: dict[str, AsyncMock],
    app: FastAPI,
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
):
    # no containers started
    response = await httpx_async_client.get("/metrics")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response
    assert _USER_SERVICES_NOT_STARTED in response.text

    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_create_service_containers(
            httpx_async_client, compose_spec, mock_metrics_params
        ),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
    ) as result:
        assert isinstance(result, list)
        assert len(result) == 1

    # check after containers started
    # update manually
    user_service_metrics: UserServicesMetrics = app.state.user_service_metrics
    await user_service_metrics._update_metrics()  # noqa: SLF001

    response = await httpx_async_client.get("/metrics")
    assert response.status_code == status.HTTP_200_OK, response
