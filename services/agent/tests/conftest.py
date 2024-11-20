# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import pytest
from faker import Faker
from models_library.basic_types import BootModeEnum
from moto.server import ThreadedMotoServer
from pydantic import HttpUrl, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from settings_library.r_clone import S3Provider

pytest_plugins = [
    "pytest_simcore.aws_server",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
]


@pytest.fixture
def swarm_stack_name() -> str:
    return "test-simcore"


@pytest.fixture
def docker_node_id() -> str:
    return "test-node-id"


@pytest.fixture
def bucket(faker: Faker) -> str:
    return f"test-bucket-{faker.uuid4()}"


@pytest.fixture
def mock_environment(
    monkeypatch: pytest.MonkeyPatch,
    mocked_s3_server_url: HttpUrl,
    bucket: str,
    swarm_stack_name: str,
    docker_node_id: str,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            "LOGLEVEL": "DEBUG",
            "SC_BOOT_MODE": BootModeEnum.DEBUG,
            "AGENT_VOLUMES_CLEANUP_TARGET_SWARM_STACK_NAME": swarm_stack_name,
            "AGENT_VOLUMES_CLEANUP_S3_ENDPOINT": f"{mocked_s3_server_url}",
            "AGENT_VOLUMES_CLEANUP_S3_ACCESS_KEY": "xxx",
            "AGENT_VOLUMES_CLEANUP_S3_SECRET_KEY": "xxx",
            "AGENT_VOLUMES_CLEANUP_S3_BUCKET": bucket,
            "AGENT_VOLUMES_CLEANUP_S3_PROVIDER": S3Provider.MINIO,
            "RABBIT_HOST": "test",
            "RABBIT_PASSWORD": "test",
            "RABBIT_SECURE": "false",
            "RABBIT_USER": "test",
            "AGENT_DOCKER_NODE_ID": docker_node_id,
            "AGENT_TRACING": "null",
        },
    )


@pytest.fixture(scope="module")
def mocked_s3_server_url(mocked_aws_server: ThreadedMotoServer) -> HttpUrl:
    # pylint: disable=protected-access
    return TypeAdapter(HttpUrl).validate_python(
        f"http://{mocked_aws_server._ip_address}:{mocked_aws_server._port}",  # noqa: SLF001
    )
