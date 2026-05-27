# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import ByteSize, TypeAdapter
from settings_library.tracing import TracingSettings
from simcore_service_dynamic_sidecar.core.settings import UserServiceTracingSettings
from simcore_service_dynamic_sidecar.modules.user_services_tracing import (
    _ACTIVE_FILE_NAME,
    UserServicesTraceForwarder,
)

_DEFAULT_TRACING_OVERRIDES: dict[str, Any] = {
    "USER_SERVICES_TRACING_SCRAPE_INTERVAL_S": 0.1,
    "USER_SERVICES_TRACING_MAX_BATCH_SIZE": TypeAdapter(ByteSize).validate_python("1MiB"),
    "USER_SERVICES_TRACING_COLLECTOR_IMAGE": "otel/opentelemetry-collector:0.100.0",
    "USER_SERVICES_TRACING_COLLECTOR_MAX_FILE_SIZE_MB": 10,
    "USER_SERVICES_TRACING_COLLECTOR_MAX_BACKUPS": 5,
    "USER_SERVICES_TRACING_COLLECTOR_FLUSH_INTERVAL_S": 10,
    "USER_SERVICES_TRACING_DRAIN_TIMEOUT_S": 5.0,
    "USER_SERVICES_TRACING_COLLECTOR_STOP_GRACE_PERIOD_S": 15,
}


@pytest.fixture
def traces_directory(tmp_path: Path) -> Path:
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    return traces_dir


@pytest.fixture
def tracing_settings_factory() -> Callable[..., UserServiceTracingSettings]:
    def _factory(**overrides: Any) -> UserServiceTracingSettings:
        params = {**_DEFAULT_TRACING_OVERRIDES, **overrides}
        return UserServiceTracingSettings(**params)

    return _factory


@pytest.fixture
def tracing_settings(
    tracing_settings_factory: Callable[..., UserServiceTracingSettings],
) -> UserServiceTracingSettings:
    return tracing_settings_factory()


@pytest.fixture
def platform_tracing_settings() -> TracingSettings:
    return TracingSettings(
        TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT="http://otel-collector.internal",
        TRACING_OPENTELEMETRY_COLLECTOR_PORT=4318,
        TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY=1.0,
    )


@pytest.fixture
def sample_span_line() -> bytes:
    span = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "service.name",
                            "value": {"stringValue": "test-svc"},
                        }
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "abc123",
                                "spanId": "def456",
                                "name": "test-span",
                                "startTimeUnixNano": "1000000000",
                                "endTimeUnixNano": "2000000000",
                            }
                        ]
                    }
                ],
            }
        ]
    }
    return json.dumps(span).encode()


@pytest.fixture
def forwarder(
    traces_directory: Path,
    tracing_settings: UserServiceTracingSettings,
    platform_tracing_settings: TracingSettings,
) -> UserServicesTraceForwarder:
    return UserServicesTraceForwarder(
        traces_directory=traces_directory,
        tracing_settings=tracing_settings,
        platform_tracing_settings=platform_tracing_settings,
    )


@pytest.fixture
def mock_successful_post() -> AsyncMock:
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    return AsyncMock(return_value=mock_response)


async def test_forwarder_ignores_active_file(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
):
    """Active file (spans.jsonl) should not be forwarded during normal scraping."""
    active_file = traces_directory / _ACTIVE_FILE_NAME
    active_file.write_bytes(sample_span_line)

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = AsyncMock()
        await forwarder._forward_rotated_files()

    mock_client.post.assert_not_called()
    assert active_file.exists()


async def test_forwarder_processes_rotated_files(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
    mock_successful_post: AsyncMock,
):
    """Rotated files should be forwarded and deleted."""
    rotated_file = traces_directory / "spans-20250101T000000.jsonl"
    rotated_file.write_bytes(sample_span_line)

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = mock_successful_post
        await forwarder._forward_rotated_files()

    mock_client.post.assert_called_once()
    assert not rotated_file.exists()


async def test_forwarder_keeps_file_on_http_error(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
):
    """Files should be kept for retry if HTTP POST fails."""
    rotated_file = traces_directory / "spans-20250101T000000.jsonl"
    rotated_file.write_bytes(sample_span_line)

    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 500

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = AsyncMock(return_value=mock_response)
        await forwarder._forward_rotated_files()

    assert rotated_file.exists()


async def test_forwarder_keeps_file_on_network_error(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
):
    """Files should be kept for retry if network error occurs."""
    rotated_file = traces_directory / "spans-20250101T000000.jsonl"
    rotated_file.write_bytes(sample_span_line)

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        await forwarder._forward_rotated_files()

    assert rotated_file.exists()


async def test_forwarder_drain_processes_all_files(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
    mock_successful_post: AsyncMock,
):
    """Drain should process ALL files including the active one."""
    active_file = traces_directory / _ACTIVE_FILE_NAME
    active_file.write_bytes(sample_span_line)

    rotated_file = traces_directory / "spans-20250101T000000.jsonl"
    rotated_file.write_bytes(sample_span_line)

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = mock_successful_post
        await forwarder.drain_remaining_traces()

    assert not active_file.exists()
    assert not rotated_file.exists()
    assert mock_client.post.call_count == 2


async def test_forwarder_drain_respects_timeout(
    traces_directory: Path,
    tracing_settings_factory: Callable[..., UserServiceTracingSettings],
    platform_tracing_settings: TracingSettings,
    sample_span_line: bytes,
):
    """Drain should stop after timeout even if files remain."""
    short_timeout_settings = tracing_settings_factory(
        USER_SERVICES_TRACING_DRAIN_TIMEOUT_S=0.1,
    )
    timeout_forwarder = UserServicesTraceForwarder(
        traces_directory=traces_directory,
        tracing_settings=short_timeout_settings,
        platform_tracing_settings=platform_tracing_settings,
    )

    rotated_file = traces_directory / "spans-20250101T000000.jsonl"
    rotated_file.write_bytes(sample_span_line)

    async def slow_post(*args, **kwargs):
        await asyncio.sleep(10)
        mock_resp = AsyncMock(spec=httpx.Response)
        mock_resp.status_code = 200
        return mock_resp

    with patch.object(timeout_forwarder, "_client") as mock_client:
        mock_client.post = slow_post
        await timeout_forwarder.drain_remaining_traces()

    assert rotated_file.exists()


async def test_forwarder_chunks_large_files(
    traces_directory: Path,
    tracing_settings_factory: Callable[..., UserServiceTracingSettings],
    platform_tracing_settings: TracingSettings,
    sample_span_line: bytes,
    mock_successful_post: AsyncMock,
):
    """Files larger than max_batch_size should be split into chunks."""
    small_batch_settings = tracing_settings_factory(
        USER_SERVICES_TRACING_MAX_BATCH_SIZE=TypeAdapter(ByteSize).validate_python("100B"),
    )
    chunked_forwarder = UserServicesTraceForwarder(
        traces_directory=traces_directory,
        tracing_settings=small_batch_settings,
        platform_tracing_settings=platform_tracing_settings,
    )

    rotated_file = traces_directory / "spans-20250101T000000.jsonl"
    content = sample_span_line + b"\n" + sample_span_line + b"\n" + sample_span_line
    rotated_file.write_bytes(content)

    with patch.object(chunked_forwarder, "_client") as mock_client:
        mock_client.post = mock_successful_post
        await chunked_forwarder._forward_rotated_files()  # noqa: SLF001

    assert mock_client.post.call_count > 1
    assert not rotated_file.exists()


async def test_forwarder_deletes_empty_files(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
):
    """Empty rotated files should be deleted without making HTTP calls."""
    empty_file = traces_directory / "spans-20250101T000000.jsonl"
    empty_file.write_bytes(b"")

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = AsyncMock()
        await forwarder._forward_rotated_files()  # noqa: SLF001

    mock_client.post.assert_not_called()
    assert not empty_file.exists()


async def test_forwarder_start_stop_lifecycle(
    forwarder: UserServicesTraceForwarder,
):
    """Forwarder can be started and stopped cleanly."""
    await forwarder.start()
    assert forwarder._scrape_task is not None  # noqa: SLF001
    assert not forwarder._scrape_task.done()  # noqa: SLF001

    await forwarder.stop()
    assert forwarder._scrape_task is None  # noqa: SLF001
