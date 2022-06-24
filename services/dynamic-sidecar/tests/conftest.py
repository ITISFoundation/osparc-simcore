# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
import random
import sys
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterable, AsyncIterator, Iterator
from unittest.mock import AsyncMock, Mock

import aiodocker
import pytest
from aiodocker.volumes import DockerVolume
from async_asgi_testclient import TestClient
from faker import Faker
from fastapi import FastAPI
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.core.application import AppState, create_app
from simcore_service_dynamic_sidecar.core.docker_utils import docker_client
from simcore_service_dynamic_sidecar.core.shared_handlers import (
    write_file_and_run_command,
)

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
def mock_dy_volumes(tmp_path: Path) -> Path:
    return tmp_path / "host-common-dy-volumes"


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
def mock_environment(
    monkeypatch: MonkeyPatch,
    mock_dy_volumes: Path,
    compose_namespace: str,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: list[Path],
    state_exclude_dirs: list[Path],
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

    monkeypatch.setenv("DYNAMIC_SIDECAR_DY_VOLUMES_COMMON_DIR", f"{mock_dy_volumes}")


@pytest.fixture
def mock_registry_service(mocker: MockerFixture) -> None:
    # TODO: PC->ANE: from respx import MockRouter registry instead.
    # It can be reused to setup different scenarios like registry down etc
    mock = mocker.patch(
        "simcore_service_dynamic_sidecar.core.utils._is_registry_reachable"
    )


@pytest.fixture
def mock_rabbitmq(mocker) -> dict[str, AsyncMock]:
    return {
        "connect": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQ.connect",
            return_value=None,
        ),
        "post_log_message": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQ.post_log_message",
            return_value=None,
        ),
        "close": mocker.patch(
            "simcore_service_dynamic_sidecar.core.rabbitmq.RabbitMQ.close",
            return_value=None,
        ),
    }


@pytest.fixture
def app(
    mock_environment: None, mock_registry_service: None, mock_rabbitmq: None
) -> FastAPI:
    app = create_app()
    app.state.rabbitmq = AsyncMock()
    return app


@pytest.fixture
async def test_client(app: FastAPI) -> AsyncIterable[TestClient]:
    async with TestClient(app) as client:
        yield client


@pytest.fixture
async def ensure_external_volumes(
    app: FastAPI,
) -> AsyncIterator[tuple[DockerVolume]]:
    """ensures inputs and outputs volumes for the service are present"""
    # Emulates from directorv2

    app_state = AppState(app)
    volume_names = [
        app_state.mounted_volumes.volume_name_inputs,
        app_state.mounted_volumes.volume_name_outputs,
    ] + app_state.mounted_volumes.volume_names_for_states

    async with docker_client() as client:

        # TODO: rm old volumes?
        volumes = await asyncio.gather(
            *[
                # NOTE: This is responsibility of the director
                client.volumes.create(
                    {
                        "Labels": {
                            "source": volume_name,
                            "run_id": f"{app_state.settings.DY_SIDECAR_RUN_ID}",
                        }
                    }
                )
                for volume_name in volume_names
            ]
        )

        # Example
        # {
        #   "CreatedAt": "2022-06-23T03:22:08+02:00",
        #   "Driver": "local",
        #   "Labels": {
        #       "run_id": "f7c1bd87-4da5-4709-9471-3d60c8a70639",
        #       "source": "dy-sidecar_e3e70682-c209-4cac-a29f-6fbed82c07cd_data_dir_2"
        #   },
        #   "Mountpoint": "/var/lib/docker/volumes/22bfd79a50eb9097d45cc946736cb66f3670a2fadccb62a77ffbe5e1d88f0034/_data",
        #   "Name": "22bfd79a50eb9097d45cc946736cb66f3670a2fadccb62a77ffbe5e1d88f0034",
        #   "Options": null,
        #   "Scope": "local",
        #   "CreatedTime": 1655947328000,
        #   "Containers": {}
        # }

        # docker volume rm $(docker volume ls --format "{{.Name}} {{.Labels}}" | grep run_id | awk '{print $1}')
        yield volumes

        # TODO: SAN retry if this is link to some container because will fail to delete until container is down
        deleted = await asyncio.gather(
            *[volume.delete() for volume in volumes], return_exceptions=True
        )
        assert not [d for d in deleted if isinstance(d, Exception)]


@pytest.fixture
async def cleanup_containers(app: FastAPI) -> AsyncGenerator[None, None]:

    app_state = AppState(app)

    yield
    # run docker compose down here

    if app_state.shared_store.compose_spec is None:
        # if no compose-spec is stored skip this operation
        return

    command = (
        "docker-compose -p {project} -f {file_path} "
        "down --remove-orphans -t {stop_and_remove_timeout}"
    )
    await write_file_and_run_command(
        settings=app_state.settings,
        file_content=app_state.shared_store.compose_spec,
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
