import json

# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
import simcore_sdk
from simcore_sdk.node_ports_common import config as node_config

## HELPERS
current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
sys.path.append(str(current_dir / "helpers"))

# FIXTURES
pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.minio_service",
    "pytest_simcore.monkeypatch_extra",
    "pytest_simcore.postgres_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.services_api_mocks_for_aiohttp_clients",
    "pytest_simcore.simcore_storage_service",
    "pytest_simcore.tmp_path_extra",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.file_extra",
]


@pytest.fixture(scope="session")
def package_dir():
    pdir = Path(simcore_sdk.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture(scope="session")
def osparc_simcore_root_dir() -> Path:
    """osparc-simcore repo root dir"""
    WILDCARD = "packages/simcore-sdk"

    root_dir = Path(current_dir)
    while not any(root_dir.glob(WILDCARD)) and root_dir != Path("/"):
        root_dir = root_dir.parent

    msg = f"'{root_dir}' does not look like the git root directory of osparc-simcore"
    assert root_dir.exists(), msg
    assert any(root_dir.glob(WILDCARD)), msg
    assert any(root_dir.glob(".git")), msg

    return root_dir


@pytest.fixture(scope="session")
def env_devel_file(osparc_simcore_root_dir) -> Path:
    env_devel_fpath = osparc_simcore_root_dir / ".env-devel"
    assert env_devel_fpath.exists()
    return env_devel_fpath


@pytest.fixture(scope="session")
def default_configuration_file() -> Path:
    path = current_dir / "mock" / "default_config.json"
    assert path.exists()
    return path


@pytest.fixture(scope="session")
def default_configuration(default_configuration_file: Path) -> Dict[str, Any]:
    config = json.loads(default_configuration_file.read_text())
    return config


@pytest.fixture(scope="session")
def empty_configuration_file() -> Path:
    path = current_dir / "mock" / "empty_config.json"
    assert path.exists()
    return path


@pytest.fixture(scope="module")
def node_ports_config(
    postgres_dsn: Dict[str, str], minio_config: Dict[str, str]
) -> None:
    node_config.POSTGRES_DB = postgres_dsn["database"]
    node_config.POSTGRES_ENDPOINT = f"{postgres_dsn['host']}:{postgres_dsn['port']}"
    node_config.POSTGRES_USER = postgres_dsn["user"]
    node_config.POSTGRES_PW = postgres_dsn["password"]
    node_config.BUCKET = minio_config["bucket_name"]
