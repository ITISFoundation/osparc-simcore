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
    "USER_SERVICES_TRACING_SCRAPE_INTERVAL": 0.1,
    "USER_SERVICES_TRACING_MAX_BATCH_SIZE": TypeAdapter(ByteSize).validate_python("1MiB"),
    "USER_SERVICES_TRACING_COLLECTOR_IMAGE": "otel/opentelemetry-collector:0.144.0",
    "USER_SERVICES_TRACING_COLLECTOR_MAX_FILE_SIZE_MB": 10,
    "USER_SERVICES_TRACING_COLLECTOR_MAX_BACKUPS": 5,
    "USER_SERVICES_TRACING_COLLECTOR_FLUSH_INTERVAL": 10,
    "USER_SERVICES_TRACING_DRAIN_TIMEOUT": 5.0,
    "USER_SERVICES_TRACING_COLLECTOR_STOP_GRACE_PERIOD": 15,
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
        await forwarder._forward_rotated_files()  # noqa: SLF001

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
        await forwarder._forward_rotated_files()  # noqa: SLF001

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
        await forwarder._forward_rotated_files()  # noqa: SLF001

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
        await forwarder._forward_rotated_files()  # noqa: SLF001

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
        USER_SERVICES_TRACING_DRAIN_TIMEOUT=0.1,
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


async def test_forwarder_tails_active_file(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
    mock_successful_post: AsyncMock,
):
    """Active file tail should forward new complete lines."""
    active_file = traces_directory / _ACTIVE_FILE_NAME
    active_file.write_bytes(sample_span_line + b"\n")

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = mock_successful_post
        await forwarder._forward_active_file_tail()  # noqa: SLF001

    mock_client.post.assert_called_once()
    assert forwarder._active_file_offset == len(sample_span_line) + 1  # noqa: SLF001
    # File should still exist (only rotated files get deleted)
    assert active_file.exists()


async def test_forwarder_tail_skips_incomplete_lines(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
):
    """Active file tail should not forward partially written lines."""
    active_file = traces_directory / _ACTIVE_FILE_NAME
    # No trailing newline = incomplete line
    active_file.write_bytes(b"partial-data-no-newline")

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = AsyncMock()
        await forwarder._forward_active_file_tail()  # noqa: SLF001

    mock_client.post.assert_not_called()
    assert forwarder._active_file_offset == 0  # noqa: SLF001


async def test_forwarder_tail_tracks_offset_across_calls(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
    mock_successful_post: AsyncMock,
):
    """Consecutive tail calls should only forward newly appended data."""
    active_file = traces_directory / _ACTIVE_FILE_NAME
    first_line = sample_span_line + b"\n"
    active_file.write_bytes(first_line)

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = mock_successful_post
        await forwarder._forward_active_file_tail()  # noqa: SLF001

    assert forwarder._active_file_offset == len(first_line)  # noqa: SLF001

    # Append more data
    second_line = b'{"another":"span"}\n'
    with active_file.open("ab") as f:
        f.write(second_line)

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = mock_successful_post
        await forwarder._forward_active_file_tail()  # noqa: SLF001

    # Should have forwarded only the second line
    sent_content = mock_client.post.call_args[1]["content"]
    assert sent_content == second_line
    assert forwarder._active_file_offset == len(first_line) + len(second_line)  # noqa: SLF001


async def test_forwarder_rotated_file_skips_already_tailed_bytes(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
    mock_successful_post: AsyncMock,
):
    """When a rotated file is found, only un-tailed bytes should be forwarded."""
    active_file = traces_directory / _ACTIVE_FILE_NAME
    first_line = sample_span_line + b"\n"
    active_file.write_bytes(first_line)

    # Tail the active file (simulates a scrape cycle that tailed some data)
    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = mock_successful_post
        await forwarder._forward_active_file_tail()  # noqa: SLF001

    assert forwarder._active_file_offset == len(first_line)  # noqa: SLF001

    # Simulate rotation: active file becomes rotated, new active file appears
    second_line = b'{"second":"span"}\n'
    with active_file.open("ab") as f:
        f.write(second_line)

    rotated_file = traces_directory / "spans-20250101T000000.jsonl"
    active_file.rename(rotated_file)

    # Process the rotated file — should only send the second line
    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = mock_successful_post
        await forwarder._forward_rotated_file(rotated_file)  # noqa: SLF001

    sent_content = mock_client.post.call_args[1]["content"]
    assert sent_content == second_line
    assert not rotated_file.exists()
    assert forwarder._active_file_offset == 0  # noqa: SLF001


async def test_forwarder_no_duplicate_data_on_rotation(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
    mock_successful_post: AsyncMock,
):
    """Full rotation cycle: tail → rotate → process rotated should not send duplicates."""
    active_file = traces_directory / _ACTIVE_FILE_NAME
    line1 = sample_span_line + b"\n"
    line2 = b'{"resource":"span2"}\n'
    active_file.write_bytes(line1 + line2)

    all_sent: list[bytes] = []

    async def capture_post(*args, **kwargs):
        all_sent.append(kwargs.get("content", args[1] if len(args) > 1 else b""))
        mock_resp = AsyncMock(spec=httpx.Response)
        mock_resp.status_code = 200
        return mock_resp

    # Step 1: Tail the active file
    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = capture_post
        await forwarder._forward_active_file_tail()  # noqa: SLF001

    # Step 2: Simulate rotation
    rotated_file = traces_directory / "spans-20250101T000000.jsonl"
    active_file.rename(rotated_file)

    # Step 3: Process the rotated file
    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = capture_post
        await forwarder._forward_rotated_file(rotated_file)  # noqa: SLF001

    # Verify: the combined sent data equals exactly the original content
    combined = b"".join(all_sent)
    assert combined == line1 + line2
    assert not rotated_file.exists()
