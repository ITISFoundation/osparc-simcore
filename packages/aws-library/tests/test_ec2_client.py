# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import json
from collections.abc import AsyncIterator, Iterator

import botocore.exceptions
import pytest
import requests
from aiohttp.test_utils import unused_port
from aws_library.ec2.client import SimcoreEC2API
from faker import Faker
from moto.server import ThreadedMotoServer
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_host import get_localhost_ip
from settings_library.ec2 import EC2Settings
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceTypeType


@pytest.fixture(scope="session")
def ec2_instances() -> list[InstanceTypeType]:
    # these are some examples
    return ["t2.nano", "m5.12xlarge"]


@pytest.fixture
def app_environment(
    mock_env_devel_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
    ec2_instances: list[InstanceTypeType],
) -> EnvVarsDict:
    # SEE https://faker.readthedocs.io/en/master/providers/faker.providers.internet.html?highlight=internet#faker-providers-internet
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "EC2_ACCESS_KEY_ID": faker.pystr(),
            "EC2_SECRET_ACCESS_KEY": faker.pystr(),
            "EC2_INSTANCES_KEY_NAME": faker.pystr(),
            "EC2_INSTANCES_SECURITY_GROUP_IDS": json.dumps(
                faker.pylist(allowed_types=(str,))
            ),
            "EC2_INSTANCES_SUBNET_ID": faker.pystr(),
            "EC2_INSTANCES_AMI_ID": faker.pystr(),
            "EC2_INSTANCES_ALLOWED_TYPES": json.dumps(ec2_instances),
        },
    )
    return mock_env_devel_environment | envs


@pytest.fixture
def ec2_settings(
    app_environment: EnvVarsDict,
) -> EC2Settings:
    return EC2Settings.create_from_envs()


@pytest.fixture
async def simcore_ec2_api(ec2_settings: EC2Settings) -> AsyncIterator[SimcoreEC2API]:
    ec2 = await SimcoreEC2API.create(settings=ec2_settings)
    assert ec2
    assert ec2.client
    assert ec2.exit_stack
    assert ec2.session
    yield ec2
    await ec2.close()


@pytest.fixture
def ec2_client(simcore_ec2_api: SimcoreEC2API) -> EC2Client:
    return simcore_ec2_api.client


@pytest.fixture(scope="module")
def mocked_aws_server() -> Iterator[ThreadedMotoServer]:
    """creates a moto-server that emulates AWS services in place
    NOTE: Never use a bucket with underscores it fails!!
    """
    server = ThreadedMotoServer(ip_address=get_localhost_ip(), port=unused_port())
    # pylint: disable=protected-access
    print(
        f"--> started mock AWS server on {server._ip_address}:{server._port}"  # noqa: SLF001
    )
    print(
        f"--> Dashboard available on [http://{server._ip_address}:{server._port}/moto-api/]"  # noqa: SLF001
    )
    server.start()
    yield server
    server.stop()
    print(
        f"<-- stopped mock AWS server on {server._ip_address}:{server._port}"  # noqa: SLF001
    )


@pytest.fixture
def reset_aws_server_state(mocked_aws_server: ThreadedMotoServer) -> Iterator[None]:
    # NOTE: reset_aws_server_state [http://docs.getmoto.org/en/latest/docs/server_mode.html#reset-api]
    yield
    # pylint: disable=protected-access
    requests.post(
        f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}/moto-api/reset",  # noqa: SLF001
        timeout=10,
    )


@pytest.fixture
def mocked_aws_server_envs(
    app_environment: EnvVarsDict,
    mocked_aws_server: ThreadedMotoServer,
    reset_aws_server_state: None,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    changed_envs: EnvVarsDict = {
        "EC2_ENDPOINT": f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access  # noqa: SLF001
        "EC2_ACCESS_KEY_ID": "xxx",
        "EC2_SECRET_ACCESS_KEY": "xxx",
    }
    return app_environment | setenvs_from_dict(monkeypatch, changed_envs)


async def test_ec2_client_lifespan(simcore_ec2_api: SimcoreEC2API):
    ...


async def test_ec2_client_raises_when_no_connection_available(ec2_client: EC2Client):
    with pytest.raises(
        botocore.exceptions.ClientError, match=r".+ AWS was not able to validate .+"
    ):
        await ec2_client.describe_account_attributes(DryRun=True)


async def test_ec2_client_with_mock_server(
    mocked_aws_server_envs: None, ec2_client: EC2Client
):
    # passes without exception
    await ec2_client.describe_account_attributes(DryRun=True)
