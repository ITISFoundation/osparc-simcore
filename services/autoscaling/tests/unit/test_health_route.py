# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import httpx
import pytest
from moto.server import ThreadedMotoServer
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from starlette import status

pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    enabled_rabbitmq: None,
    mocked_aws_server_envs: None,
) -> EnvVarsDict:
    return app_environment


async def test_healthcheck(async_client: httpx.AsyncClient):
    response = await async_client.get("/")
    response.raise_for_status()
    assert response.status_code == status.HTTP_200_OK
    assert "simcore_service_autoscaling" in response.text


async def test_status_no_rabbit(
    disabled_rabbitmq: None,
    async_client: httpx.AsyncClient,
):
    response = await async_client.get("/status")
    response.raise_for_status()
    assert response.status_code == status.HTTP_200_OK
    status_response = response.json()
    assert "rabbitmq" in status_response
    rabbitmq_status = status_response["rabbitmq"]
    assert "initialized" in rabbitmq_status
    assert rabbitmq_status["initialized"] is False
    assert rabbitmq_status["connection_state"] is False

    assert "ec2" in status_response
    ec2_status = status_response["ec2"]
    assert "initialized" in ec2_status
    assert ec2_status["initialized"] is True
    assert ec2_status["connection_state"] is True


async def test_status(
    mocked_aws_server: ThreadedMotoServer,
    async_client: httpx.AsyncClient,
):
    # stop the aws server...
    mocked_aws_server.stop()

    response = await async_client.get("/status")
    response.raise_for_status()
    assert response.status_code == status.HTTP_200_OK
    status_response = response.json()
    assert "rabbitmq" in status_response
    rabbitmq_status = status_response["rabbitmq"]
    assert "initialized" in rabbitmq_status
    assert rabbitmq_status["initialized"] is True
    assert rabbitmq_status["connection_state"] is True

    assert "ec2" in status_response
    ec2_status = status_response["ec2"]
    assert "initialized" in ec2_status
    assert ec2_status["initialized"] is True
    assert ec2_status["connection_state"] is False

    # restart the server
    mocked_aws_server.start()

    response = await async_client.get("/status")
    response.raise_for_status()
    assert response.status_code == status.HTTP_200_OK
    status_response = response.json()
    assert "rabbitmq" in status_response
    rabbitmq_status = status_response["rabbitmq"]
    assert "initialized" in rabbitmq_status
    assert rabbitmq_status["initialized"] is True
    assert rabbitmq_status["connection_state"] is True

    assert "ec2" in status_response
    ec2_status = status_response["ec2"]
    assert "initialized" in ec2_status
    assert ec2_status["initialized"] is True
    assert ec2_status["connection_state"] is True
