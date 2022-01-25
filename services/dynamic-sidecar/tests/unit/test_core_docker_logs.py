# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import json
from pathlib import Path
from typing import AsyncIterable, Dict, Iterable, List
from unittest.mock import AsyncMock
from uuid import uuid4

import aiodocker
import pytest
from _pytest.monkeypatch import MonkeyPatch
from async_asgi_testclient import TestClient
from fastapi import FastAPI
from simcore_service_dynamic_sidecar.core.application import assemble_application
from simcore_service_dynamic_sidecar.core.docker_logs import (
    _get_background_log_fetcher,
    start_log_fetching,
    stop_log_fetching,
)
from simcore_service_dynamic_sidecar.modules import mounted_fs

pytestmark = pytest.mark.asyncio


# FIXTURES


@pytest.fixture(scope="module")
def app(
    monkeypatch_module: MonkeyPatch,
    mock_dy_volumes: Path,
    inputs_dir: Path,
    outputs_dir: Path,
    state_paths_dirs: List[Path],
    state_exclude_dirs: List[Path],
    disable_registry_check: None,
) -> Iterable[FastAPI]:
    monkeypatch_module.setenv("SC_BOOT_MODE", "production")
    monkeypatch_module.setenv("DYNAMIC_SIDECAR_COMPOSE_NAMESPACE", "test-space")
    monkeypatch_module.setenv("REGISTRY_AUTH", "false")
    monkeypatch_module.setenv("REGISTRY_USER", "test")
    monkeypatch_module.setenv("REGISTRY_PW", "test")
    monkeypatch_module.setenv("REGISTRY_SSL", "false")
    monkeypatch_module.setenv("DY_SIDECAR_USER_ID", "1")
    monkeypatch_module.setenv("DY_SIDECAR_PROJECT_ID", f"{uuid4()}")
    monkeypatch_module.setenv("DY_SIDECAR_NODE_ID", f"{uuid4()}")
    monkeypatch_module.setenv("DY_SIDECAR_PATH_INPUTS", str(inputs_dir))
    monkeypatch_module.setenv("DY_SIDECAR_PATH_OUTPUTS", str(outputs_dir))
    monkeypatch_module.setenv(
        "DY_SIDECAR_STATE_PATHS", json.dumps([str(x) for x in state_paths_dirs])
    )
    monkeypatch_module.setenv(
        "DY_SIDECAR_STATE_EXCLUDE", json.dumps([str(x) for x in state_exclude_dirs])
    )

    monkeypatch_module.setattr(mounted_fs, "DY_VOLUMES", mock_dy_volumes)

    yield assemble_application()


@pytest.fixture
def mock_rabbitmq(mocker) -> Iterable[Dict[str, AsyncMock]]:
    yield {
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
async def container_name() -> AsyncIterable[str]:
    # docker run -it --rm busybox echo "test message"
    async with aiodocker.Docker() as client:
        container = await client.containers.run(
            config={
                "Cmd": ["/bin/ash", "-c", 'echo "test message"'],
                "Image": "busybox",
            }
        )
        container_inspect = await container.show()

        yield container_inspect["Name"][1:]

        await container.delete()


# TESTS


async def test_background_log_fetcher(
    mock_rabbitmq: Dict[str, AsyncMock], test_client: TestClient, container_name: str
) -> None:
    app: FastAPI = test_client.application
    assert _get_background_log_fetcher(app=app) is not None

    assert mock_rabbitmq["connect"].call_count == 1

    await start_log_fetching(app=app, container_name=container_name)

    # wait for background log fetcher
    await asyncio.sleep(1)
    assert mock_rabbitmq["post_log_message"].call_count == 1

    await stop_log_fetching(app=app, container_name=container_name)
    assert mock_rabbitmq["connect"].call_count == 1
