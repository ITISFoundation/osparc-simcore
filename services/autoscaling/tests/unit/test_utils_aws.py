# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Iterator

import botocore.exceptions
import pytest
from aiohttp.test_utils import unused_port
from moto.server import ThreadedMotoServer
from pydantic import ByteSize
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_autoscaling.core.errors import Ec2InstanceNotFoundError
from simcore_service_autoscaling.core.settings import AwsSettings
from simcore_service_autoscaling.models import Resources
from simcore_service_autoscaling.utils_aws import (
    compose_user_data,
    ec2_client,
    find_needed_ec2_instance,
    get_ec2_instance_capabilities,
)


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
        f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access
    )
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "xxx")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "xxx")

    yield


def test_ec2_client(
    app_environment: EnvVarsDict,
):
    settings = AwsSettings.create_from_envs()
    with ec2_client(settings) as client:
        ...

    with pytest.raises(
        botocore.exceptions.ClientError, match=r".+ AWS was not able to validate .+"
    ):
        with ec2_client(settings) as client:
            client.describe_account_attributes(DryRun=True)


def test_ec2_client_with_mock_server(
    app_environment: EnvVarsDict,
    mocked_aws_server_envs: None,
):
    settings = AwsSettings.create_from_envs()
    # passes without exception
    with ec2_client(settings) as client:
        client.describe_account_attributes(DryRun=True)


def test_get_ec2_instance_capabilities(
    app_environment: EnvVarsDict,
    mocked_aws_server_envs: None,
):
    settings = AwsSettings.create_from_envs()
    instance_types = get_ec2_instance_capabilities(settings)
    assert instance_types
    assert len(instance_types) == len(settings.AWS_EC2_TYPE_NAMES)

    # all the instance names are found and valid
    assert all(i.name in settings.AWS_EC2_TYPE_NAMES for i in instance_types)
    for instance_type_name in settings.AWS_EC2_TYPE_NAMES:
        assert any(i.name == instance_type_name for i in instance_types)


def test_find_needed_ec2_instance(
    app_environment: EnvVarsDict,
    mocked_aws_server_envs: None,
):
    settings = AwsSettings.create_from_envs()
    # this shall raise as there are no available instances
    with pytest.raises(Ec2InstanceNotFoundError):
        find_needed_ec2_instance(
            available_ec2_instances=[],
            resources=Resources(cpus=0, ram=ByteSize(0)),
        )
    available_instance_types = get_ec2_instance_capabilities(settings)


def test_compose_user_data(app_environment: EnvVarsDict):

    settings = AwsSettings.create_from_envs()

    user_data = compose_user_data(settings)
    print(user_data)

    for line in user_data.split("\n"):
        if "ssh" in line:
            assert f"ubuntu@{settings.AWS_DNS}" in line
