# pylint: disable=protected-access
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import asyncio
import logging
import os
import shutil
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Final
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.outputs import _content_monitor as monitor_module
from simcore_service_dynamic_sidecar.modules.outputs._content_monitor import (
    PortContentMonitor,
    StabilityOutcome,
    _ScanResult,
)
from simcore_service_dynamic_sidecar.modules.outputs._upload_trust import PortUploadTrust

_PORT_KEY: Final[str] = "output_1"


@pytest.fixture
def hash_pool() -> Iterator[ThreadPoolExecutor]:
    pool = ThreadPoolExecutor(max_workers=4)
    yield pool
    pool.shutdown(wait=True, cancel_futures=True)


@pytest.fixture
def port_dir(tmp_path: Path) -> Path:
    path = tmp_path / _PORT_KEY
    path.mkdir()
    return path


@pytest.fixture
def on_stable_content() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def monitor(
    port_dir: Path,
    hash_pool: ThreadPoolExecutor,
    on_stable_content: AsyncMock,
    no_quiet_delay: None,
) -> PortContentMonitor:
    return PortContentMonitor(
        port_key=_PORT_KEY,
        directory=port_dir,
        hash_executor=hash_pool,
        on_stable_content=on_stable_content,
    )


@pytest.fixture
def trust(monitor: PortContentMonitor) -> PortUploadTrust:
    return PortUploadTrust(port_key=_PORT_KEY, monitor=monitor)


async def _wait_for(cb: AsyncMock, *, calls: int = 1, timeout_s: float = 5.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while cb.call_count < calls:
        if loop.time() > deadline:
            pytest.fail(f"callback called {cb.call_count} times, expected {calls}")
        await asyncio.sleep(0.01)


async def _stable_fingerprint(monitor: PortContentMonitor) -> str:
    """Runs an immediate check and returns the proven fingerprint, failing when content is not stable"""
    result = await monitor.check_now()
    assert result.outcome is StabilityOutcome.STABLE
    assert result.fingerprint is not None
    return result.fingerprint


async def _record_upload(monitor: PortContentMonitor, trust: PortUploadTrust) -> str:
    candidate = monitor.stable_fingerprint()
    assert candidate is not None
    trust.note_upload_started(candidate)
    assert await trust.verify_upload_completed() is True
    return candidate


@contextmanager
def _directory_that_cannot_be_listed(path: Path) -> Iterator[None]:
    path.chmod(0o000)
    try:
        yield
    finally:
        path.chmod(0o700)


def _build_deep_chain(port_dir: Path, depth: int) -> None:
    # Path.mkdir(parents=True) costs one frame per level: build the chain one mkdir at a time
    deep = port_dir
    for _ in range(depth):
        deep = deep / "a"
        deep.mkdir()
    (deep / "leaf.dat").write_bytes(b"leaf")


def _place_name(port_dir: Path, name: str, *, as_directory: bool) -> None:
    target = port_dir / name
    if target.is_dir():
        target.rmdir()
    if as_directory:
        target.mkdir()
    else:
        target.write_bytes(b"")


# TESTS: quiet trigger


async def test_event_then_quiet_period_reports_stable_content(
    monitor: PortContentMonitor, on_stable_content: AsyncMock, port_dir: Path
):
    (port_dir / "a.dat").write_bytes(b"hello")

    monitor.record_filesystem_event()
    await _wait_for(on_stable_content)

    on_stable_content.assert_awaited_once_with(_PORT_KEY, await _stable_fingerprint(monitor))


async def test_quiet_period_restarts_on_late_events(
    port_dir: Path, hash_pool: ThreadPoolExecutor, on_stable_content: AsyncMock, mocker: MockerFixture
):
    # events arriving before the quiet period ends must postpone the check
    mocker.patch.object(monitor_module, "_QUIET_SECONDS", 0.4)
    monitor = PortContentMonitor(
        port_key=_PORT_KEY,
        directory=port_dir,
        hash_executor=hash_pool,
        on_stable_content=on_stable_content,
    )
    (port_dir / "a.dat").write_bytes(b"hello")

    monitor.record_filesystem_event()
    for _ in range(4):
        await asyncio.sleep(0.08)
        monitor.record_filesystem_event()  # repeat the event: the port never stays quiet for 0.4 s

    assert on_stable_content.call_count == 0
    await _wait_for(on_stable_content)


async def test_event_during_check_abandons_the_check(
    monitor: PortContentMonitor, on_stable_content: AsyncMock, port_dir: Path, mocker: MockerFixture
):
    (port_dir / "a.dat").write_bytes(b"hello")

    original_scan = monitor._scan  # noqa: SLF001

    async def _scan_with_event_in_between():
        await original_scan()
        monitor.record_filesystem_event()  # an event lands while the check is running

    mocker.patch.object(monitor, "_scan", _scan_with_event_in_between)

    monitor.record_filesystem_event()
    await asyncio.sleep(0.3)

    assert on_stable_content.call_count == 0


async def test_failed_check_waits_for_the_next_event(
    port_dir: Path,
    hash_pool: ThreadPoolExecutor,
    on_stable_content: AsyncMock,
    no_quiet_delay: None,
    mocker: MockerFixture,
):
    monitor = PortContentMonitor(
        port_key=_PORT_KEY,
        directory=port_dir,
        hash_executor=hash_pool,
        on_stable_content=on_stable_content,
    )
    (port_dir / "a.dat").write_bytes(b"hello")

    # every scan reports a new fingerprint, so no two scans agree
    real_scan = monitor._scan  # noqa: SLF001
    counter = iter(range(1000))

    async def _always_moving_scan() -> _ScanResult:
        result = await real_scan()
        return _ScanResult(fingerprint=f"moving-{next(counter)}", pending_hashes=result.pending_hashes)

    mocker.patch.object(monitor, "_scan", _always_moving_scan)

    monitor.record_filesystem_event()
    await asyncio.sleep(0.3)
    assert on_stable_content.call_count == 0

    # a later event re-arms the mechanism (here: the scans stabilize again)
    mocker.patch.object(monitor, "_scan", real_scan)
    monitor.record_filesystem_event()
    await _wait_for(on_stable_content)


# TESTS: check outcomes


async def test_new_file_hashes_before_stable(monitor: PortContentMonitor, port_dir: Path):
    (port_dir / "a.dat").write_bytes(b"hello")

    assert (await monitor.check_now()).outcome is StabilityOutcome.STABLE


async def test_check_matching_the_last_upload_is_certified(
    monitor: PortContentMonitor, trust: PortUploadTrust, port_dir: Path
):
    (port_dir / "a.dat").write_bytes(b"hello")
    first = await _stable_fingerprint(monitor)
    assert trust.is_certified(first) is False
    await _record_upload(monitor, trust)

    assert trust.is_certified(await _stable_fingerprint(monitor)) is True


async def test_unstable_content_never_requests_upload(monitor: PortContentMonitor, mocker: MockerFixture):
    # every scan leaves a pending hash: the content is in motion
    async def _pending_scan() -> _ScanResult:
        monitor._pending_hashes = 3  # noqa: SLF001
        monitor._fingerprint = "in-motion"  # noqa: SLF001
        return _ScanResult(fingerprint="in-motion", pending_hashes=3)

    mocker.patch.object(monitor, "_scan", _pending_scan)

    assert (await monitor.check_now()).outcome is StabilityOutcome.UNSTABLE
    assert monitor.stable_fingerprint() is None


async def test_stable_but_unrecorded_content_has_a_candidate(monitor: PortContentMonitor, port_dir: Path):
    (port_dir / "a.dat").write_bytes(b"hello")
    await _stable_fingerprint(monitor)

    assert monitor.stable_fingerprint() is not None


# TESTS: save path and verification


async def test_check_now_cancels_an_armed_check(monitor: PortContentMonitor, port_dir: Path, mocker: MockerFixture):
    mocker.patch.object(monitor_module, "_QUIET_SECONDS", 10.0)
    (port_dir / "a.dat").write_bytes(b"hello")

    monitor.record_filesystem_event()
    assert monitor.has_pending_work() is True

    assert (await monitor.check_now()).outcome is StabilityOutcome.STABLE
    assert monitor.has_pending_work() is False


async def test_cancelling_an_armed_check_stops_it_without_report(
    monitor: PortContentMonitor, on_stable_content: AsyncMock, port_dir: Path, mocker: MockerFixture
):
    # cancellation from outside must stop the check before any scan or report
    mocker.patch.object(monitor_module, "_QUIET_SECONDS", 10.0)
    (port_dir / "a.dat").write_bytes(b"hello")

    monitor.record_filesystem_event()
    check_task = monitor._check_task  # noqa: SLF001
    assert check_task is not None
    await asyncio.sleep(0)  # let the check reach its quiet-period sleep

    check_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await check_task

    await asyncio.sleep(0.3)
    assert on_stable_content.call_count == 0


async def test_check_now_propagates_cancellation_of_its_caller(
    monitor: PortContentMonitor, port_dir: Path, mocker: MockerFixture
):
    # a cancellation aimed at check_now must propagate, not end in the armed-check cleanup
    mocker.patch.object(monitor_module, "_QUIET_SECONDS", 10.0)
    (port_dir / "a.dat").write_bytes(b"hello")

    monitor.record_filesystem_event()  # leaves an armed check for check_now to cancel
    caller = asyncio.create_task(monitor.check_now())
    await asyncio.sleep(0)  # let check_now reach the await on the check it cancelled

    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller


async def test_upload_of_content_that_changed_during_put_is_not_certified(
    monitor: PortContentMonitor, trust: PortUploadTrust, port_dir: Path
):
    (port_dir / "a.dat").write_bytes(b"hello")
    candidate = await _stable_fingerprint(monitor)
    trust.note_upload_started(candidate)

    (port_dir / "a.dat").write_bytes(b"grew during the put")
    assert await trust.verify_upload_completed() is False


async def test_upload_completed_records_the_fingerprint(
    monitor: PortContentMonitor, trust: PortUploadTrust, port_dir: Path
):
    (port_dir / "a.dat").write_bytes(b"hello")
    await _stable_fingerprint(monitor)
    recorded = await _record_upload(monitor, trust)

    assert trust._uploaded_fingerprint == recorded  # noqa: SLF001
    assert trust.is_certified(await _stable_fingerprint(monitor)) is True


# TESTS: safety sweep


async def test_sweep_reports_drift_without_events(
    monitor: PortContentMonitor, on_stable_content: AsyncMock, port_dir: Path
):
    # the content changed and no inotify event arrived
    (port_dir / "a.dat").write_bytes(b"hello")

    await monitor.sweep()
    await _wait_for(on_stable_content)


async def test_sweep_skips_armed_ports(monitor: PortContentMonitor, port_dir: Path, mocker: MockerFixture):
    mocker.patch.object(monitor_module, "_QUIET_SECONDS", 10.0)
    (port_dir / "a.dat").write_bytes(b"hello")

    monitor.record_filesystem_event()
    scan_spy = mocker.spy(monitor, "_scan")
    await monitor.sweep()
    assert scan_spy.call_count == 0


# TESTS: robustness


async def test_same_size_replacement_with_restored_mtime_is_detected(monitor: PortContentMonitor, port_dir: Path):
    # tools like tar and rsync replace a file and restore its mtime; ctime still proves the rewrite
    file_path = port_dir / "a.dat"
    file_path.write_bytes(b"content-v1-aaaa")
    first = await _stable_fingerprint(monitor)

    before = file_path.stat()
    file_path.write_bytes(b"content-v2-bbbb")  # same length as v1
    os.utime(file_path, ns=(before.st_atime_ns, before.st_mtime_ns))

    assert (await monitor.check_now()).outcome is StabilityOutcome.STABLE
    assert monitor._fingerprint != first  # noqa: SLF001


async def test_unstatable_entry_with_failing_readlink_survives_check(
    monitor: PortContentMonitor, port_dir: Path, mocker: MockerFixture
):
    # a link too deep for stat also breaks readlink (ENAMETOOLONG on deep trees)
    (port_dir / "deep_loop").symlink_to(port_dir / "deep_loop")
    mocker.patch.object(Path, "readlink", side_effect=OSError(36, "File name too long"))

    assert (await monitor.check_now()).outcome is StabilityOutcome.STABLE

    (port_dir / "deep_loop").unlink()  # the self-loop would block tmp cleanup


async def test_unreadable_file_keeps_upload_eligible_with_warning(
    monitor: PortContentMonitor, port_dir: Path, caplog: pytest.LogCaptureFixture
):
    # a file that never hashes must keep the port eligible for upload, not stuck pending
    poison = port_dir / "poison.dat"
    poison.write_bytes(b"secret")
    poison.chmod(0o000)
    try:
        with caplog.at_level(logging.WARNING):
            outcome = await monitor.check_now()

        assert outcome.outcome is StabilityOutcome.UNSTABLE  # a new random digest per scan: always a change
        assert monitor._pending_hashes == 0  # noqa: SLF001
        assert monitor.stable_fingerprint() is not None
        assert any("poison.dat" in r.message for r in caplog.records)
    finally:
        poison.chmod(0o600)


async def test_unreadable_port_directory_cannot_be_certified(
    monitor: PortContentMonitor, port_dir: Path, caplog: pytest.LogCaptureFixture
):
    # an unlistable port must not look like an empty port that is already uploaded
    (port_dir / "a.dat").write_bytes(b"hello")
    with _directory_that_cannot_be_listed(port_dir), caplog.at_level(logging.WARNING):
        outcome = await monitor.check_now()

    assert outcome.outcome is StabilityOutcome.UNSTABLE
    assert monitor.stable_fingerprint() is None
    assert any("cannot be listed" in r.message for r in caplog.records)


async def test_missing_port_directory_scans_as_empty_content(
    hash_pool: ThreadPoolExecutor,
    on_stable_content: AsyncMock,
    no_quiet_delay: None,
    tmp_path: Path,
):
    # a port directory that does not exist holds no content: the scan must say so, not stay pending
    monitor = PortContentMonitor(
        port_key=_PORT_KEY,
        directory=tmp_path / "no-such-port",
        hash_executor=hash_pool,
        on_stable_content=on_stable_content,
    )

    result = await monitor.check_now()

    assert result.outcome is StabilityOutcome.STABLE
    assert result.fingerprint == monitor_module.EMPTY_PORT_FINGERPRINT


async def test_deleting_the_port_directory_reports_empty_content(
    monitor: PortContentMonitor, port_dir: Path, trust: PortUploadTrust
):
    (port_dir / "f.dat").write_bytes(b"payload")
    await _stable_fingerprint(monitor)
    await _record_upload(monitor, trust)

    shutil.rmtree(port_dir)
    result = await monitor.check_now()

    assert result.outcome is StabilityOutcome.STABLE
    assert result.fingerprint == monitor_module.EMPTY_PORT_FINGERPRINT
    assert trust.is_certified(result.fingerprint) is False


async def test_deep_directory_chain_is_scanned_without_recursion(monitor: PortContentMonitor, port_dir: Path):
    # recursive scans exhaust the recursion limit on deep trees
    _build_deep_chain(port_dir, depth=1200)

    assert (await monitor.check_now()).outcome is StabilityOutcome.STABLE
    assert any(key.endswith("leaf.dat") for key in monitor._entries)  # noqa: SLF001


async def test_symlink_with_undecodable_target_is_scanned(
    monitor: PortContentMonitor, port_dir: Path, caplog: pytest.LogCaptureFixture
):
    (port_dir / "link").symlink_to(os.fsdecode(b"missing-\xff\xfe-target"))

    with caplog.at_level(logging.WARNING):
        outcome = await monitor.check_now()

    assert outcome.outcome is StabilityOutcome.STABLE
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


async def test_names_that_are_not_valid_utf8_are_distinguished(monitor: PortContentMonitor, port_dir: Path):
    (port_dir / os.fsdecode(b"calf\xe9")).write_bytes(b"x")
    await _stable_fingerprint(monitor)
    first = monitor._fingerprint  # noqa: SLF001

    (port_dir / os.fsdecode(b"calf\xe9")).unlink()
    (port_dir / os.fsdecode(b"calf\xea")).write_bytes(b"x")
    await _stable_fingerprint(monitor)

    assert monitor._fingerprint != first  # noqa: SLF001


async def test_empty_file_and_directory_at_the_same_name_differ(monitor: PortContentMonitor, port_dir: Path):
    # the sentinel classifies a record: its size does not
    _place_name(port_dir, "x", as_directory=True)
    await _stable_fingerprint(monitor)
    first = monitor._fingerprint  # noqa: SLF001

    _place_name(port_dir, "x", as_directory=False)
    await _stable_fingerprint(monitor)

    assert monitor._fingerprint != first  # noqa: SLF001


async def test_uncertified_upload_is_never_matched_against(
    monitor: PortContentMonitor, trust: PortUploadTrust, port_dir: Path
):
    # a PUT of unidentified content must not certify the port
    (port_dir / "a.dat").write_bytes(b"hello")
    await _stable_fingerprint(monitor)
    await _record_upload(monitor, trust)
    assert trust.is_certified(await _stable_fingerprint(monitor)) is True

    trust.note_upload_uncertified()

    new_fingerprint = await _stable_fingerprint(monitor)
    assert trust.is_certified(new_fingerprint) is False
