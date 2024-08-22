# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import httpx
import pytest
from moto.server import ThreadedMotoServer
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_autoscaling.api.health import _StatusGet
from starlette import status

pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    enabled_rabbitmq: None,
    mocked_ec2_server_envs: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    mocked_redis_server: None,
) -> EnvVarsDict:
    return app_environment


async def test_healthcheck(async_client: httpx.AsyncClient):
    response = await async_client.get("/")
    response.raise_for_status()
    assert response.status_code == status.HTTP_200_OK
    assert "simcore_service_autoscaling" in response.text


async def test_status_no_rabbit(
    disabled_rabbitmq: None,
    with_enabled_buffer_pools: EnvVarsDict,
    async_client: httpx.AsyncClient,
):
    response = await async_client.get("/status")
    response.raise_for_status()
    assert response.status_code == status.HTTP_200_OK
    status_response = _StatusGet.parse_obj(response.json())
    assert status_response

    assert status_response.rabbitmq.is_enabled is False
    assert status_response.rabbitmq.is_responsive is False

    assert status_response.ec2.is_enabled is True
    assert status_response.ec2.is_responsive is True

    assert status_response.ssm.is_enabled is True
    assert status_response.ssm.is_responsive is True

    assert status_response.docker.is_enabled is True
    assert status_response.docker.is_responsive is True


async def test_status_no_ssm(
    disabled_rabbitmq: None,
    disabled_ssm: None,
    async_client: httpx.AsyncClient,
):
    response = await async_client.get("/status")
    response.raise_for_status()
    assert response.status_code == status.HTTP_200_OK
    status_response = _StatusGet.parse_obj(response.json())
    assert status_response

    assert status_response.rabbitmq.is_enabled is False
    assert status_response.rabbitmq.is_responsive is False

    assert status_response.ec2.is_enabled is True
    assert status_response.ec2.is_responsive is True

    assert status_response.ssm.is_enabled is False
    assert status_response.ssm.is_responsive is False

    assert status_response.docker.is_enabled is True
    assert status_response.docker.is_responsive is True


async def test_status(
    mocked_aws_server: ThreadedMotoServer,
    with_enabled_buffer_pools: EnvVarsDict,
    mocked_ssm_server_envs: EnvVarsDict,
    async_client: httpx.AsyncClient,
):
    # stop the aws server...
    mocked_aws_server.stop()

    response = await async_client.get("/status")
    response.raise_for_status()
    assert response.status_code == status.HTTP_200_OK
    status_response = _StatusGet.parse_obj(response.json())
    assert status_response

    assert status_response.rabbitmq.is_enabled is True
    assert status_response.rabbitmq.is_responsive is True

    assert status_response.ec2.is_enabled is True
    assert status_response.ec2.is_responsive is False

    assert status_response.ssm.is_enabled is True
    assert status_response.ssm.is_responsive is False

    assert status_response.docker.is_enabled is True
    assert status_response.docker.is_responsive is True
    # restart the server
    mocked_aws_server.start()

    response = await async_client.get("/status")
    response.raise_for_status()
    assert response.status_code == status.HTTP_200_OK
    status_response = _StatusGet.parse_obj(response.json())
    assert status_response

    assert status_response.rabbitmq.is_enabled is True
    assert status_response.rabbitmq.is_responsive is True

    assert status_response.ec2.is_enabled is True
    assert status_response.ec2.is_responsive is True

    assert status_response.ssm.is_enabled is True
    assert status_response.ssm.is_responsive is True

    assert status_response.docker.is_enabled is True
    assert status_response.docker.is_responsive is True
