# pylint: disable=protected-access
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import asyncio
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Final
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.outputs import _fingerprinter as fingerprinter_module
from simcore_service_dynamic_sidecar.modules.outputs._fingerprinter import (
    CheckOutcome,
    PortFingerprint,
    _ScanResult,
)

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
def on_stable_change() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def fingerprinter(
    port_dir: Path,
    hash_pool: ThreadPoolExecutor,
    on_stable_change: AsyncMock,
    no_quiet_delay: None,
) -> PortFingerprint:
    return PortFingerprint(
        port_key=_PORT_KEY,
        directory=port_dir,
        hash_executor=hash_pool,
        on_stable_change=on_stable_change,
    )


async def _wait_for(cb: AsyncMock, *, calls: int = 1, timeout_s: float = 5.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while cb.call_count < calls:
        if loop.time() > deadline:
            pytest.fail(f"callback called {cb.call_count} times, expected {calls}")
        await asyncio.sleep(0.01)


async def _record_upload(fingerprint: PortFingerprint) -> str:
    candidate = fingerprint.take_upload_candidate()
    assert candidate is not None
    fingerprint.note_upload_started(candidate)
    assert await fingerprint.verify_upload_completed() is True
    return candidate


# --- quiet trigger -------------------------------------------------------------


async def test_event_then_quiet_period_requests_upload(
    fingerprinter: PortFingerprint, on_stable_change: AsyncMock, port_dir: Path
):
    (port_dir / "a.dat").write_bytes(b"hello")

    fingerprinter.note_event()
    await _wait_for(on_stable_change)

    on_stable_change.assert_awaited_once_with(_PORT_KEY)


async def test_quiet_period_restarts_on_late_events(
    port_dir: Path, hash_pool: ThreadPoolExecutor, on_stable_change: AsyncMock, mocker: MockerFixture
):
    # events arriving before the quiet period ends must postpone the check
    mocker.patch.object(fingerprinter_module, "_QUIET_SECONDS", 0.4)
    fingerprinter = PortFingerprint(
        port_key=_PORT_KEY,
        directory=port_dir,
        hash_executor=hash_pool,
        on_stable_change=on_stable_change,
    )
    (port_dir / "a.dat").write_bytes(b"hello")

    fingerprinter.note_event()
    for _ in range(4):
        await asyncio.sleep(0.08)
        fingerprinter.note_event()  # keep touching: never quiet for 0.4 s

    assert on_stable_change.call_count == 0
    await _wait_for(on_stable_change)


async def test_event_during_check_abandons_the_episode(
    fingerprinter: PortFingerprint, on_stable_change: AsyncMock, port_dir: Path, mocker: MockerFixture
):
    (port_dir / "a.dat").write_bytes(b"hello")

    original_scan = fingerprinter._scan  # noqa: SLF001

    async def _scan_with_event_in_between():
        await original_scan()
        fingerprinter.note_event()  # an event lands while the episode is running

    mocker.patch.object(fingerprinter, "_scan", _scan_with_event_in_between)

    fingerprinter.note_event()
    await asyncio.sleep(0.3)

    assert on_stable_change.call_count == 0


async def test_failed_episode_waits_for_the_next_event(
    port_dir: Path,
    hash_pool: ThreadPoolExecutor,
    on_stable_change: AsyncMock,
    no_quiet_delay: None,
    mocker: MockerFixture,
):
    fingerprinter = PortFingerprint(
        port_key=_PORT_KEY,
        directory=port_dir,
        hash_executor=hash_pool,
        on_stable_change=on_stable_change,
    )
    (port_dir / "a.dat").write_bytes(b"hello")

    # the content never looks identical across two scans: every scan reports a new fingerprint
    real_scan = fingerprinter._scan  # noqa: SLF001
    counter = iter(range(1000))

    async def _always_moving_scan() -> _ScanResult:
        result = await real_scan()
        return _ScanResult(fingerprint=f"moving-{next(counter)}", pending_hashes=result.pending_hashes)

    mocker.patch.object(fingerprinter, "_scan", _always_moving_scan)

    fingerprinter.note_event()
    await asyncio.sleep(0.3)
    assert on_stable_change.call_count == 0

    # a later event re-arms the mechanism (here: the scans stabilize again)
    mocker.patch.object(fingerprinter, "_scan", real_scan)
    fingerprinter.note_event()
    await _wait_for(on_stable_change)


# --- check outcomes -------------------------------------------------------------


async def test_new_file_hashes_before_stable(fingerprinter: PortFingerprint, port_dir: Path):
    (port_dir / "a.dat").write_bytes(b"hello")

    assert await fingerprinter.check_now() is CheckOutcome.STABLE_NEW


async def test_check_matching_the_last_upload_skips(fingerprinter: PortFingerprint, port_dir: Path):
    (port_dir / "a.dat").write_bytes(b"hello")
    assert await fingerprinter.check_now() is CheckOutcome.STABLE_NEW
    await _record_upload(fingerprinter)

    assert await fingerprinter.check_now() is CheckOutcome.STABLE_MATCHING


async def test_unstable_content_never_requests_upload(fingerprinter: PortFingerprint, mocker: MockerFixture):
    # every scan leaves a pending hash: the content is in motion
    async def _pending_scan() -> _ScanResult:
        fingerprinter._pending_hashes = 3  # noqa: SLF001
        fingerprinter._fingerprint = "in-motion"  # noqa: SLF001
        return _ScanResult(fingerprint="in-motion", pending_hashes=3)

    mocker.patch.object(fingerprinter, "_scan", _pending_scan)

    assert await fingerprinter.check_now() is CheckOutcome.UNSTABLE
    assert fingerprinter.take_upload_candidate() is None


async def test_stable_but_unrecorded_content_has_a_candidate(fingerprinter: PortFingerprint, port_dir: Path):
    (port_dir / "a.dat").write_bytes(b"hello")
    assert await fingerprinter.check_now() is CheckOutcome.STABLE_NEW

    assert fingerprinter.take_upload_candidate() is not None


# --- save path & verification ----------------------------------------------------


async def test_check_now_cancels_an_armed_episode(
    fingerprinter: PortFingerprint, port_dir: Path, mocker: MockerFixture
):
    mocker.patch.object(fingerprinter_module, "_QUIET_SECONDS", 10.0)
    (port_dir / "a.dat").write_bytes(b"hello")

    fingerprinter.note_event()
    assert fingerprinter.has_pending_work() is True

    assert await fingerprinter.check_now() is CheckOutcome.STABLE_NEW
    assert fingerprinter.has_pending_work() is False


async def test_upload_of_content_that_changed_during_put_is_not_recorded(
    fingerprinter: PortFingerprint, port_dir: Path
):
    (port_dir / "a.dat").write_bytes(b"hello")
    assert await fingerprinter.check_now() is CheckOutcome.STABLE_NEW

    candidate = fingerprinter.take_upload_candidate()
    assert candidate is not None
    fingerprinter.note_upload_started(candidate)

    (port_dir / "a.dat").write_bytes(b"grew during the put")
    assert await fingerprinter.verify_upload_completed() is False


async def test_upload_completed_records_the_fingerprint(fingerprinter: PortFingerprint, port_dir: Path):
    (port_dir / "a.dat").write_bytes(b"hello")
    assert await fingerprinter.check_now() is CheckOutcome.STABLE_NEW
    recorded = await _record_upload(fingerprinter)

    assert fingerprinter._uploaded_fingerprint == recorded  # noqa: SLF001
    assert await fingerprinter.check_now() is CheckOutcome.STABLE_MATCHING


# --- safety sweep -----------------------------------------------------------------


async def test_sweep_triggers_on_drift_without_events(
    fingerprinter: PortFingerprint, on_stable_change: AsyncMock, port_dir: Path
):
    # content changed with no event delivered: simulates a lost inotify event
    (port_dir / "a.dat").write_bytes(b"hello")

    await fingerprinter.sweep()
    await _wait_for(on_stable_change)


async def test_sweep_skips_armed_ports(fingerprinter: PortFingerprint, port_dir: Path, mocker: MockerFixture):
    mocker.patch.object(fingerprinter_module, "_QUIET_SECONDS", 10.0)
    (port_dir / "a.dat").write_bytes(b"hello")

    fingerprinter.note_event()
    scan_spy = mocker.spy(fingerprinter, "_scan")
    await fingerprinter.sweep()
    assert scan_spy.call_count == 0


# --- robustness -------------------------------------------------------------------


async def test_unstatable_entry_with_failing_readlink_survives_check(
    fingerprinter: PortFingerprint, port_dir: Path, mocker: MockerFixture
):
    # a link too deep for stat also breaks readlink (ENAMETOOLONG on deep trees)
    (port_dir / "deep_loop").symlink_to(port_dir / "deep_loop")
    mocker.patch.object(Path, "readlink", side_effect=OSError(36, "File name too long"))

    assert await fingerprinter.check_now() is CheckOutcome.STABLE_NEW

    (port_dir / "deep_loop").unlink()  # the self-loop would block tmp cleanup


async def test_unreadable_file_keeps_upload_eligible_with_warning(
    fingerprinter: PortFingerprint, port_dir: Path, caplog: pytest.LogCaptureFixture
):
    # a file that never hashes must keep the port eligible for upload, not stuck pending
    poison = port_dir / "poison.dat"
    poison.write_bytes(b"secret")
    poison.chmod(0o000)
    try:
        with caplog.at_level(logging.WARNING):
            outcome = await fingerprinter.check_now()

        assert outcome is CheckOutcome.UNSTABLE  # a new random digest per scan: always a change
        assert fingerprinter._pending_hashes == 0  # noqa: SLF001
        assert fingerprinter.take_upload_candidate() is not None
        assert any("poison.dat" in r.message for r in caplog.records)
    finally:
        poison.chmod(0o600)
