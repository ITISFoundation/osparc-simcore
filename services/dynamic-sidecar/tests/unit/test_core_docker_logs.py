# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from typing import AsyncIterable
from unittest.mock import AsyncMock

import aiodocker
import pytest
from async_asgi_testclient import TestClient
from fastapi import FastAPI
from pytest import MonkeyPatch
from simcore_service_dynamic_sidecar.core.docker_logs import (
    _get_background_log_fetcher,
    start_log_fetching,
    stop_log_fetching,
)


@pytest.fixture
def mock_environment(monkeypatch: MonkeyPatch, mock_environment: None) -> None:
    monkeypatch.setenv("DYNAMIC_SIDECAR_COMPOSE_NAMESPACE", "test-space")


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


async def test_background_log_fetcher(
    mock_core_rabbitmq: dict[str, AsyncMock],
    test_client: TestClient,
    container_name: str,
    app: FastAPI,
):
    assert _get_background_log_fetcher(app=app) is not None

    assert mock_core_rabbitmq["connect"].call_count == 1

    await start_log_fetching(app=app, container_name=container_name)

    # wait for background log fetcher
    await asyncio.sleep(1)
    assert mock_core_rabbitmq["post_log_message"].call_count == 1

    await stop_log_fetching(app=app, container_name=container_name)
    assert mock_core_rabbitmq["connect"].call_count == 1
