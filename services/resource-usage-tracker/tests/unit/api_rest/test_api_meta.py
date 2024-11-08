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


def test_healthcheck(
    disabled_database: None,
    disabled_prometheus: None,
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.MagicMock,
    client: TestClient,
    mocker: MockerFixture,
):
    rabbitmq_mock = mocker.Mock(spec=RabbitMQClient)
    rabbitmq_mock.healthy = True
    mocker.patch(
        "simcore_service_resource_usage_tracker.services.modules.rabbitmq.get_rabbitmq_client",
        return_value=rabbitmq_mock,
    )

    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text.startswith(
        "simcore_service_resource_usage_tracker.api.rest._health@"
    )


def test_healthcheck__unhealthy(
    disabled_database: None,
    disabled_prometheus: None,
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.MagicMock,
    client: TestClient,
    mocker: MockerFixture,
):
    rabbitmq_mock = mocker.Mock(spec=RabbitMQClient)
    rabbitmq_mock.healthy = False
    mocker.patch(
        "simcore_service_resource_usage_tracker.services.modules.rabbitmq.get_rabbitmq_client",
        return_value=rabbitmq_mock,
    )

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
