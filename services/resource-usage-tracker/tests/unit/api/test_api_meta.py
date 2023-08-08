# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from unittest import mock

from fastapi import status
from fastapi.testclient import TestClient
from simcore_service_resource_usage_tracker._meta import API_VTAG
from simcore_service_resource_usage_tracker.api._meta import _Meta


def test_healthcheck(
    disabled_database: None,
    disabled_prometheus: None,
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    mocked_setup_rabbitmq: mock.MagicMock,
    client: TestClient,
):
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text.startswith(
        "simcore_service_resource_usage_tracker.api._health@"
    )


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
    meta = _Meta.parse_obj(response.json())

    response = client.get(meta.docs_url)
    assert response.status_code == status.HTTP_200_OK
