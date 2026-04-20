# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from unittest import mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_resource_usage_tracker._meta import API_VTAG
from simcore_service_resource_usage_tracker.api.rest._health import HealthCheckError
from simcore_service_resource_usage_tracker.api.rest._meta import _Meta


def _mock_health_client(mocker: MockerFixture, healthy: bool, target_function: str) -> None:
    rabbitmq_mock = mocker.Mock(spec=RabbitMQClient)
    rabbitmq_mock.healthy = healthy
    mocker.patch(
        f"simcore_service_resource_usage_tracker.services.modules.rabbitmq.{target_function}",
        return_value=rabbitmq_mock,
    )


def test_healthcheck(
    disabled_database: None,
    disabled_prometheus: None,
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.MagicMock,
    client: TestClient,
    mocker: MockerFixture,
):
    _mock_health_client(mocker, healthy=True, target_function="get_rabbitmq_client")
    _mock_health_client(mocker, healthy=True, target_function="get_rabbitmq_rpc_client")

    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text.startswith("simcore_service_resource_usage_tracker.api.rest._health@")


@pytest.mark.parametrize(
    "rabbit_client_healthy, rabbitmq_rpc_client_healthy",
    [(False, False), (False, True), (True, False)],
)
def test_healthcheck__unhealthy(
    disabled_database: None,
    disabled_prometheus: None,
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.MagicMock,
    client: TestClient,
    mocker: MockerFixture,
    rabbit_client_healthy: bool,
    rabbitmq_rpc_client_healthy: bool,
):
    _mock_health_client(mocker, healthy=rabbit_client_healthy, target_function="get_rabbitmq_client")
    _mock_health_client(mocker, healthy=rabbitmq_rpc_client_healthy, target_function="get_rabbitmq_rpc_client")

    with pytest.raises(HealthCheckError):
        client.get("/")


def test_meta(
    disabled_database: None,
    disabled_prometheus: None,
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.MagicMock,
    client: TestClient,
):
    response = client.get(f"/{API_VTAG}/meta")
    assert response.status_code == status.HTTP_200_OK
    meta = _Meta.model_validate(response.json())

    response = client.get(f"{meta.docs_url}")
    assert response.status_code == status.HTTP_200_OK
