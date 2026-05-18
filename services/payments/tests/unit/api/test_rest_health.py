# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging

import httpx
import pytest
import simcore_service_payments.api.rest._health as health_module
from fastapi import status
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient


def _mock_rabbitmq_clients(
    mocker: MockerFixture,
    *,
    client_healthy: bool,
    rpc_client_healthy: bool,
) -> None:
    rabbitmq_mock = mocker.Mock(spec=RabbitMQClient)
    rabbitmq_mock.healthy = client_healthy
    mocker.patch(
        "simcore_service_payments.services.rabbitmq.get_rabbitmq_client",
        return_value=rabbitmq_mock,
    )

    rpc_mock = mocker.Mock(spec=RabbitMQRPCClient)
    rpc_mock.healthy = rpc_client_healthy
    mocker.patch(
        "simcore_service_payments.services.rabbitmq.get_rabbitmq_rpc_client",
        return_value=rpc_mock,
    )


async def test_healthcheck_returns_200_when_healthy(
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
    client: httpx.AsyncClient,
    mocker: MockerFixture,
):
    _mock_rabbitmq_clients(mocker, client_healthy=True, rpc_client_healthy=True)

    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text.startswith(f"{health_module.__name__}@"), f"got {response.text!r}"


@pytest.mark.parametrize(
    "client_healthy, rpc_client_healthy",
    [(False, False), (False, True), (True, False)],
)
async def test_healthcheck_returns_503_when_rabbitmq_unhealthy(
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
    client: httpx.AsyncClient,
    mocker: MockerFixture,
    client_healthy: bool,
    rpc_client_healthy: bool,
):
    """When the RabbitMQ client is unhealthy (e.g. AWS MQ maintenance), the
    healthcheck endpoint must return HTTP 503 (not raise an exception that
    produces a noisy 500 + traceback in the logs)."""
    _mock_rabbitmq_clients(mocker, client_healthy=client_healthy, rpc_client_healthy=rpc_client_healthy)

    response = await client.get("/")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@pytest.mark.parametrize(
    "client_healthy, rpc_client_healthy",
    [(False, False), (False, True), (True, False)],
)
async def test_healthcheck_does_not_log_error_when_rabbitmq_unhealthy(
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
    client: httpx.AsyncClient,
    mocker: MockerFixture,
    is_client_healthy: bool,
    is_rpc_client_healthy: bool,
    caplog: pytest.LogCaptureFixture,
):
    """An unhealthy RabbitMQ connection must NOT produce ERROR-level log entries
    from the unhandled-exception handler (handle_errors_as_500). It is expected
    and should be handled as a clean 503, not a 500."""
    _mock_rabbitmq_clients(mocker, client_healthy=is_client_healthy, rpc_client_healthy=is_rpc_client_healthy)

    with caplog.at_level(logging.ERROR):
        response = await client.get("/")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    error_records_from_500_handler = [
        r for r in caplog.records if r.levelno >= logging.ERROR and "servicelib.fastapi.exceptions_utils" in r.name
    ]
    assert not error_records_from_500_handler, (
        "Unhealthy healthcheck must not produce ERROR logs from the 500 handler. "
        f"Got: {[r.getMessage() for r in error_records_from_500_handler]}"
    )
