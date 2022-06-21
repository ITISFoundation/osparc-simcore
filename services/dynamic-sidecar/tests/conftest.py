# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
import os
import random
import sys
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterable, Iterator, List
from unittest.mock import AsyncMock, Mock

import aiodocker
import pytest
from async_asgi_testclient import TestClient
from faker import Faker
from fastapi import FastAPI
from pytest import MonkeyPatch
from pytest_mock.plugin import MockerFixture
from simcore_service_dynamic_sidecar.core import utils
from simcore_service_dynamic_sidecar.core.application import assemble_application
from simcore_service_dynamic_sidecar.core.docker_utils import docker_client
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings
from simcore_service_dynamic_sidecar.core.shared_handlers import (
    write_file_and_run_command,
)
from simcore_service_dynamic_sidecar.models.domains.shared_store import SharedStore
from simcore_service_dynamic_sidecar.modules import mounted_fs

pytest_plugins = [
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
]
CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    folder = CURRENT_DIR.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_dynamic_sidecar"))
    return folder


@pytest.fixture
def mock_dy_volumes(tmp_path: Path) -> Iterator[Path]:
    return tmp_path / "dy-volumes"


@pytest.fixture
def io_temp_dir(tmp_path: Path) -> Path:
    return tmp_path / "io"


@pytest.fixture
def compose_namespace(faker: Faker) -> str:
    return f"dy-sidecar_{faker.uuid4()}"


@pytest.fixture
def inputs_dir(io_temp_dir: Path) -> Path:
    return io_temp_dir / "inputs"


@pytest.fixture
def outputs_dir(io_temp_dir: Path) -> Path:
    return io_temp_dir / "outputs"


@pytest.fixture
def state_paths_dirs(io_temp_dir: Path) -> List[Path]:
    return [io_temp_dir / f"dir_{i}" for i in range(4)]


@pytest.fixture
def state_exclude_dirs(io_temp_dir: Path) -> List[Path]:
    return [io_temp_dir / f"dir_exclude_{i}" for i in range(4)]


@pytest.fixture
def mock_environment(
    monkeypatch: MonkeyPatch,
    mock_dy_volumes: Path,
    compose_namespace: str,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: List[Path],
    state_exclude_dirs: List[Path],
    faker: Faker,
) -> None:
    monkeypatch.setenv("SC_BOOT_MODE", "production")
    monkeypatch.setenv("DYNAMIC_SIDECAR_COMPOSE_NAMESPACE", compose_namespace)
    monkeypatch.setenv("REGISTRY_AUTH", "false")
    monkeypatch.setenv("REGISTRY_USER", "test")
    monkeypatch.setenv("REGISTRY_PW", "test")
    monkeypatch.setenv("REGISTRY_SSL", "false")
    monkeypatch.setenv("DY_SIDECAR_USER_ID", "1")
    monkeypatch.setenv("DY_SIDECAR_PROJECT_ID", f"{faker.uuid4()}")
    monkeypatch.setenv("DY_SIDECAR_NODE_ID", f"{faker.uuid4()}")
    monkeypatch.setenv("DY_SIDECAR_RUN_ID", f"{faker.uuid4()}")
    monkeypatch.setenv("DY_SIDECAR_PATH_INPUTS", f"{inputs_dir}")
    monkeypatch.setenv("DY_SIDECAR_PATH_OUTPUTS", f"{outputs_dir}")
    monkeypatch.setenv(
        "DY_SIDECAR_STATE_PATHS", json.dumps([f"{x}" for x in state_paths_dirs])
    )
    monkeypatch.setenv(
        "DY_SIDECAR_STATE_EXCLUDE", json.dumps([f"{x}" for x in state_exclude_dirs])
    )
    monkeypatch.setenv("RABBIT_SETTINGS", "null")

    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")

    monkeypatch.setattr(mounted_fs, "DY_VOLUMES", mock_dy_volumes)


@pytest.fixture
def disable_registry_check(monkeypatch: MonkeyPatch) -> None:
    mock = Mock(return_value=None)
    monkeypatch.setattr(utils, "_is_registry_reachable", mock)


@pytest.fixture
def app(mock_environment: None, disable_registry_check: None) -> FastAPI:
    app = assemble_application()
    app.state.rabbitmq = AsyncMock()
    return app


@pytest.fixture
def dynamic_sidecar_settings() -> DynamicSidecarSettings:
    return DynamicSidecarSettings.create_from_envs()


@pytest.fixture
async def ensure_external_volumes(
    compose_namespace: str,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: List[Path],
    dynamic_sidecar_settings: DynamicSidecarSettings,
) -> AsyncGenerator[None, None]:
    """ensures inputs and outputs volumes for the service are present"""

    volume_names = []
    for state_paths_dir in [inputs_dir, outputs_dir] + state_paths_dirs:
        name_from_path = str(state_paths_dir).replace(os.sep, "_")
        volume_names.append(f"{compose_namespace}{name_from_path}")

    async with docker_client() as client:
        volumes = await asyncio.gather(
            *[
                client.volumes.create(
                    {
                        "Labels": {
                            "source": volume_name,
                            "run_id": f"{dynamic_sidecar_settings.DY_SIDECAR_RUN_ID}",
                        }
                    }
                )
                for volume_name in volume_names
            ]
        )

        yield

        await asyncio.gather(*[volume.delete() for volume in volumes])


@pytest.fixture
async def test_client(app: FastAPI) -> AsyncIterable[TestClient]:
    async with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)  # <----- TODO: PC->ANE!!
async def cleanup_containers(
    app: FastAPI, ensure_external_volumes: None
) -> AsyncGenerator[None, None]:

    yield
    # run docker compose down here

    shared_store: SharedStore = app.state.shared_store
    stored_compose_content = shared_store.compose_spec

    if stored_compose_content is None:
        # if no compose-spec is stored skip this operation
        return

    settings: DynamicSidecarSettings = app.state.settings
    command = (
        "docker-compose -p {project} -f {file_path} "
        "down --remove-orphans -t {stop_and_remove_timeout}"
    )
    await write_file_and_run_command(
        settings=settings,
        file_content=stored_compose_content,
        command=command,
        command_timeout=5.0,
    )


@pytest.fixture
def mock_containers_get(mocker: MockerFixture) -> int:
    """raises a DockerError with a random HTTP status which is also returned"""
    mock_status_code = random.randint(1, 999)

    async def mock_get(*args: str, **kwargs: Any) -> None:
        raise aiodocker.exceptions.DockerError(
            status=mock_status_code, data=dict(message="aiodocker_mocked_error")
        )

    mocker.patch("aiodocker.containers.DockerContainers.get", side_effect=mock_get)

    return mock_status_code


@pytest.fixture
def mock_dir_watcher_on_any_event(
    app: FastAPI, monkeypatch: MonkeyPatch
) -> Iterator[Mock]:

    mock = Mock(return_value=None)

    monkeypatch.setattr(
        app.state.dir_watcher.outputs_event_handle, "_invoke_push_directory", mock
    )
    yield mock
