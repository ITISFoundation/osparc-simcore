# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

from collections.abc import Iterator

import pytest
import requests
from aiohttp.test_utils import unused_port
from moto.server import ThreadedMotoServer

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


@pytest.fixture
def mocked_aws_server_envs(
    client_environment: EnvVarsDict,
    mocked_aws_server: ThreadedMotoServer,
    reset_aws_server_state: None,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    changed_envs: EnvVarsDict = {
        "EC2_ENDPOINT": f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # pylint: disable=protected-access  # noqa: SLF001
        "EC2_ACCESS_KEY_ID": "xxx",
        "EC2_SECRET_ACCESS_KEY": "xxx",
    }
    return client_environment | setenvs_from_dict(monkeypatch, changed_envs)
