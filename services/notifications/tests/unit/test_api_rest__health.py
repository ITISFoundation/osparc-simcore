# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import pytest
from fastapi import status
from fastapi.testclient import TestClient
from models_library.api_schemas__common.health import HealthCheckGet
from models_library.errors import (
    POSRGRES_DATABASE_UNHEALTHY_MSG,
    RABBITMQ_CLIENT_UNHEALTHY_MSG,
)
from models_library.healthchecks import IsNonResponsive
from pytest_mock import MockerFixture
from simcore_service_notifications.api.rest._health import HealthCheckError

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]


def test_health_ok(test_client: TestClient):
    response = test_client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert HealthCheckGet.model_validate(response.json())


@pytest.fixture
def mock_postgres_liveness(mocker: MockerFixture, test_client: TestClient) -> None:
    mocker.patch.object(
        test_client.app.state.postgres_liveness,
        "_liveness_result",
        new=IsNonResponsive(reason="fake"),
    )


def test_health_postgres_unhealthy(
    mock_postgres_liveness: None, test_client: TestClient
):
    with pytest.raises(HealthCheckError) as exc:
        test_client.get("/")
    assert POSRGRES_DATABASE_UNHEALTHY_MSG in f"{exc.value}"


@pytest.fixture
def mock_rabbit_healthy(mocker: MockerFixture, test_client: TestClient) -> None:
    mocker.patch.object(
        test_client.app.state.rabbitmq_rpc_server, "_healthy_state", new=False
    )


def test_health_rabbit_unhealthy(mock_rabbit_healthy: None, test_client: TestClient):
    with pytest.raises(HealthCheckError) as exc:
        test_client.get("/")
    assert RABBITMQ_CLIENT_UNHEALTHY_MSG in f"{exc.value}"
