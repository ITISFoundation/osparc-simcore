# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Iterator

import boto3
import pytest
from aiohttp.test_utils import unused_port
from moto.server import ThreadedMotoServer
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.core.settings import AwsSettings
from simcore_service_autoscaling.utils_aws import compose_user_data


@pytest.fixture(scope="module")
def mocked_aws_server() -> Iterator[ThreadedMotoServer]:
    """creates a moto-server that emulates AWS services in place
    NOTE: Never use a bucket with underscores it fails!!
    """
    server = ThreadedMotoServer(ip_address=get_localhost_ip(), port=unused_port())
    # pylint: disable=protected-access
    print(f"--> started mock AWS server on {server._ip_address}:{server._port}")
    print(
        f"--> Dashboard available on [http://{server._ip_address}:{server._port}/moto-api/]"
    )
    server.start()
    yield server
    server.stop()
    print(f"<-- stopped mock AWS server on {server._ip_address}:{server._port}")


@pytest.fixture
def mocked_aws_server_envs(
    mocked_aws_server: ThreadedMotoServer, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    monkeypatch.setenv(
        "AWS_ENDPOINT",
        f"{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access
    )
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "xxx")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "xxx")

    yield


def test_mocked_ec2_server(
    app_environment: EnvVarsDict,
    mocked_aws_server_envs: None,
):
    settings = AwsSettings.create_from_envs()

    ec2 = boto3.resource(
        "ec2",
        region_name=settings.AWS_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    # ec2.meta.client.get_paginator()


def test_compose_user_data(app_environment: EnvVarsDict):

    settings = AwsSettings.create_from_envs()

    user_data = compose_user_data(settings)
    print(user_data)

    for line in user_data.split("\n"):
        if "ssh" in line:
            assert f"ubuntu@{settings.AWS_DNS}" in line
