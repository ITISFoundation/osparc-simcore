# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import logging
import sys
from copy import deepcopy
from pathlib import Path
from typing import Iterable, Iterator
from unittest.mock import AsyncMock

import pytest
import simcore_service_dynamic_sidecar
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.services import RunID
from models_library.users import UserID
from pytest import LogCaptureFixture, MonkeyPatch
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_envs import (
    EnvVarsDict,
    setenvs_from_dict,
    setenvs_from_envfile,
)
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
    "pytest_simcore.simcore_service_library_fixtures",
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
def shared_store_dir(tmp_path: Path) -> Path:
    return tmp_path / "shared-store"


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
def run_id(faker: Faker) -> RunID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def ensure_shared_store_dir(shared_store_dir: Path) -> Iterator[Path]:
    shared_store_dir.mkdir(parents=True, exist_ok=True)
    assert shared_store_dir.exists() is True

    yield shared_store_dir

    # remove files and dir
    for f in shared_store_dir.glob("*"):
        f.unlink()
    shared_store_dir.rmdir()
    assert shared_store_dir.exists() is False


@pytest.fixture
def base_mock_envs(
    dy_volumes: Path,
    shared_store_dir: Path,
    compose_namespace: str,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: list[Path],
    state_exclude_dirs: list[Path],
    node_id: NodeID,
    run_id: RunID,
    ensure_shared_store_dir: None,
) -> EnvVarsDict:
    return {
        # envs in Dockerfile
        "SC_BOOT_MODE": "production",
        "SC_BUILD_TARGET": "production",
        "DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR": f"{dy_volumes}",
        "DYNAMIC_SIDECAR_SHARED_STORE_DIR": f"{shared_store_dir}",
        # envs on container
        "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": compose_namespace,
        "REGISTRY_AUTH": "false",
        "REGISTRY_USER": "test",
        "REGISTRY_PW": "test",
        "REGISTRY_SSL": "false",
        "DY_SIDECAR_RUN_ID": f"{run_id}",
        "DY_SIDECAR_NODE_ID": f"{node_id}",
        "DY_SIDECAR_PATH_INPUTS": f"{inputs_dir}",
        "DY_SIDECAR_PATH_OUTPUTS": f"{outputs_dir}",
        "DY_SIDECAR_STATE_PATHS": json_dumps(state_paths_dirs),
        "DY_SIDECAR_STATE_EXCLUDE": json_dumps(state_exclude_dirs),
        "DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS": "false",
    }


@pytest.fixture
def mock_environment(
    monkeypatch: MonkeyPatch,
    base_mock_envs: dict[str, str],
    user_id: UserID,
    project_id: ProjectID,
) -> EnvVarsDict:
    """Main test environment used to build the application

    Override if new configuration for the app is needed.
    """
    envs: EnvVarsDict = deepcopy(base_mock_envs)

    envs["DY_SIDECAR_USER_ID"] = f"{user_id}"
    envs["DY_SIDECAR_PROJECT_ID"] = f"{project_id}"

    envs["S3_ENDPOINT"] = "endpoint"
    envs["S3_ACCESS_KEY"] = "access_key"
    envs["S3_SECRET_KEY"] = "secret_key"
    envs["S3_BUCKET_NAME"] = "bucket_name"
    envs["S3_SECURE"] = "false"

    envs["R_CLONE_PROVIDER"] = "MINIO"

    setenvs_from_dict(monkeypatch, envs)

    return envs


@pytest.fixture
def mock_environment_with_envdevel(
    monkeypatch: MonkeyPatch, project_slug_dir: Path
) -> EnvVarsDict:
    """Alternative environment loaded fron .env-devel.

    .env-devel is used mainly to run CLI
    """
    env_file = project_slug_dir / ".env-devel"
    return setenvs_from_envfile(monkeypatch, env_file.read_text())


@pytest.fixture()
def caplog_info_debug(caplog: LogCaptureFixture) -> Iterable[LogCaptureFixture]:
    with caplog.at_level(logging.DEBUG):
        yield caplog


@pytest.fixture
def mock_registry_service(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_dynamic_sidecar.core.utils._is_registry_reachable",
        autospec=True,
    )


@pytest.fixture
def mock_core_rabbitmq(mocker: MockerFixture) -> dict[str, AsyncMock]:
    """mocks simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQClient member functions"""
    return {
        "wait_till_rabbitmq_responsive": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.wait_till_rabbitmq_responsive",
            return_value=None,
            autospec=True,
        ),
        "post_log_message": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq._post_rabbit_message",
            return_value=None,
            autospec=True,
        ),
        "close": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQClient.close",
            return_value=None,
            autospec=True,
        ),
    }
