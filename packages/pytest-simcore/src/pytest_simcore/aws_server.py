# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

from collections.abc import Iterator

import pytest
import requests
from aiohttp.test_utils import unused_port
from faker import Faker
from moto.server import ThreadedMotoServer
from pydantic import AnyHttpUrl, parse_obj_as
from settings_library.ec2 import EC2Settings
from settings_library.s3 import S3Settings

from .helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from .helpers.utils_host import get_localhost_ip


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
    print(
        f"<-- cleaned mock AWS server on {mocked_aws_server._ip_address}:{mocked_aws_server._port}"  # noqa: SLF001
    )


@pytest.fixture
def mocked_ec2_server_settings(
    mocked_aws_server: ThreadedMotoServer,
    reset_aws_server_state: None,
) -> EC2Settings:
    return EC2Settings(
        EC2_ACCESS_KEY_ID="xxx",
        EC2_ENDPOINT=f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access # noqa: SLF001
        EC2_SECRET_ACCESS_KEY="xxx",  # noqa: S106
    )


@pytest.fixture
def mocked_ec2_server_envs(
    mocked_ec2_server_settings: EC2Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    changed_envs: EnvVarsDict = mocked_ec2_server_settings.dict()
    return setenvs_from_dict(monkeypatch, changed_envs)


@pytest.fixture
def mocked_s3_server_settings(
    mocked_aws_server: ThreadedMotoServer, reset_aws_server_state: None, faker: Faker
) -> S3Settings:
    return S3Settings(
        S3_ACCESS_KEY="xxx",
        S3_ENDPOINT=parse_obj_as(
            AnyHttpUrl,
            f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access  # noqa: SLF001
        ),
        S3_SECRET_KEY="xxx",  # noqa: S106
        S3_BUCKET_NAME=f"pytest{faker.pystr().lower()}",
        S3_REGION="us-east-1",
    )


@pytest.fixture
def mocked_s3_server_envs(
    mocked_s3_server_settings: S3Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    changed_envs: EnvVarsDict = mocked_s3_server_settings.dict(exclude_unset=True)
    return setenvs_from_dict(monkeypatch, changed_envs)
