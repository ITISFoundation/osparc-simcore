# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from uuid import uuid4

import pytest
from models_library.basic_types import BootModeEnum
from moto.server import ThreadedMotoServer
from pydantic import HttpUrl, parse_obj_as
from settings_library.r_clone import S3Provider

pytest_plugins = [
    "pytest_simcore.aws_server",
    "pytest_simcore.repository_paths",
]


@pytest.fixture
def swarm_stack_name() -> str:
    return "test-simcore"


@pytest.fixture
def bucket() -> str:
    return f"test-bucket-{uuid4()}"


@pytest.fixture
def env(
    monkeypatch: pytest.MonkeyPatch,
    mocked_s3_server_url: HttpUrl,
    bucket: str,
    swarm_stack_name: str,
) -> None:
    mock_dict = {
        "LOGLEVEL": "DEBUG",
        "SC_BOOT_MODE": BootModeEnum.DEBUG,
        "AGENT_VOLUMES_CLEANUP_TARGET_SWARM_STACK_NAME": swarm_stack_name,
        "AGENT_VOLUMES_CLEANUP_S3_ENDPOINT": mocked_s3_server_url,
        "AGENT_VOLUMES_CLEANUP_S3_ACCESS_KEY": "xxx",
        "AGENT_VOLUMES_CLEANUP_S3_SECRET_KEY": "xxx",
        "AGENT_VOLUMES_CLEANUP_S3_BUCKET": bucket,
        "AGENT_VOLUMES_CLEANUP_S3_PROVIDER": S3Provider.MINIO,
    }
    for key, value in mock_dict.items():
        monkeypatch.setenv(key, value)


@pytest.fixture(scope="module")
def mocked_s3_server_url(mocked_aws_server: ThreadedMotoServer) -> HttpUrl:
    # pylint: disable=protected-access
    return parse_obj_as(
        HttpUrl,
        f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # noqa: SLF001
    )
