# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
import logging
import sys
from collections.abc import AsyncIterable, Iterable, Iterator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import simcore_service_dynamic_sidecar
from common_library.json_serialization import json_dumps
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.services import RunID
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import (
    EnvVarsDict,
    setenvs_from_dict,
    setenvs_from_envfile,
)
from simcore_service_dynamic_sidecar.core.reserved_space import (
    remove_reserved_disk_space,
)

logger = logging.getLogger(__name__)

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.minio_service",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.simcore_service_library_fixtures",
    "pytest_simcore.socketio",
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
def project_id(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def run_id() -> RunID:
    return RunID.create()


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
def mock_storage_check(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.core.external_dependencies.wait_for_storage_liveness",
    )


@pytest.fixture
def mock_postgres_check(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.core.external_dependencies.wait_for_postgres_liveness",
    )


@pytest.fixture
def mock_rabbit_check(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.core.external_dependencies.wait_for_rabbitmq_liveness",
    )


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
        "DY_SIDECAR_RUN_ID": f"{run_id}",
        "DY_SIDECAR_NODE_ID": f"{node_id}",
        "DY_SIDECAR_PATH_INPUTS": f"{inputs_dir}",
        "DY_SIDECAR_PATH_OUTPUTS": f"{outputs_dir}",
        "DY_SIDECAR_STATE_PATHS": json_dumps(state_paths_dirs),
        "DY_SIDECAR_STATE_EXCLUDE": json_dumps(state_exclude_dirs),
        "DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS": "false",
        "DY_DEPLOYMENT_REGISTRY_SETTINGS": json.dumps(
            {
                "REGISTRY_AUTH": "false",
                "REGISTRY_USER": "test",
                "REGISTRY_PW": "test",
                "REGISTRY_SSL": "false",
                "REGISTRY_URL": "registry.pytest.com",
            }
        ),
        "DYNAMIC_SIDECAR_TRACING": "null",
    }


@pytest.fixture
def mock_environment(
    mock_storage_check: None,
    mock_postgres_check: None,
    mock_rabbit_check: None,
    monkeypatch: pytest.MonkeyPatch,
    base_mock_envs: EnvVarsDict,
    user_id: UserID,
    project_id: ProjectID,
    state_paths_dirs: list[Path],
    state_exclude_dirs: list[Path],
    node_id: NodeID,
    run_id: RunID,
    inputs_dir: Path,
    compose_namespace: str,
    outputs_dir: Path,
    dy_volumes: Path,
    shared_store_dir: Path,
    faker: Faker,
) -> EnvVarsDict:
    """Main test environment used to build the application

    Override if new configuration for the app is needed.
    """
    return setenvs_from_dict(
        monkeypatch,
        {
            # envs in Dockerfile
            "DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR": f"{dy_volumes}",
            "DYNAMIC_SIDECAR_SHARED_STORE_DIR": f"{shared_store_dir}",
            "SC_BOOT_MODE": "production",
            "SC_BUILD_TARGET": "production",
            # envs on container
            "DY_SIDECAR_CALLBACKS_MAPPING": "{}",
            "DY_SIDECAR_NODE_ID": f"{node_id}",
            "DY_SIDECAR_PATH_INPUTS": f"{inputs_dir}",
            "DY_SIDECAR_PATH_OUTPUTS": f"{outputs_dir}",
            "DY_SIDECAR_PROJECT_ID": f"{project_id}",
            "DY_SIDECAR_RUN_ID": run_id,
            "DY_SIDECAR_STATE_EXCLUDE": json_dumps(state_exclude_dirs),
            "DY_SIDECAR_STATE_PATHS": json_dumps(state_paths_dirs),
            "DY_SIDECAR_USER_ID": f"{user_id}",
            "DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS": "false",
            "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": compose_namespace,
            "POSTGRES_DB": "test",
            "POSTGRES_HOST": "test",
            "POSTGRES_PASSWORD": "test",
            "POSTGRES_USER": "test",
            "R_CLONE_PROVIDER": "MINIO",
            "RABBIT_HOST": "test",
            "RABBIT_PASSWORD": "test",
            "RABBIT_SECURE": "false",
            "RABBIT_USER": "test",
            "S3_ACCESS_KEY": faker.pystr(),
            "S3_BUCKET_NAME": faker.pystr(),
            "S3_ENDPOINT": faker.url(),
            "S3_REGION": faker.pystr(),
            "S3_SECRET_KEY": faker.pystr(),
            "DY_DEPLOYMENT_REGISTRY_SETTINGS": json.dumps(
                {
                    "REGISTRY_AUTH": "false",
                    "REGISTRY_USER": "test",
                    "REGISTRY_PW": "test",
                    "REGISTRY_SSL": "false",
                    "REGISTRY_URL": "registry.pytest.com",
                }
            ),
        },
    )


@pytest.fixture
def mock_environment_with_envdevel(
    monkeypatch: pytest.MonkeyPatch, project_slug_dir: Path
) -> EnvVarsDict:
    """Alternative environment loaded fron .env-devel.

    .env-devel is used mainly to run CLI
    """
    env_file = project_slug_dir / ".env-devel"
    return setenvs_from_envfile(monkeypatch, env_file.read_text())


@pytest.fixture()
def caplog_info_debug(
    caplog: pytest.LogCaptureFixture,
) -> Iterable[pytest.LogCaptureFixture]:
    with caplog.at_level(logging.DEBUG):
        yield caplog


@pytest.fixture
def mock_registry_service(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_dynamic_sidecar.core.registry._login_registry",
        autospec=True,
    )


@pytest.fixture
def mock_core_rabbitmq(mocker: MockerFixture) -> dict[str, AsyncMock]:
    """mocks simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQClient member functions"""
    return {
        "wait_till_rabbitmq_responsive": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.wait_for_rabbitmq_liveness",
            return_value=None,
            autospec=True,
        ),
        "post_rabbit_message": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq._post_rabbit_message",
            return_value=None,
            autospec=True,
        ),
        "close": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQClient.close",
            return_value=None,
            autospec=True,
        ),
        "rpc._rpc_initialize": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQRPCClient._rpc_initialize",
            return_value=None,
            autospec=True,
        ),
        "rpc.close": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQRPCClient.close",
            return_value=None,
            autospec=True,
        ),
        "rpc.register_router": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQRPCClient.register_router",
            return_value=None,
            autospec=True,
        ),
    }


@pytest.fixture
def mock_stop_heart_beat_task(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_dynamic_sidecar.modules.resource_tracking._core.stop_heart_beat_task",
        return_value=None,
    )


@pytest.fixture
def mock_metrics_params(faker: Faker) -> CreateServiceMetricsAdditionalParams:
    return TypeAdapter(CreateServiceMetricsAdditionalParams).validate_python(
        CreateServiceMetricsAdditionalParams.model_config["json_schema_extra"][
            "example"
        ],
    )


@pytest.fixture
def cleanup_reserved_disk_space() -> AsyncIterable[None]:
    remove_reserved_disk_space()
    yield
    remove_reserved_disk_space()
