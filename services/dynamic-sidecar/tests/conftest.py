# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import json
import os
import random
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Iterator, List
from unittest import mock

import aiodocker
import pytest
from async_asgi_testclient import TestClient
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture
from simcore_service_dynamic_sidecar.core.application import assemble_application
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings
from simcore_service_dynamic_sidecar.core.shared_handlers import (
    write_file_and_run_command,
)
from simcore_service_dynamic_sidecar.core.utils import docker_client
from simcore_service_dynamic_sidecar.models.domains.shared_store import SharedStore
from simcore_service_dynamic_sidecar.modules import mounted_fs


@pytest.fixture(scope="module")
def mock_dy_volumes() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(scope="module")
def io_temp_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(scope="module")
def compose_namespace() -> str:
    return "test-space"


@pytest.fixture(scope="module", autouse=True)
def app(
    io_temp_dir: Path, mock_dy_volumes: Path, compose_namespace: str
) -> Iterator[FastAPI]:
    inputs_dir = io_temp_dir / "inputs"
    outputs_dir = io_temp_dir / "outputs"
    state_paths_dirs: List[str] = [str(io_temp_dir / f"dir_{x}") for x in range(4)]
    with mock.patch.dict(
        os.environ,
        {
            "SC_BOOT_MODE": "production",
            "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": compose_namespace,
            "REGISTRY_AUTH": "false",
            "REGISTRY_USER": "test",
            "REGISTRY_PW": "test",
            "REGISTRY_SSL": "false",
            "DY_SIDECAR_PATH_INPUTS": str(inputs_dir),
            "DY_SIDECAR_PATH_OUTPUTS": str(outputs_dir),
            "DY_SIDECAR_STATE_PATHS": json.dumps(state_paths_dirs),
            "DY_SIDECAR_USER_ID": "1",
            "DY_SIDECAR_PROJECT_ID": f"{uuid.uuid4()}",
            "DY_SIDECAR_NODE_ID": f"{uuid.uuid4()}",
        },
    ), mock.patch.object(mounted_fs, "DY_VOLUMES", mock_dy_volumes):
        print(os.environ)
        yield assemble_application()


@pytest.fixture
async def ensure_external_volumes(compose_namespace: str) -> AsyncGenerator[None, None]:
    """ensures inputs and outputs volumes for the service are present"""
    async with docker_client() as client:
        inputs_volume = await client.volumes.create(
            {"Name": f"{compose_namespace}_inputs"}
        )
        outputs_volume = await client.volumes.create(
            {"Name": f"{compose_namespace}_outputs"}
        )

        yield

        await inputs_volume.delete()
        await outputs_volume.delete()


@pytest.fixture
async def test_client(app: FastAPI) -> TestClient:
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
