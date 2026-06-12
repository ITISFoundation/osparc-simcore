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
    _CHECKPOINT_FILE_NAME,
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
    return TypeAdapter(TracingSettings).validate_python(
        {
            "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT": "http://otel-collector.internal",
            "TRACING_OPENTELEMETRY_COLLECTOR_PORT": 4318,
            "TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY": 1.0,
        }
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


@pytest.fixture
def capture_post() -> tuple[list[bytes], Callable]:
    """Returns (sent_list, post_handler) — use post_handler as mock_client.post."""
    all_sent: list[bytes] = []

    async def _post(*args, **kwargs):
        all_sent.append(kwargs.get("content", args[1] if len(args) > 1 else b""))
        mock_resp = AsyncMock(spec=httpx.Response)
        mock_resp.status_code = 200
        return mock_resp

    return all_sent, _post


@pytest.fixture
def forwarder_factory(
    traces_directory: Path,
    tracing_settings: UserServiceTracingSettings,
    platform_tracing_settings: TracingSettings,
) -> Callable[..., UserServicesTraceForwarder]:
    """Creates a new forwarder instance (simulates restart scenarios)."""

    def _factory(**settings_overrides: Any) -> UserServicesTraceForwarder:
        return UserServicesTraceForwarder(
            traces_directory=traces_directory,
            tracing_settings=tracing_settings,
            platform_tracing_settings=platform_tracing_settings,
        )

    return _factory


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
    await forwarder.setup()
    assert forwarder._scrape_task is not None  # noqa: SLF001
    assert not forwarder._scrape_task.done()  # noqa: SLF001

    await forwarder.shutdown()
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
    capture_post: tuple[list[bytes], Callable],
):
    """Full rotation cycle: tail → rotate → process rotated should not send duplicates."""
    all_sent, post_handler = capture_post
    active_file = traces_directory / _ACTIVE_FILE_NAME
    line1 = sample_span_line + b"\n"
    line2 = b'{"resource":"span2"}\n'
    active_file.write_bytes(line1 + line2)

    # Step 1: Tail the active file
    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = post_handler
        await forwarder._forward_active_file_tail()  # noqa: SLF001

    # Step 2: Simulate rotation
    rotated_file = traces_directory / "spans-20250101T000000.jsonl"
    active_file.rename(rotated_file)

    # Step 3: Process the rotated file
    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = post_handler
        await forwarder._forward_rotated_file(rotated_file)  # noqa: SLF001

    # Verify: the combined sent data equals exactly the original content
    combined = b"".join(all_sent)
    assert combined == line1 + line2
    assert not rotated_file.exists()


async def test_checkpoint_persisted_after_scrape(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
    mock_successful_post: AsyncMock,
):
    """Checkpoint file should be written after each scrape cycle."""
    active_file = traces_directory / _ACTIVE_FILE_NAME
    active_file.write_bytes(sample_span_line + b"\n")

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = mock_successful_post
        await forwarder._scrape_once()  # noqa: SLF001

    checkpoint = traces_directory / _CHECKPOINT_FILE_NAME
    assert checkpoint.exists()
    assert int(checkpoint.read_text()) == len(sample_span_line) + 1


async def test_checkpoint_reset_after_rotated_file_processed(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
    mock_successful_post: AsyncMock,
):
    """Checkpoint should be reset to 0 when a rotated file is fully processed."""
    # Set a non-zero offset (simulates prior tailing)
    forwarder._active_file_offset = 50  # noqa: SLF001

    rotated_file = traces_directory / "spans-20250101T000000.jsonl"
    rotated_file.write_bytes(b"x" * 50 + sample_span_line)

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = mock_successful_post
        await forwarder._forward_rotated_file(rotated_file)  # noqa: SLF001

    checkpoint = traces_directory / _CHECKPOINT_FILE_NAME
    assert checkpoint.exists()
    assert int(checkpoint.read_text()) == 0
    assert forwarder._active_file_offset == 0  # noqa: SLF001


async def test_restart_recovery_from_checkpoint(
    traces_directory: Path,
    forwarder_factory: Callable[..., UserServicesTraceForwarder],
):
    """A new forwarder instance should resume from persisted checkpoint offset."""
    checkpoint = traces_directory / _CHECKPOINT_FILE_NAME
    checkpoint.write_text("100")

    new_forwarder = forwarder_factory()
    await new_forwarder.setup()
    try:
        assert new_forwarder._active_file_offset == 100  # noqa: SLF001
    finally:
        await new_forwarder.shutdown()


async def test_restart_with_missing_checkpoint(
    forwarder_factory: Callable[..., UserServicesTraceForwarder],
):
    """Without a checkpoint file, forwarder should start from offset 0."""
    new_forwarder = forwarder_factory()
    await new_forwarder.setup()
    try:
        assert new_forwarder._active_file_offset == 0  # noqa: SLF001
    finally:
        await new_forwarder.shutdown()


async def test_drain_does_not_duplicate_tailed_data(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
    capture_post: tuple[list[bytes], Callable],
):
    """Drain after partial tail should not re-send already-forwarded bytes."""
    all_sent, post_handler = capture_post
    active_file = traces_directory / _ACTIVE_FILE_NAME
    line1 = sample_span_line + b"\n"
    line2 = b'{"resource":"span2"}\n'
    active_file.write_bytes(line1 + line2)

    # Step 1: Tail the active file (forwards both lines)
    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = post_handler
        await forwarder._forward_active_file_tail()  # noqa: SLF001

    # Step 2: Drain remaining traces (should NOT re-send the already-tailed data)
    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = post_handler
        await forwarder.drain_remaining_traces()

    # All data should appear exactly once
    combined = b"".join(all_sent)
    assert combined == line1 + line2


async def test_multiple_rotations_offset_applied_to_first_only(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    capture_post: tuple[list[bytes], Callable],
):
    """When 2+ rotations happen between scrapes, offset applies to the oldest file only."""
    all_sent, post_handler = capture_post
    # Simulate: tailed 50 bytes from active file, then 2 rotations happened
    forwarder._active_file_offset = 50  # noqa: SLF001

    first_content = b"x" * 50 + b"UNSENT_FROM_FIRST\n"
    second_content = b"FULL_SECOND_FILE\n"

    first_rotated = traces_directory / "spans-20250101T000000.jsonl"
    second_rotated = traces_directory / "spans-20250101T000001.jsonl"
    first_rotated.write_bytes(first_content)
    second_rotated.write_bytes(second_content)

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = post_handler
        await forwarder._scrape_once()  # noqa: SLF001

    # First file: only unsent portion (skipped 50 bytes)
    # Second file: full content (offset was reset after first file)
    assert b"UNSENT_FROM_FIRST\n" in all_sent[0]
    assert b"FULL_SECOND_FILE\n" in all_sent[1]
    assert not first_rotated.exists()
    assert not second_rotated.exists()
    assert forwarder._active_file_offset == 0  # noqa: SLF001


async def test_rotated_file_smaller_than_offset(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    mock_successful_post: AsyncMock,
):
    """If offset exceeds rotated file size, file should be deleted (all content was tailed)."""
    forwarder._active_file_offset = 1000  # noqa: SLF001

    rotated_file = traces_directory / "spans-20250101T000000.jsonl"
    rotated_file.write_bytes(b"small content")  # 13 bytes < 1000 offset

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = mock_successful_post
        await forwarder._forward_rotated_file(rotated_file)  # noqa: SLF001

    # File should be deleted — all its content was already tailed
    assert not rotated_file.exists()
    # Offset reset for new active file
    assert forwarder._active_file_offset == 0  # noqa: SLF001
    # No HTTP calls needed since unsent_content is empty
    mock_client.post.assert_not_called()


async def test_active_file_truncated_below_offset(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
):
    """If active file is smaller than offset (truncated/replaced), tail should be a no-op."""
    forwarder._active_file_offset = 500  # noqa: SLF001

    active_file = traces_directory / _ACTIVE_FILE_NAME
    active_file.write_bytes(b"short")  # 5 bytes < 500 offset

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = AsyncMock()
        await forwarder._forward_active_file_tail()  # noqa: SLF001

    mock_client.post.assert_not_called()
    # Offset remains unchanged — we don't corrupt it
    assert forwarder._active_file_offset == 500  # noqa: SLF001


async def test_checkpoint_corrupted_content(
    traces_directory: Path,
    forwarder_factory: Callable[..., UserServicesTraceForwarder],
):
    """Corrupted checkpoint file should reset offset to 0."""
    checkpoint = traces_directory / _CHECKPOINT_FILE_NAME
    checkpoint.write_text("not-a-number")

    new_forwarder = forwarder_factory()
    await new_forwarder.setup()
    try:
        assert new_forwarder._active_file_offset == 0  # noqa: SLF001
    finally:
        await new_forwarder.shutdown()


async def test_http_failure_on_second_rotated_file_preserves_it(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    sample_span_line: bytes,
):
    """If HTTP fails on second rotated file, first is gone but second is retained."""
    first_rotated = traces_directory / "spans-20250101T000000.jsonl"
    second_rotated = traces_directory / "spans-20250101T000001.jsonl"
    first_rotated.write_bytes(sample_span_line)
    second_rotated.write_bytes(sample_span_line)

    call_count = 0

    async def fail_on_second(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = AsyncMock(spec=httpx.Response)
        if call_count == 1:
            mock_resp.status_code = 200
        else:
            mock_resp.status_code = 503
        return mock_resp

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = fail_on_second
        await forwarder._scrape_once()  # noqa: SLF001

    # First file forwarded and deleted
    assert not first_rotated.exists()
    # Second file kept for retry
    assert second_rotated.exists()


async def test_drain_with_rotated_and_active_after_partial_tail(
    forwarder: UserServicesTraceForwarder,
    traces_directory: Path,
    capture_post: tuple[list[bytes], Callable],
):
    """Drain with both rotated files and a partially-tailed active file sends no duplicates."""
    all_sent, post_handler = capture_post
    # Simulate: tailed 30 bytes from active, then it rotated, new active has fresh data
    forwarder._active_file_offset = 30  # noqa: SLF001

    rotated_content = b"x" * 30 + b"ROTATED_UNSENT\n"
    active_content = b"FRESH_ACTIVE_DATA\n"

    rotated_file = traces_directory / "spans-20250101T000000.jsonl"
    rotated_file.write_bytes(rotated_content)

    active_file = traces_directory / _ACTIVE_FILE_NAME
    active_file.write_bytes(active_content)

    with patch.object(forwarder, "_client") as mock_client:
        mock_client.post = post_handler
        await forwarder.drain_remaining_traces()

    # Rotated file: skipped first 30 bytes
    assert b"ROTATED_UNSENT\n" in all_sent[0]
    assert b"x" * 30 not in all_sent[0]
    # Active file: sent fully (offset was reset after rotated file)
    assert b"FRESH_ACTIVE_DATA\n" in all_sent[1]
    # Both files deleted
    assert not rotated_file.exists()
    assert not active_file.exists()
