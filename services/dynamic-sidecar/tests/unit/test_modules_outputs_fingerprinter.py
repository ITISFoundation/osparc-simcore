# pylint: disable=redefined-outer-name
# pylint: disable=protected-access
# pylint: disable=unused-argument

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.outputs import _fingerprinter as fingerprinter_module
from simcore_service_dynamic_sidecar.modules.outputs._fingerprinter import (
    PortFingerprint,
)

_PORT_DIR_NAME: Final[str] = "output_1"
_REQUIRED_STABLE_LOOKS: Final[int] = fingerprinter_module._DEFAULT_REQUIRED_STABLE_LOOKS  # noqa: SLF001
# new content is hashed once its stat repeated, so settling takes 2 extra scans
_SCANS_TO_SETTLE: Final[int] = _REQUIRED_STABLE_LOOKS + 2


@pytest.fixture
def hash_pool() -> Iterator[ThreadPoolExecutor]:
    pool = ThreadPoolExecutor(max_workers=4)
    yield pool
    pool.shutdown(wait=True, cancel_futures=True)


@pytest.fixture
def port_dir(tmp_path: Path) -> Path:
    path = tmp_path / _PORT_DIR_NAME
    path.mkdir()
    return path


def _make_fingerprint(directory: Path, hash_pool: ThreadPoolExecutor) -> PortFingerprint:
    return PortFingerprint(directory=directory, hash_executor=hash_pool)


@pytest.fixture
def fingerprinter(port_dir: Path, hash_pool: ThreadPoolExecutor, no_scan_interval_cap: None) -> PortFingerprint:
    return _make_fingerprint(port_dir, hash_pool)


async def _scan(fingerprint: PortFingerprint) -> None:
    await fingerprint._scan_now()  # noqa: SLF001


def _scanning(fingerprint: PortFingerprint) -> bool:
    return fingerprint._is_scanning()  # noqa: SLF001


async def _settle(fingerprint: PortFingerprint, *, max_scans: int = 100) -> None:
    for _ in range(max_scans):
        await _scan(fingerprint)
        if fingerprint.is_settled():
            return
    pytest.fail("port did not settle")


async def _record_upload(fingerprint: PortFingerprint) -> None:
    candidate = fingerprint.take_upload_candidate()
    assert candidate is not None
    fingerprint.note_upload_started(candidate)
    assert await fingerprint.verify_upload_completed() is True


async def test_unchanging_content_settles_after_the_required_stable_looks(
    fingerprinter: PortFingerprint, port_dir: Path
):
    (port_dir / "a.dat").write_bytes(b"hello")

    for _ in range(_SCANS_TO_SETTLE - 1):
        await _scan(fingerprinter)
        assert not fingerprinter.is_settled()

    await _scan(fingerprinter)
    assert fingerprinter.is_settled()


async def test_content_change_resets_the_settling(fingerprinter: PortFingerprint, port_dir: Path):
    (port_dir / "a.dat").write_bytes(b"hello")
    await _settle(fingerprinter)

    (port_dir / "a.dat").write_bytes(b"grew while being watched")
    await _scan(fingerprinter)
    assert not fingerprinter.is_settled()

    await _settle(fingerprinter)


async def test_matches_last_upload_only_after_a_recorded_upload(fingerprinter: PortFingerprint, port_dir: Path):
    (port_dir / "a.dat").write_bytes(b"hello")
    await _settle(fingerprinter)
    assert not fingerprinter.matches_last_upload()

    await _record_upload(fingerprinter)

    await _scan(fingerprinter)
    assert fingerprinter.is_settled()
    assert fingerprinter.matches_last_upload()


async def test_upload_of_content_that_changed_during_upload_is_not_recorded(
    fingerprinter: PortFingerprint, port_dir: Path
):
    (port_dir / "a.dat").write_bytes(b"hello")
    await _settle(fingerprinter)
    candidate = fingerprinter.take_upload_candidate()
    assert candidate is not None
    fingerprinter.note_upload_started(candidate)

    (port_dir / "a.dat").write_bytes(b"grew during the put")
    assert await fingerprinter.verify_upload_completed() is False

    await _settle(fingerprinter)
    assert not fingerprinter.matches_last_upload()


async def test_mtime_only_change_rehashes_to_the_same_fingerprint_and_skips_upload(
    fingerprinter: PortFingerprint, port_dir: Path
):
    file_path = port_dir / "a.dat"
    file_path.write_bytes(b"hello")
    await _settle(fingerprinter)
    await _record_upload(fingerprinter)

    before = file_path.stat()
    file_path.write_bytes(b"hello")  # same size, newer mtime
    assert file_path.stat().st_mtime_ns != before.st_mtime_ns

    await _settle(fingerprinter)
    assert fingerprinter.matches_last_upload()


async def test_missing_port_directory_is_a_stable_empty_state(
    tmp_path: Path, hash_pool: ThreadPoolExecutor, no_scan_interval_cap: None
):
    fingerprinter = _make_fingerprint(tmp_path / "gone", hash_pool)
    for _ in range(_REQUIRED_STABLE_LOOKS):
        await _scan(fingerprinter)
        assert not fingerprinter.is_settled()

    await _scan(fingerprinter)
    assert fingerprinter.is_settled()

    await _record_upload(fingerprinter)
    assert fingerprinter.matches_last_upload()


async def test_symlink_target_content_change_is_detected(
    fingerprinter: PortFingerprint, port_dir: Path, tmp_path: Path
):
    outside = tmp_path / "target.dat"
    outside.write_bytes(b"v1")
    (port_dir / "link.dat").symlink_to(outside)
    await _settle(fingerprinter)
    await _record_upload(fingerprinter)

    outside.write_bytes(b"v2 written through the link")
    await _settle(fingerprinter)
    assert not fingerprinter.matches_last_upload()


async def test_broken_symlink_settles_without_raising(fingerprinter: PortFingerprint, port_dir: Path):
    (port_dir / "broken.dat").symlink_to(port_dir / "never existed")
    await _settle(fingerprinter)
    await _record_upload(fingerprinter)


async def test_unstatable_entry_with_failing_readlink_settles_without_raising(
    fingerprinter: PortFingerprint, port_dir: Path, mocker: MockerFixture
):
    # a link too deep for stat also breaks readlink (ENAMETOOLONG on FUSE mount loops)
    (port_dir / "deep_loop").symlink_to(port_dir / "deep_loop")
    mocker.patch.object(Path, "readlink", side_effect=OSError(36, "File name too long"))

    await _settle(fingerprinter)
    await _record_upload(fingerprinter)

    (port_dir / "deep_loop").unlink()  # the self-loop would block tmp cleanup


async def test_ports_never_share_change_state(
    hash_pool: ThreadPoolExecutor, tmp_path: Path, no_scan_interval_cap: None
):
    dir_a = tmp_path / "port_a"
    dir_b = tmp_path / "port_b"
    dir_a.mkdir()
    dir_b.mkdir()
    # the same relative path in both ports must not couple their ledgers
    (dir_a / "f.dat").write_bytes(b"AAAA")
    (dir_b / "f.dat").write_bytes(b"BBBB")

    fp_a = _make_fingerprint(dir_a, hash_pool)
    fp_b = _make_fingerprint(dir_b, hash_pool)
    await _settle(fp_a)
    await _settle(fp_b)
    assert fp_a._fingerprint != fp_b._fingerprint  # noqa: SLF001

    (dir_b / "f.dat").write_bytes(b"CCCC")
    await _scan(fp_b)
    assert not fp_b.is_settled()

    await _scan(fp_a)
    assert fp_a.is_settled()


async def test_idle_rescan_rehashes_nothing(fingerprinter: PortFingerprint, port_dir: Path, mocker: MockerFixture):
    spy = mocker.spy(fingerprinter_module, "_hash_file")
    (port_dir / "a.dat").write_bytes(b"hello")
    await _settle(fingerprinter)
    assert spy.call_count == 1

    await _scan(fingerprinter)
    await _scan(fingerprinter)
    assert spy.call_count == 1


async def test_only_quiet_files_are_hashed(fingerprinter: PortFingerprint, port_dir: Path, mocker: MockerFixture):
    spy = mocker.spy(fingerprinter_module, "_hash_file")
    (port_dir / "growing.dat").write_bytes(b"chunk1")

    await _scan(fingerprinter)  # stat seen for the first time: nothing hashed yet
    assert spy.call_count == 0

    await _scan(fingerprinter)  # stat repeated: the file is quiet and gets its digest
    assert spy.call_count == 1

    (port_dir / "growing.dat").write_bytes(b"chunk1chunk2")
    await _scan(fingerprinter)  # stat moved once: still possibly mid-write
    assert spy.call_count == 1

    await _scan(fingerprinter)
    assert spy.call_count == 2


async def test_request_scan_respects_single_flight_and_interval_cap(
    port_dir: Path, hash_pool: ThreadPoolExecutor, mocker: MockerFixture
):
    mocker.patch.object(fingerprinter_module, "_DEFAULT_MIN_SCAN_INTERVAL", timedelta(hours=1).total_seconds())
    fingerprinter = _make_fingerprint(port_dir, hash_pool)
    fingerprinter.mark_dirty()
    fingerprinter.request_scan()
    assert _scanning(fingerprinter)

    fingerprinter.mark_dirty()
    fingerprinter.request_scan()  # single flight: no second scan next to the running one
    assert _scanning(fingerprinter)
    await _scan(fingerprinter)

    fingerprinter.mark_dirty()
    fingerprinter.request_scan()  # the interval cap holds until min_scan_interval passed
    assert not _scanning(fingerprinter)


async def test_request_scan_without_demand_does_not_scan(fingerprinter: PortFingerprint):
    await _scan(fingerprinter)  # clears the initial demand
    fingerprinter.request_scan()
    assert not _scanning(fingerprinter)

    fingerprinter.request_scan(force=True)  # pending ports are probed regardless of dirtiness
    assert _scanning(fingerprinter)
    await _scan(fingerprinter)


async def test_burst_of_dirty_marks_collapses_into_one_scan(
    fingerprinter: PortFingerprint, port_dir: Path, mocker: MockerFixture
):
    spy = mocker.spy(fingerprinter_module, "_hash_file")
    (port_dir / "a.dat").write_bytes(b"hello")
    await _scan(fingerprinter)
    assert spy.call_count == 0

    for _ in range(50):
        fingerprinter.mark_dirty()
    assert spy.call_count == 0
    assert not _scanning(fingerprinter)

    fingerprinter.request_scan()
    assert _scanning(fingerprinter)
    await _scan(fingerprinter)
    assert spy.call_count == 1
