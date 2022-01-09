# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import asyncio
import json
import os
import random
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterable, Iterator, List
from unittest.mock import AsyncMock

import aiodocker
import pytest
from _pytest.monkeypatch import MonkeyPatch
from async_asgi_testclient import TestClient
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture
from simcore_service_dynamic_sidecar.core import utils
from simcore_service_dynamic_sidecar.core.application import assemble_application
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings
from simcore_service_dynamic_sidecar.core.shared_handlers import (
    write_file_and_run_command,
)
from simcore_service_dynamic_sidecar.core.utils import docker_client
from simcore_service_dynamic_sidecar.models.domains.shared_store import SharedStore
from simcore_service_dynamic_sidecar.modules import mounted_fs

pytest_plugins = [
    "pytest_simcore.monkeypatch_extra",
]


@pytest.fixture(scope="session")
def mock_dy_volumes() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(scope="session")
def io_temp_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(scope="session")
def compose_namespace() -> str:
    return f"dy-sidecar_{uuid.uuid4()}"


@pytest.fixture(scope="session")
def inputs_dir(io_temp_dir: Path) -> Path:
    return io_temp_dir / "inputs"


@pytest.fixture(scope="session")
def outputs_dir(io_temp_dir: Path) -> Path:
    return io_temp_dir / "outputs"


@pytest.fixture(scope="session")
def state_paths_dirs(io_temp_dir: Path) -> List[Path]:
    return [io_temp_dir / f"dir_{x}" for x in range(4)]


@pytest.fixture(scope="module")
def mock_environment(
    monkeypatch_module: MonkeyPatch,
    mock_dy_volumes: Path,
    compose_namespace: str,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: List[Path],
) -> None:
    monkeypatch_module.setenv("SC_BOOT_MODE", "production")
    monkeypatch_module.setenv("DYNAMIC_SIDECAR_compose_namespace", compose_namespace)
    monkeypatch_module.setenv("REGISTRY_AUTH", "false")
    monkeypatch_module.setenv("REGISTRY_USER", "test")
    monkeypatch_module.setenv("REGISTRY_PW", "test")
    monkeypatch_module.setenv("REGISTRY_SSL", "false")
    monkeypatch_module.setenv("DY_SIDECAR_USER_ID", "1")
    monkeypatch_module.setenv("DY_SIDECAR_PROJECT_ID", f"{uuid.uuid4()}")
    monkeypatch_module.setenv("DY_SIDECAR_NODE_ID", f"{uuid.uuid4()}")
    monkeypatch_module.setenv("DY_SIDECAR_PATH_INPUTS", str(inputs_dir))
    monkeypatch_module.setenv("DY_SIDECAR_PATH_OUTPUTS", str(outputs_dir))
    monkeypatch_module.setenv(
        "DY_SIDECAR_STATE_PATHS", json.dumps([str(x) for x in state_paths_dirs])
    )
    monkeypatch_module.setenv("RABBIT_SETTINGS", "null")

    monkeypatch_module.setattr(mounted_fs, "DY_VOLUMES", mock_dy_volumes)


@pytest.fixture(scope="module")
def disable_registry_check(monkeypatch_module: MockerFixture) -> None:
    async def _mock_is_registry_reachable(*args, **kwargs) -> None:
        pass

    monkeypatch_module.setattr(
        utils, "_is_registry_reachable", _mock_is_registry_reachable
    )


@pytest.fixture(scope="module")
def app(mock_environment: None, disable_registry_check: None) -> FastAPI:
    app = assemble_application()
    app.state.rabbitmq = AsyncMock()
    return app


@pytest.fixture
async def ensure_external_volumes(
    compose_namespace: str,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: List[Path],
) -> AsyncGenerator[None, None]:
    """ensures inputs and outputs volumes for the service are present"""

    volume_names = []
    for state_paths_dir in [inputs_dir, outputs_dir] + state_paths_dirs:
        name_from_path = str(state_paths_dir).replace(os.sep, "_")
        volume_names.append(f"{compose_namespace}{name_from_path}")

    async with docker_client() as client:
        volumes = await asyncio.gather(
            *[
                client.volumes.create({"Name": volume_name})
                for volume_name in volume_names
            ]
        )

        yield

        await asyncio.gather(*[volume.delete() for volume in volumes])


@pytest.fixture
async def test_client(app: FastAPI) -> AsyncIterable[TestClient]:
    async with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
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
def tests_dir() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
