# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
import re
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from random import choice
from typing import Any
from unittest import mock

import httpx
import pytest
import requests_mock
from asgi_lifespan import LifespanManager
from faker import Faker
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from simcore_service_resource_usage_tracker.core.application import create_app
from simcore_service_resource_usage_tracker.core.settings import ApplicationSettings

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.aws_s3_service",
    "pytest_simcore.aws_server",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "resource-usage-tracker"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_resource_usage_tracker"))
    return service_folder


@pytest.fixture
def app_environment(
    mock_env_devel_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
) -> EnvVarsDict:
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "POSTGRES_HOST": faker.domain_name(),
            "POSTGRES_USER": faker.user_name(),
            "POSTGRES_PASSWORD": faker.password(special_chars=False),
            "POSTGRES_DB": faker.pystr(),
            "PROMETHEUS_URL": f"{choice(['http', 'https'])}://{faker.domain_name()}",
            "PROMETHEUS_USERNAME": faker.user_name(),
            "PROMETHEUS_PASSWORD": faker.password(special_chars=False),
            "RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_CHECK_ENABLED": "0",
            "RESOURCE_USAGE_TRACKER_TRACING": "null",
        },
    )

    return mock_env_devel_environment | envs


@pytest.fixture
def disabled_prometheus(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PROMETHEUS_URL")
    monkeypatch.delenv("PROMETHEUS_USERNAME")
    monkeypatch.delenv("PROMETHEUS_PASSWORD")


@pytest.fixture
def disabled_database(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("POSTGRES_HOST")
    monkeypatch.delenv("POSTGRES_USER")
    monkeypatch.delenv("POSTGRES_PASSWORD")
    monkeypatch.delenv("POSTGRES_DB")


@pytest.fixture
def disabled_rabbitmq(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("RABBIT_HOST")
    monkeypatch.delenv("RABBIT_USER")
    monkeypatch.delenv("RABBIT_SECURE")
    monkeypatch.delenv("RABBIT_PASSWORD")


@pytest.fixture
def enabled_rabbitmq(
    app_environment: EnvVarsDict, rabbit_service: RabbitSettings
) -> RabbitSettings:
    return rabbit_service


@pytest.fixture
def app_settings(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> ApplicationSettings:
    return ApplicationSettings.create_from_envs()


@pytest.fixture
async def initialized_app(app_settings: ApplicationSettings) -> AsyncIterator[FastAPI]:
    app = create_app(app_settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture
def client(app_settings: ApplicationSettings) -> Iterator[TestClient]:
    app = create_app(app_settings)
    with TestClient(app, base_url="http://testserver.test") as client:
        yield client


@pytest.fixture
async def async_client(initialized_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        app=initialized_app,
        base_url=f"http://{initialized_app.title}.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
def mocked_prometheus(
    requests_mock: requests_mock.Mocker, app_settings: ApplicationSettings
) -> requests_mock.Mocker:
    assert app_settings.RESOURCE_USAGE_TRACKER_PROMETHEUS
    requests_mock.get(f"{app_settings.RESOURCE_USAGE_TRACKER_PROMETHEUS.api_url}/")
    return requests_mock


@pytest.fixture
def get_metric_response(faker: Faker) -> Callable[..., dict[str, Any]]:
    def _get_metric(request, context) -> dict[str, Any]:
        return {
            "data": {
                "result": [
                    {
                        "metric": {
                            "id": "cpu",
                            "container_label_uuid": faker.uuid4(),
                            "container_label_simcore_service_settings": json.dumps(
                                [
                                    {
                                        "name": "Resources",
                                        "type": "Resources",
                                        "resources": faker.pystr(),
                                        "value": {
                                            "Limits": {
                                                "NanoCPUs": faker.pyint(min_value=1000)
                                            }
                                        },
                                    }
                                ]
                            ),
                        },
                        "value": faker.pylist(allowed_types=(int,)),
                    }
                ]
            }
        }

    return _get_metric


@pytest.fixture
def mocked_prometheus_with_query(
    mocked_prometheus: requests_mock.Mocker,
    app_settings: ApplicationSettings,
    faker: Faker,
    get_metric_response,
) -> requests_mock.Mocker:
    """overrides with needed calls here"""
    assert app_settings.RESOURCE_USAGE_TRACKER_PROMETHEUS
    pattern = re.compile(
        rf"^{re.escape(app_settings.RESOURCE_USAGE_TRACKER_PROMETHEUS.api_url)}/api/v1/query\?.*$"
    )
    mocked_prometheus.get(pattern, json=get_metric_response)
    return mocked_prometheus


@pytest.fixture
def disabled_tracker_background_task(mocker: MockerFixture) -> dict[str, mock.Mock]:
    mocked_start = mocker.patch(
        "simcore_service_resource_usage_tracker.modules.prometheus_containers.plugin.start_periodic_task",
        autospec=True,
    )

    mocked_stop = mocker.patch(
        "simcore_service_resource_usage_tracker.modules.prometheus_containers.plugin.stop_periodic_task",
        autospec=True,
    )
    return {"start_task": mocked_start, "stop_task": mocked_stop}


@pytest.fixture
async def mocked_redis_server(mocker: MockerFixture) -> None:
    mock_redis = FakeRedis()
    mocker.patch("redis.asyncio.from_url", return_value=mock_redis)


@pytest.fixture
def mocked_setup_rabbitmq(mocker: MockerFixture):
    return (
        mocker.patch(
            "simcore_service_resource_usage_tracker.core.application.setup_rabbitmq",
            autospec=True,
        ),
        mocker.patch(
            "simcore_service_resource_usage_tracker.core.application.setup_rpc_api_routes",
            autospec=True,
        ),
    )
