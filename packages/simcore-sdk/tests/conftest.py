# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
import sys
from pathlib import Path
from typing import Any

import pytest
import simcore_sdk
from helpers.utils_port_v2 import CONSTANT_UUID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.postgres_tools import PostgresTestConfig
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
sys.path.append(str(current_dir / "helpers"))


pytest_plugins = [
    "pytest_simcore.aws_s3_service",
    "pytest_simcore.aws_server",
    "pytest_simcore.db_entries_mocks",
    "pytest_simcore.disk_usage_monitoring",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.file_extra",
    "pytest_simcore.logging",
    "pytest_simcore.minio_service",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
    "pytest_simcore.services_api_mocks_for_aiohttp_clients",
    "pytest_simcore.simcore_services",
    "pytest_simcore.simcore_storage_service",
]


@pytest.fixture(scope="session")
def package_dir():
    pdir = Path(simcore_sdk.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture(scope="session")
def default_configuration_file() -> Path:
    path = current_dir / "mock" / "default_config.json"
    assert path.exists()
    return path


@pytest.fixture(scope="session")
def default_configuration(default_configuration_file: Path) -> dict[str, Any]:
    return json.loads(default_configuration_file.read_text())


@pytest.fixture(scope="session")
def empty_configuration_file() -> Path:
    path = current_dir / "mock" / "empty_config.json"
    assert path.exists()
    return path


@pytest.fixture
def node_ports_config(
    postgres_host_config: PostgresTestConfig, minio_s3_settings_envs: EnvVarsDict
) -> None: ...


@pytest.fixture
def mock_io_log_redirect_cb() -> LogRedirectCB:
    async def _mocked_function(*args, **kwargs) -> None:
        pass

    return _mocked_function


@pytest.fixture
def constant_uuid4(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_sdk.node_ports_common.data_items_utils.uuid4",
        return_value=CONSTANT_UUID,
    )
