# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import logging
import sys
from pathlib import Path
from uuid import UUID

import pytest
import simcore_service_dynamic_sidecar
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.users import UserID
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_envfile
from servicelib.json_serialization import json_dumps

logger = logging.getLogger(__name__)

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.monkeypatch_extra",  # TODO: remove this dependency
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.tmp_path_extra",
]

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def package_dir() -> Path:
    folder = Path(simcore_service_dynamic_sidecar.__file__).resolve().parent
    assert folder.exists()
    return folder


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    folder = CURRENT_DIR.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_dynamic_sidecar"))
    return folder


#
# Fixtures associated to the configuration of a dynamic-sidecar service
#  - Can be used both to create new fixture or as references
#


@pytest.fixture
def dy_volumes(tmp_path: Path) -> Path:
    """mount folder on the sidecar (path withn the sidecar)"""
    return tmp_path / "dy-volumes"


@pytest.fixture
def container_base_dir() -> Path:
    return Path("/data")


@pytest.fixture
def compose_namespace(faker: Faker) -> str:
    return f"dy-sidecar_{faker.uuid4()}"


@pytest.fixture
def inputs_dir(container_base_dir: Path) -> Path:
    return container_base_dir / "inputs"


@pytest.fixture
def outputs_dir(container_base_dir: Path) -> Path:
    return container_base_dir / "outputs"


@pytest.fixture
def state_paths_dirs(container_base_dir: Path) -> list[Path]:
    return [container_base_dir / f"state_dir{i}" for i in range(4)]


@pytest.fixture
def state_exclude_dirs(container_base_dir: Path) -> list[Path]:
    return [container_base_dir / f"exclude_{i}" for i in range(4)]


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def run_id(faker: Faker) -> UUID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def mock_environment(
    monkeypatch: MonkeyPatch,
    dy_volumes: Path,
    compose_namespace: str,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: list[Path],
    state_exclude_dirs: list[Path],
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    run_id: UUID,
) -> None:
    """Main test environment used to build the application

    Override if new configuration for the app is needed.
    """
    # envs in Dockerfile
    monkeypatch.setenv("SC_BOOT_MODE", "production")
    monkeypatch.setenv("SC_BUILD_TARGET", "production")
    monkeypatch.setenv("DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR", f"{dy_volumes}")

    # envs on container
    monkeypatch.setenv("DYNAMIC_SIDECAR_COMPOSE_NAMESPACE", compose_namespace)

    monkeypatch.setenv("REGISTRY_AUTH", "false")
    monkeypatch.setenv("REGISTRY_USER", "test")
    monkeypatch.setenv("REGISTRY_PW", "test")
    monkeypatch.setenv("REGISTRY_SSL", "false")

    monkeypatch.setenv("DY_SIDECAR_USER_ID", f"{user_id}")
    monkeypatch.setenv("DY_SIDECAR_PROJECT_ID", f"{project_id}")
    monkeypatch.setenv("DY_SIDECAR_RUN_ID", f"{run_id}")
    monkeypatch.setenv("DY_SIDECAR_NODE_ID", f"{node_id}")
    monkeypatch.setenv("DY_SIDECAR_PATH_INPUTS", f"{inputs_dir}")
    monkeypatch.setenv("DY_SIDECAR_PATH_OUTPUTS", f"{outputs_dir}")
    monkeypatch.setenv("DY_SIDECAR_STATE_PATHS", json_dumps(state_paths_dirs))
    monkeypatch.setenv("DY_SIDECAR_STATE_EXCLUDE", json_dumps(state_exclude_dirs))

    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")

    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")


@pytest.fixture
def mock_environment_with_envdevel(
    monkeypatch: MonkeyPatch, project_slug_dir: Path
) -> EnvVarsDict:
    """Alternative environment loaded fron .env-devel.

    .env-devel is used mainly to run CLI
    """
    env_file = project_slug_dir / ".env-devel"
    envs = setenvs_from_envfile(monkeypatch, env_file.read_text())
    return envs
