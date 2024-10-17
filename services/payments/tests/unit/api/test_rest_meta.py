# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import httpx
import pytest
import simcore_service_payments.api.rest._health as health_module
from fastapi import status
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQClient
from simcore_service_payments._meta import API_VTAG
from simcore_service_payments.api.rest._health import HealthCheckError
from simcore_service_payments.models.schemas.meta import Meta


async def test_healthcheck(
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
    client: httpx.AsyncClient,
    mocker: MockerFixture,
):
    rabbitmq_mock = mocker.Mock(spec=RabbitMQClient)
    rabbitmq_mock.healthy = True
    mocker.patch(
        "simcore_service_payments.services.rabbitmq.get_rabbitmq_client",
        return_value=rabbitmq_mock,
    )

    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text.startswith(
        f"{health_module.__name__}@"
    ), f"got {response.text!r}"


async def test_healthcheck__unhealthy(
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
    client: httpx.AsyncClient,
    mocker: MockerFixture,
):
    rabbitmq_mock = mocker.Mock(spec=RabbitMQClient)
    rabbitmq_mock.healthy = False
    mocker.patch(
        "simcore_service_payments.services.rabbitmq.get_rabbitmq_client",
        return_value=rabbitmq_mock,
    )

    with pytest.raises(HealthCheckError):
        await client.get("/")


async def test_meta(
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
):
    response = await client.get(f"/{API_VTAG}/meta", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    meta = Meta.model_validate(response.json())

    response = await client.get(f"{meta.docs_url}")
    assert response.status_code == status.HTTP_200_OK
