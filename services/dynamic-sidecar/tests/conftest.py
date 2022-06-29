# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import asyncio
import json
import logging
import os
import random
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterable, AsyncIterator, Iterator
from unittest.mock import AsyncMock, Mock

import aiodocker
import pytest
from _pytest.monkeypatch import MonkeyPatch
from async_asgi_testclient import TestClient
from fastapi import FastAPI
from pytest_mock.plugin import MockerFixture
from simcore_service_dynamic_sidecar.core import utils
from simcore_service_dynamic_sidecar.core.application import create_app
from simcore_service_dynamic_sidecar.core.docker_utils import docker_client
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings
from simcore_service_dynamic_sidecar.core.shared_handlers import (
    write_file_and_run_command,
)
from simcore_service_dynamic_sidecar.models.domains.shared_store import SharedStore
from simcore_service_dynamic_sidecar.modules import mounted_fs
from tenacity import retry
from tenacity.after import after_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)

pytest_plugins = [
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.monkeypatch_extra",
    "pytest_simcore.pytest_global_environs",
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
def state_paths_dirs(io_temp_dir: Path) -> list[Path]:
    return [io_temp_dir / f"dir_{x}" for x in range(4)]


@pytest.fixture(scope="session")
def state_exclude_dirs(io_temp_dir: Path) -> list[Path]:
    return [io_temp_dir / f"dir_exclude_{x}" for x in range(4)]


@pytest.fixture(scope="module")
def mock_environment(
    monkeypatch_module: MonkeyPatch,
    mock_dy_volumes: Path,
    compose_namespace: str,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: list[Path],
    state_exclude_dirs: list[Path],
) -> None:
    monkeypatch_module.setenv("SC_BOOT_MODE", "production")
    monkeypatch_module.setenv("DYNAMIC_SIDECAR_COMPOSE_NAMESPACE", compose_namespace)
    monkeypatch_module.setenv("REGISTRY_AUTH", "false")
    monkeypatch_module.setenv("REGISTRY_USER", "test")
    monkeypatch_module.setenv("REGISTRY_PW", "test")
    monkeypatch_module.setenv("REGISTRY_SSL", "false")
    monkeypatch_module.setenv("DY_SIDECAR_USER_ID", "1")
    monkeypatch_module.setenv("DY_SIDECAR_PROJECT_ID", f"{uuid.uuid4()}")
    monkeypatch_module.setenv("DY_SIDECAR_NODE_ID", f"{uuid.uuid4()}")
    monkeypatch_module.setenv("DY_SIDECAR_RUN_ID", f"{uuid.uuid4()}")
    monkeypatch_module.setenv("DY_SIDECAR_PATH_INPUTS", str(inputs_dir))
    monkeypatch_module.setenv("DY_SIDECAR_PATH_OUTPUTS", str(outputs_dir))
    monkeypatch_module.setenv(
        "DY_SIDECAR_STATE_PATHS", json.dumps([str(x) for x in state_paths_dirs])
    )
    monkeypatch_module.setenv(
        "DY_SIDECAR_STATE_EXCLUDE", json.dumps([str(x) for x in state_exclude_dirs])
    )
    monkeypatch_module.setenv("RABBIT_SETTINGS", "null")

    monkeypatch_module.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch_module.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch_module.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch_module.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch_module.setenv("S3_SECURE", "false")
    monkeypatch_module.setenv("R_CLONE_PROVIDER", "MINIO")

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
    app = create_app()
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
    state_paths_dirs: list[Path],
    dynamic_sidecar_settings: DynamicSidecarSettings,
) -> AsyncIterator[None]:
    """ensures inputs and outputs volumes for the service are present"""

    volume_labels_source = []
    for state_paths_dir in [inputs_dir, outputs_dir] + state_paths_dirs:
        name_from_path = str(state_paths_dir).replace(os.sep, "_")
        volume_labels_source.append(f"{compose_namespace}{name_from_path}")

    async with docker_client() as docker:

        volumes = await asyncio.gather(
            *[
                docker.volumes.create(
                    {
                        "Labels": {
                            "source": source,
                            "run_id": f"{dynamic_sidecar_settings.DY_SIDECAR_RUN_ID}",
                        }
                    }
                )
                for source in volume_labels_source
            ]
        )

        #
        # docker volume ls --format "{{.Name}} {{.Labels}}" | grep run_id | awk '{print $1}')
        #
        #
        # Example
        #   {
        #     "CreatedAt": "2022-06-23T03:22:08+02:00",
        #     "Driver": "local",
        #     "Labels": {
        #         "run_id": "f7c1bd87-4da5-4709-9471-3d60c8a70639",
        #         "source": "dy-sidecar_e3e70682-c209-4cac-a29f-6fbed82c07cd_data_dir_2"
        #     },
        #     "Mountpoint": "/var/lib/docker/volumes/22bfd79a50eb9097d45cc946736cb66f3670a2fadccb62a77ffbe5e1d88f0034/_data",
        #     "Name": "22bfd79a50eb9097d45cc946736cb66f3670a2fadccb62a77ffbe5e1d88f0034",
        #     "Options": null,
        #     "Scope": "local",
        #     "CreatedTime": 1655947328000,
        #     "Containers": {}
        #   }

        yield

        @retry(
            wait=wait_fixed(1),
            stop=stop_after_delay(3),
            reraise=True,
            after=after_log(logger, logging.WARNING),
        )
        async def _delete(volume):
            # Ocasionally might raise because volumes are mount to closing containers
            await volume.delete()

        deleted = await asyncio.gather(
            *(_delete(volume) for volume in volumes), return_exceptions=True
        )
        assert not [r for r in deleted if isinstance(r, Exception)]


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


@pytest.fixture
def mock_dir_watcher_on_any_event(
    app: FastAPI, monkeypatch: MonkeyPatch
) -> Iterator[Mock]:

    mock = Mock(return_value=None)

    monkeypatch.setattr(
        app.state.dir_watcher.outputs_event_handle, "_invoke_push_directory", mock
    )
    yield mock
